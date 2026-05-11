# `DEPLOYMENT` — Hosted Cloud / BYO-DB / Self-Host / Local Dev Runners

Status: M0–M3. Combines `DEP-HOSTED` + `DEP-BYO` + `DEP-LOCAL` + (M3) `DEP-SELFHOST` + `DEP-LICENSE`. The four-runner abstraction.

---

## 1. Overview

One engine codebase, four runners. The data-plane interface is the seam; engine and agent code never branch on deployment mode. Selecting a runner is a config flip on the project.

This is the architectural decision that makes Baseflo defensible for enterprise (BYO-DB / self-host) without paying a refactor tax later.

## 2. High-Level Design

```
                          ┌────────────────────────────┐
                          │        Engine + Agents      │
                          │       (one codebase)        │
                          └──────────────┬─────────────┘
                                         │
                                         ▼ data_plane.query / write / emit_ddl / execute_kpi
                          ┌─────────────────────────────────────────────┐
                          │              DataPlane (Protocol)            │
                          └─────┬──────────────┬──────────────┬─────────┘
                                │              │              │
              ┌─────────────────┘              │              └────────────────┐
              ▼                                ▼                               ▼
   ┌─────────────────┐               ┌──────────────────┐             ┌───────────────────┐
   │ HostedDataPlane │               │ BYODataPlane     │             │ SelfHostDataPlane │
   │ (multi-tenant   │               │ (customer's PG)  │             │ (their infra)     │
   │  PG on AWS)     │               │                  │             │                   │
   └─────────────────┘               └──────────────────┘             └───────────────────┘

                                ┌──────────────────┐
                                │ LocalDataPlane   │  (dev-time docker-compose)
                                └──────────────────┘
```

## 3. Low-Level Design

### 3.1 Module Layout

```
server/app/engines/data_plane/
├── __init__.py
├── base.py                  # DataPlane Protocol
├── hosted.py                # multi-tenant Postgres on our infra; tenant-scoped schemas
├── byo_db.py                # customer-supplied DSN; engine connects but never persists customer rows in our DB
├── self_host.py             # bundled Postgres in customer's Docker; license-aware
├── local_dev.py             # docker-compose dev stack; same code as self_host minus license check
├── factory.py               # make_data_plane(mode, project) -> DataPlane
└── tests/
    ├── test_hosted.py
    ├── test_byo_db.py
    └── test_local_dev.py

infra/
├── docker/
│   ├── server/Dockerfile
│   ├── worker/Dockerfile
│   └── compose.dev.yml
├── helm/                    # M3+ Helm chart for self-host Kubernetes
└── terraform/               # M2+ hosted-cloud infrastructure
```

### 3.2 The Protocol

```python
class DataPlane(Protocol):
    async def emit_ddl(self, ir: SchemaIR, ctx: TenantCtx) -> EmissionResult: ...
    async def query(self, plan: QueryPlan, ctx: TenantCtx) -> AsyncIterator[Row]: ...
    async def write(self, mutation: Mutation, ctx: TenantCtx) -> WriteResult: ...
    async def execute_kpi(self, kpi: KPIDefinition, ctx: TenantCtx) -> KPIResult: ...
    async def health(self, ctx: TenantCtx) -> HealthStatus: ...
    async def migrate(self, from_version: int, to_version: int, ctx: TenantCtx) -> MigrationResult: ...
```

### 3.3 Hosted Cloud Runner

- Multi-tenant Postgres on AWS RDS.
- Per-tenant schemas (`tenant_<org_slug>_<project_slug>`); engine uses `SET search_path = tenant_..., public`.
- Per-tenant KMS via AWS KMS (per `SECURITY.md`).
- Connection pool per worker; reused across tenants but RLS-scoped.
- Backups: daily snapshots, 30-day retention.
- Region: us-east-1 default; eu-west-1 added when first EU customer signs.

### 3.4 BYO-Database Runner

- Customer provides a Postgres connection string; engine validates it accepts the required extensions (uuid-ossp or equivalent for UUIDv7; or we ship UUIDv7 generation in app code if extension unavailable).
- Engine emits DDL into the schema named per-project; only that schema is touched.
- Connection string stored encrypted (per-tenant KMS) in our control plane; never in plaintext in any log.
- Health check: ping every 5min; alert if unreachable; admin UI degrades gracefully (cached metadata only).
- Failure mode: customer-DB downtime surfaces typed `BF-DATA-001` to the admin UI; no silent stale data.

### 3.5 Self-Host Runner (M3+)

- Single Docker image (`baseflo/engine:<version>`) bundles engine + worker + admin UI server.
- External requirements: Postgres + Redis + S3-compatible storage + LLM provider key (or self-hosted model endpoint).
- License-key activation: contacts our license server on boot; cached for 30 days offline.
- Updates: customer pulls new image; alembic migrations run on boot.
- Telemetry: opt-in only; anonymized counts; never customer rows.
- Helm chart for Kubernetes deployments.

### 3.6 Local Dev Runner

- `baseflo dev` from the CLI spins up `compose.dev.yml`: engine + worker + Postgres + Redis + admin UI on localhost.
- Same code path as self-host minus license check.
- Used by indie devs during build; by us for dev/test; by custom-connector authors validating against their own modules.

### 3.7 Switching Modes

Settings → Deployment → switch mode triggers a migration job:
1. Old plane: full export.
2. New plane: validate connection (BYO-DB / self-host).
3. New plane: emit DDL.
4. New plane: import data.
5. Verify: row counts match; KPI sanity checks.
6. Cut over `current_version_id` and `deployment_mode`.
7. Old plane: schedule cleanup (30-day soft delete).

Cut-over has a 30-day rollback window during which old data is retained.

### 3.8 The Factory

```python
def make_data_plane(project: Project) -> DataPlane:
    match project.deployment_mode:
        case DeploymentMode.HOSTED:    return HostedDataPlane(...)
        case DeploymentMode.BYO_DB:    return BYODataPlane(decrypted_dsn(project))
        case DeploymentMode.SELF_HOST: return SelfHostDataPlane(...)
        case DeploymentMode.LOCAL_DEV: return LocalDataPlane(...)
```

Engine code calls `data_plane.query(...)` regardless. The strategy resolves at request time.

## 4. Design Patterns Applied

| Pattern | Where | Why |
|---|---|---|
| **Strategy** | Four runner implementations of one protocol | The architectural unlock. |
| **Factory** | `make_data_plane` | Per-request resolution from project config. |
| **Adapter** | `BYODataPlane` adapts customer's Postgres to our protocol | Customer provides any compatible DB. |

## 5. Test Plan

- Per-runner contract tests (same suite, four implementations).
- Hosted: tenant isolation under load.
- BYO-DB: connection failure handling; customer-DB downtime gracefully surfaced.
- Self-host: license check (online + offline modes).
- Local dev: docker-compose up → end-to-end smoke.
- Mode-switch test: project moved hosted → BYO-DB end-to-end.
- Coverage: 90%.

## 6. Error Codes

| Code | Condition | Recovery |
|---|---|---|
| `BF-DATA-001` | Customer DB unreachable (BYO-DB) | Admin UI degrades; cached metadata; alert. |
| `BF-DATA-002` | DDL emission failed in target | Surface verbatim error; no silent fallback. |
| `BF-DATA-003` | Mode-switch validation failed (row counts mismatch) | Abort cut-over; old plane retained. |
| `BF-DATA-004` | License invalid or expired (self-host) | Admin UI shows reactivation flow. |
| `BF-DATA-005` | Self-host extension missing | Boot-time fail-fast with clear remediation. |

## 7. Dependencies

[`IR-CORE`](IR-CORE.md), [`IR-DDL`](IR-DDL.md), [`SECURITY`](SECURITY.md), [`AUTH`](AUTH.md), Postgres, Redis, AWS / KMS / S3.

## 8. Milestone

- **M0**: Hosted Cloud + Local Dev runners.
- **M1**: Hosted Cloud production-ready; mode-switch flow scaffolded.
- **M3**: BYO-DB runner; mode-switch flow live; first paying privacy-conscious customer.
- **M4**: Self-host Docker + Helm; license server; first paying enterprise customer.
- **M5+**: EU region; multi-region routing.
