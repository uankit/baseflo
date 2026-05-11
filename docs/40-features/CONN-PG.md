# `CONN-PG` — Postgres Connector

Status: M1. The flagship built-in connector. Conforms to the [`CONN-FRAMEWORK`](CONN-FRAMEWORK.md) protocol.

---

## 1. Overview

Direct Postgres connection — the customer points us at any Postgres database (their own RDS, Neon, Supabase, on-prem). The connector introspects the schema via `information_schema`, samples rows, reads via async cursor, writes via parameterized queries, and tracks change events via Postgres LISTEN/NOTIFY (where the customer's DB grants the privilege).

This is also the connector used by the Hosted Cloud + Self-Host data planes to read their own tenant data — the connector framework is uniform, so internal-loopback queries use the same code path as external-source queries.

## 2. Module Layout

```
server/app/connectors/postgres/
├── __init__.py
├── connector.py              # PostgresConnector implementing Connector Protocol
├── auth.py                   # DSN parsing + TLS config
├── introspection.py          # information_schema queries → SourceSchema
├── reader.py                 # async cursor; pagination via keyset (created_at, id)
├── writer.py                 # parameterized INSERT/UPDATE/DELETE; idempotent
├── webhooks.py               # LISTEN/NOTIFY-based change subscriptions when granted
└── tests/
    ├── test_contract.py      # extends ContractTestSuite
    ├── test_introspection.py
    ├── test_reader.py
    ├── test_writer.py
    └── fixtures/             # Docker compose Postgres for integration tests
```

## 3. Capabilities

```python
metadata = ConnectorMetadata(
    name="postgres",
    display_name="Postgres",
    version="1.0.0",
    protocol_version="1.0",
    auth_kind=AuthKind.DB_URL,
    capabilities=ConnectorCapabilities(
        can_introspect=True,
        can_read=True,
        can_write=True,
        can_subscribe_webhooks=True,            # via LISTEN/NOTIFY when CREATE TRIGGER privilege granted
        supports_pagination=True,
        supports_streaming=True,
        requires_periodic_sync=False,            # webhook-driven when subscribed; poll otherwise
        write_back_canonical_only=True,
    ),
    required_scopes=["SELECT"],                  # baseline read
    optional_scopes=["INSERT", "UPDATE", "DELETE", "TRIGGER", "LISTEN"],
)
```

## 4. Auth

- DSN format: `postgresql://user:pass@host:port/db?sslmode=require`.
- TLS: required by default; customer can opt to plaintext for localhost.
- CA cert: optional, supplied separately for self-signed deployments.
- Read-only role recommended; write capability automatically detected by introspecting role grants.

Token storage: full DSN encrypted with tenant KMS per [`SECURITY.md`](SECURITY.md).

## 5. Introspection

```sql
-- Tables
SELECT table_schema, table_name
FROM information_schema.tables
WHERE table_schema NOT IN ('pg_catalog', 'information_schema');

-- Columns + types
SELECT column_name, data_type, is_nullable, column_default
FROM information_schema.columns
WHERE table_schema = $1 AND table_name = $2;

-- Primary keys
SELECT a.attname
FROM pg_index i JOIN pg_attribute a ON ...

-- Foreign keys
SELECT ... FROM information_schema.referential_constraints ...

-- Estimated row counts via pg_stat_user_tables (cheap; not exact)
SELECT schemaname, relname, n_live_tup
FROM pg_stat_user_tables;
```

Output is mapped to typed `SourceSchema` / `SourceTable` / `SourceColumn`. Source types are preserved verbatim; `ColumnClassifier` later assigns semantic types.

## 6. Read

Async cursor with keyset pagination (`(created_at, id) > $cursor`). Fetches in chunks of 1000; backpressure via the consumer. SSL+TLS active.

Filter compilation: typed `SourceQuery.filter` compiled to parameterized SQL via SQLGlot — never string interpolation. `IN` clauses bounded by 100 values; larger filter sets paginated.

## 7. Write

`SourceMutation` → INSERT/UPDATE/DELETE via parameterized queries. Returns typed `WriteResult` with affected_rows + new_id (for INSERT). Idempotent: if mutation includes `idempotency_key`, the connector first checks `baseflo_idempotency` table (created by us in the customer's DB if write capability is granted) and short-circuits.

## 8. Webhooks

When the customer grants `TRIGGER` and `CREATE FUNCTION` privileges, the connector creates a per-table trigger that calls `pg_notify('baseflo_<project_id>', ...)` on row changes. The connector subscribes via `LISTEN`. When privileges aren't granted, falls back to periodic polling at the connector-configured cadence.

## 9. Test Plan

- Contract suite (`ContractTestSuite`) — required.
- Integration tests against Postgres in CI via Docker compose:
  - Introspection of a fixture schema.
  - Read with filter, sort, pagination, cursor.
  - Write: create, update, delete; idempotency.
  - LISTEN/NOTIFY subscription delivery on insert.
  - Reconnect after network drop.
- Coverage: 92%.

## 10. Error Codes

Inherits `BF-CONN-NNN` family. Specific:

| Code | Condition |
|---|---|
| `BF-CONN-PG-001` | DSN parse failure |
| `BF-CONN-PG-002` | TLS handshake failure |
| `BF-CONN-PG-003` | Insufficient privilege for write |
| `BF-CONN-PG-004` | LISTEN/NOTIFY not granted; falling back to poll |
| `BF-CONN-PG-005` | Schema introspection requires `usage` on schema |

## 11. Dependencies

[`CONN-FRAMEWORK`](CONN-FRAMEWORK.md), `asyncpg`, SQLGlot.

## 12. Milestone

- **M1**: full implementation; ships as the first built-in connector; integration tested in CI.
- **M2**: LISTEN/NOTIFY-based change subscriptions hardened.
- **M3**: read-replica targeting for large analytics queries; connection-pool tuning per tenant.
