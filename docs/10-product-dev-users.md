# Baseflo — Product Doc: Developer / Solo Builder

Status: locked for v1; CLI commands ship in M1-M2; custom-connector authoring path ships in M3. This doc covers what developers see, type, and integrate against — including the path to building their own connector for an internal/custom system.

Defers to `01-architecture.md` for system context, `50-design-patterns.md` for the connector framework pattern, and `03-agentic-workflow.md` for the agent surface.

---

## 1. Who They Are

Three developer profiles for v1:

1. **Solo dev with an AI-built frontend** (the friend's case). Built a frontend with Cursor / Lovable / Bolt; needs admin + APIs + database.
2. **Small startup engineer** (1-3 person team). Has a frontend, has Stripe, needs the operations layer between them. Cares about typed SDKs, cares about cost, cares about not being locked in.
3. **Custom-system integrator.** Existing internal CRM or weird data source. Needs to bridge it into Baseflo's unified view. Will build their own connector following our spec.

What they share:
- Comfortable in a terminal.
- Read READMEs before email support.
- Will accept a 5-minute setup if it pays off forever.
- Want types over docs; want signature inspection in their editor over searching the docs site.
- Will recommend us to peers if the SDK is sharp and the CLI is polished.

## 2. The Promise to Developers

> **Two lines of TypeScript and your frontend has a backend. Custom system? Implement seven methods and you're in.**

Plain English: drop in the SDK, ship today. If your system is special enough to need a custom connector, we ship the spec and the scaffolding so you can build one in a focused afternoon.

## 3. The CLI (`baseflo`)

A single Go binary. Cross-platform. Distributed via `curl | sh`, Homebrew tap, and GitHub Releases. Updates checked on invocation; opt-out flag respected.

```
$ baseflo --help
Usage: baseflo <command> [flags]

Commands:
  init        Bootstrap a new project from a config file or prompt
  connect     Add or reconfigure a source connector
  dev         Run engine + admin + Postgres + Redis locally (docker-compose)
  deploy      Push a project's config and custom connectors to hosted or self-host
  versions    List, compare, or rollback project versions
  export      Export full project data (CSV / SQL / JSON)
  tokens      Manage API keys and connector tokens
  connector   Scaffold and manage custom connectors

Run `baseflo <command> --help` for command-specific flags.
```

### 3.1 `baseflo init`

```
$ baseflo init my-shop
```

Interactive: prompts for a one-line business description (or reads from a `baseflo.yaml` if present), authenticates against `app.baseflo.com` (opens browser), creates an organization-or-uses-existing, scaffolds a project, opens the workspace URL in the browser.

Optionally non-interactive:

```
$ baseflo init my-shop --description "Online ceramics shop with reviews" --org my-org --plan hobby
```

Creates a local `baseflo.yaml`:

```yaml
name: my-shop
description: Online ceramics shop with reviews
org: my-org
deployment_mode: hosted    # hosted | byo_db | self_host
api_url: https://api.baseflo.com
project_id: prj_01HZX...   # populated after first sync
```

This file is the project's portable identity; checked into the repo alongside the frontend.

### 3.2 `baseflo connect`

```
$ baseflo connect postgres
Postgres host: db.example.com
Database: production
User: readonly_baseflo
Password: ********
Testing connection... ok (247 tables found)
Connector "postgres" connected to project "my-shop". Tokens are stored securely with the project's KMS.

$ baseflo connect shopify
Opening browser for OAuth...
✓ Connected as my-shop.myshopify.com (1,243 customers, 2,891 orders)
```

For OAuth connectors: opens browser, waits for callback. For API-key connectors: prompts for the key. For DB-URL connectors: prompts for the parts (or accepts a `--dsn` flag). For file uploads (CSV/Excel): accepts `--file path/to/data.csv`.

### 3.3 `baseflo dev`

```
$ baseflo dev
Starting Baseflo dev environment...
✓ Postgres up at localhost:5432
✓ Redis up at localhost:6379
✓ Engine up at http://localhost:8000
✓ Admin UI up at http://localhost:3000
✓ Project "my-shop" loaded.

Watching for connector changes... (Ctrl+C to stop)
```

Spins up the entire stack via docker-compose. Useful for: trying Baseflo without signing up, building/testing custom connectors, integration tests.

### 3.4 `baseflo deploy`

```
$ baseflo deploy
Deploying project "my-shop"...
✓ Config validated
✓ Custom connectors built (1: my_internal_crm v0.3.0)
✓ Pushed to hosted (project_id: prj_01HZX...)
✓ Workspace at https://app.baseflo.com/p/my-shop
```

Pushes `baseflo.yaml`, custom connector modules (if `connectors/` is present in repo), and project state to the configured target. Supports `--target hosted`, `--target self-host --url https://baseflo.internal.example.com`, etc.

### 3.5 `baseflo versions`

```
$ baseflo versions list
v3 (current)  2026-05-08  "Add wishlists"
v2            2026-05-07  "Add product reviews"
v1            2026-05-05  Initial generation

$ baseflo versions diff v2 v3
+ table: wishlists
+   columns: id, customer_id, product_id, created_at
+ relationship: wishlists.customer_id → customers.id (many-to-one)
+ kpi: "Wishlist conversion rate"

$ baseflo versions rollback v2
Rolling back to v2... done. Workspace updated.
```

### 3.6 `baseflo export`

```
$ baseflo export --format sql --out ./exports/
Queueing export job...
✓ Job started (export_01HZX...)
✓ Ready: ./exports/my-shop-v3-2026-05-08.sql.gz
```

### 3.7 `baseflo connector`

The command surface for custom connector authoring:

```
$ baseflo connector init my_internal_crm
Scaffolding new connector "my_internal_crm"...
✓ Created connectors/my_internal_crm/
✓ Created connectors/my_internal_crm/connector.py
✓ Created connectors/my_internal_crm/models.py
✓ Created connectors/my_internal_crm/tests/
✓ Created connectors/my_internal_crm/README.md
Next: implement the seven methods, run `pytest connectors/my_internal_crm/tests/`.

$ baseflo connector test my_internal_crm
Running contract tests for "my_internal_crm"...
[passes/fails inline]

$ baseflo connector validate my_internal_crm
Validating "my_internal_crm" against the protocol spec...
✓ Metadata complete
✓ Auth shape conforms
✓ All required methods present
✓ Capabilities flags consistent with implemented methods
✓ All errors typed (BasefloError + BF-CONN-NNN)
✓ No app/* imports outside app/connectors/base
Ready to deploy.

$ baseflo connector publish my_internal_crm
(M5+; community marketplace flow)
```

## 4. The TypeScript SDK

Published as `@baseflo/sdk`. Generated from the project's schema IR; types regenerate on every refinement and ship with the SDK package.

### 4.1 Install

```bash
npm install @baseflo/sdk
# or pnpm add @baseflo/sdk / yarn add @baseflo/sdk
```

### 4.2 Initialize

```ts
import { createClient } from '@baseflo/sdk';

const baseflo = createClient({
  projectId: process.env.BASEFLO_PROJECT_ID!,
  apiKey: process.env.BASEFLO_API_KEY!,
  baseUrl: 'https://api.baseflo.com',  // or your self-host URL
});
```

### 4.3 Typed Entity Methods

The SDK is generated from the unified schema IR, so what you get is project-specific:

```ts
// For a ceramics-shop schema:
const products = await baseflo.products.list({
  limit: 50,
  filter: { in_stock: true },
  sort: { created_at: 'desc' },
});

const product = await baseflo.products.get('prod_01HZX...');

const newProduct = await baseflo.products.create({
  title: 'Speckled Mug',
  price_minor: 4500,
  price_currency: 'USD',
  in_stock: true,
});

await baseflo.products.update('prod_01HZX...', { in_stock: false });

// Relationships traversal:
const customer = await baseflo.customers.get('cust_01HZX...');
const customerOrders = await customer.orders.list();
```

Every method has full TypeScript signatures derived from `ColumnIR`. Money fields show as minor units with currency. PII fields are typed (`PII<string>`) so you know they're masked client-side by default.

### 4.4 Events

```ts
await baseflo.events.track('order_completed', {
  order_id: 'ord_01HZX...',
  customer_id: 'cust_01HZX...',
  total_minor: 12500,
  total_currency: 'USD',
});
```

Event names are validated against the schema-aware event taxonomy generated by `KPIPlanner`. Unknown event names return a typed error with suggestions.

### 4.5 Refinement (Programmatic)

```ts
const refinement = await baseflo.refinements.propose({
  intent: 'Add wishlists — customers should save products they like.',
});

console.log(refinement.diff_summary);   // human-readable diff
console.log(refinement.change_plan);    // typed plan

const result = await baseflo.refinements.apply(refinement.id);
console.log(result.child_version_id);   // new immutable version
// SDK types regenerate on next install / pnpm update.
```

### 4.6 SSE / Live Updates

```ts
const stream = baseflo.events.subscribe(['orders.created', 'customers.created']);
for await (const event of stream) {
  console.log(event);  // typed event
}
```

### 4.7 Error Handling

Every error is a typed `BasefloError` with an `error_code`, `message`, `details`, and `request_id`. Errors are documented in `40-features/<feature>.md` per `BF-AREA-NNN` family.

```ts
try {
  await baseflo.products.create({ ... });
} catch (e) {
  if (e instanceof BasefloError) {
    console.error(e.code, e.message, e.requestId);
    // e.code: 'BF-VALID-002', e.requestId: 'req_01HZX...'
  }
}
```

## 5. The MCP Server (M3+)

Baseflo ships an MCP (Model Context Protocol) server so AI tools — Claude Code, Cursor, Continue, Cline, Goose — can read and write through us with proper auth and scope.

### 5.1 Setup

```jsonc
// In Claude Code settings:
{
  "mcpServers": {
    "baseflo": {
      "url": "https://api.baseflo.com/mcp",
      "auth": { "type": "bearer", "token": "{{BASEFLO_API_KEY}}" }
    }
  }
}
```

### 5.2 What the AI tool gets

- Tool: `list_products`, `get_customer`, `create_order`, ... (auto-derived from schema IR)
- Tool: `propose_refinement` and `apply_refinement` for evolution
- Resource: `schema_ir` — the AI can read the current schema to ground its actions
- Resource: `recent_activity` — recent events and audit log

The same scope and audit-log rules apply: the AI tool acts as a typed actor (`api_key` actor type) with the API key's scope. Every action is audit-logged with the AI tool's identifier.

### 5.3 Why this matters

Once Baseflo is your operations layer, your AI dev tools become operationally aware. *"Cursor, add a 10% discount to all customers in California"* runs against the SDK with proper auth, audit, and rollback. Refinement and operations stop being separate flows.

## 6. Custom Connectors — Full Authoring Guide

This is the developer-facing version of `50-design-patterns.md` §2. The user-experience promise from `00-decisions.md` is: **n built-in connectors AND unlimited custom connectors built against our published spec**.

### 6.1 When to build a custom connector

- You have an internal CRM or ERP not on the built-in list.
- You have a niche SaaS the marketplace doesn't cover yet.
- You want a transform layer in front of an existing source (e.g., a stricter view of your Postgres).
- You want a write path Baseflo doesn't have built-in (e.g., into a queue we don't natively support).

### 6.2 The seven methods

Per `50-design-patterns.md` §2.1, the protocol is:

```python
class Connector(Protocol):
    metadata: ConnectorMetadata

    async def authenticate(self, credentials: AuthCredentials) -> ConnectorToken: ...
    async def revoke(self, token: ConnectorToken) -> None: ...
    async def introspect_schema(self, token: ConnectorToken) -> SourceSchema: ...
    async def sample_rows(self, token: ConnectorToken, table: str, n: int) -> list[Row]: ...
    async def read(self, token: ConnectorToken, query: SourceQuery) -> AsyncIterator[Row]: ...
    async def write(self, token: ConnectorToken, mutation: SourceMutation) -> WriteResult: ...
    async def webhook_subscribe(self, token: ConnectorToken, events: list[str], callback_url: str) -> Subscription: ...
    async def webhook_unsubscribe(self, subscription: Subscription) -> None: ...
    async def health_check(self, token: ConnectorToken) -> HealthStatus: ...
```

(Eight methods plus `revoke`. The "seven core" framing in marketing copy refers to the conceptual surface: auth, introspect, sample, read, write, webhooks, health.)

### 6.3 Implementation walkthrough — custom internal CRM

```bash
$ baseflo connector init my_internal_crm
# scaffolds connectors/my_internal_crm/
```

Open `connectors/my_internal_crm/connector.py`:

```python
from app.connectors.base import (
    Connector, ConnectorMetadata, ConnectorCapabilities,
    AuthCredentials, ConnectorToken, AuthKind,
    SourceSchema, SourceTable, SourceColumn,
    SourceQuery, SourceMutation, Row, WriteResult,
    Subscription, HealthStatus,
)
from app.connectors.registry import ConnectorRegistry
from app.core.errors import BasefloError

class MyInternalCRMConnector:
    metadata = ConnectorMetadata(
        name="my_internal_crm",
        display_name="My Internal CRM",
        version="0.1.0",
        auth_kind=AuthKind.API_KEY,
        capabilities=ConnectorCapabilities(
            can_introspect=True,
            can_read=True,
            can_write=True,
            can_subscribe_webhooks=False,
            supports_pagination=True,
            requires_periodic_sync=True,
        ),
        required_scopes=["read:contacts", "read:deals", "write:contacts"],
        optional_scopes=[],
    )

    async def authenticate(self, credentials: AuthCredentials) -> ConnectorToken:
        # call your CRM's auth endpoint, validate the API key, return a typed token
        ...

    async def revoke(self, token: ConnectorToken) -> None:
        # if your CRM supports token revocation, call it; else no-op
        ...

    async def introspect_schema(self, token: ConnectorToken) -> SourceSchema:
        # list tables/objects in the CRM, return typed SourceSchema
        return SourceSchema(
            tables=[
                SourceTable(
                    name="contacts",
                    columns=[
                        SourceColumn(name="id", source_type="string", nullable=False, sample_values=[...]),
                        SourceColumn(name="email", source_type="string", nullable=False, sample_values=[...]),
                        ...
                    ],
                    estimated_row_count=1234,
                ),
                ...
            ]
        )

    async def sample_rows(self, token: ConnectorToken, table: str, n: int) -> list[Row]:
        # fetch up to n rows from the table; return typed Row objects
        ...

    async def read(self, token: ConnectorToken, query: SourceQuery) -> AsyncIterator[Row]:
        # implement pagination; yield Row objects one by one
        ...

    async def write(self, token: ConnectorToken, mutation: SourceMutation) -> WriteResult:
        # apply create/update/delete; return typed WriteResult
        ...

    async def webhook_subscribe(self, ...) -> Subscription:
        # if can_subscribe_webhooks=False, raise BF-CONN-002
        raise BasefloError(error_code="BF-CONN-002", message="Webhooks not supported")

    async def webhook_unsubscribe(self, subscription: Subscription) -> None:
        ...

    async def health_check(self, token: ConnectorToken) -> HealthStatus:
        # ping the CRM; return typed health status
        ...

ConnectorRegistry.register(MyInternalCRMConnector)
```

### 6.4 Tests

The scaffold ships with contract tests every connector must pass:

```python
# connectors/my_internal_crm/tests/test_contract.py
from app.connectors.testing import ContractTestSuite
from connectors.my_internal_crm.connector import MyInternalCRMConnector

class TestMyInternalCRM(ContractTestSuite):
    connector_cls = MyInternalCRMConnector
    test_credentials = {"api_key": "test-key"}
    expected_capabilities = {"can_introspect", "can_read", "can_write"}
    sample_table = "contacts"
```

Run: `pytest connectors/my_internal_crm/tests/`. The contract suite covers:
- Metadata is complete and version parses as semver.
- Auth flow accepts valid credentials; rejects invalid.
- `introspect_schema` returns a non-empty `SourceSchema` with at least one table.
- `sample_rows` returns rows shaped correctly per the introspected columns.
- `read` is paginated and respects `query.limit`.
- `write` returns typed `WriteResult` with success/failure indication.
- All errors raise `BasefloError` with `BF-CONN-NNN` codes.
- No imports outside `app.connectors.base` and `app.core` (boundary check).

### 6.5 Local validation

```bash
$ baseflo dev                        # spin up local engine
$ baseflo connect my_internal_crm    # use your custom connector
# admin UI at localhost:3000 should work end-to-end against your CRM
```

### 6.6 Deployment

**Self-host:** drop the connector module into the deployed engine's `connectors/custom/` directory; restart. The registry picks it up at boot.

**Hosted (M4+):** package as a distributable; upload via `baseflo connector deploy` (or the dashboard); we run it in a sandboxed worker that only sees your tenant's data.

### 6.7 Versioning

- Connectors are SemVer-versioned independently from the Baseflo engine.
- The Connector Protocol itself is versioned; breaking protocol changes ship in major engine releases with a 6-month deprecation window.
- A connector declares the protocol version it targets in `metadata.protocol_version`; the engine refuses to load mismatched protocols.

### 6.8 Anti-patterns (will fail validation)

- Returning `dict` instead of typed `Row` / `SourceSchema`.
- Untyped exceptions; every failure must be `BasefloError` with `BF-CONN-NNN`.
- Holding tenant context in module-level globals.
- Importing from `app/engines/` or `app/agents/` (connectors are leaves).
- Calling the LLM (connectors are deterministic; if inference is needed, return raw data and let the agent layer infer).
- Capability flags that don't match implemented methods (e.g., `can_write=True` but no `write` implementation).
- Skipping the contract test suite ("but my connector is special").

## 7. Error Code Reference (Developer-Facing)

Every error a developer will hit is documented per family in `40-features/<feature-id>.md`. Common families:

| Family | Surface | Examples |
|---|---|---|
| `BF-VALID-NNN` | Request validation | `BF-VALID-001` invalid request body, `BF-VALID-002` missing required field |
| `BF-AUTH-NNN` | Authentication / authorization | `BF-AUTH-001` invalid API key, `BF-AUTH-003` insufficient scope |
| `BF-CONN-NNN` | Connectors | `BF-CONN-001` unknown connector, `BF-CONN-002` capability not supported, `BF-CONN-003` token revoked |
| `BF-AGENT-NNN` | Agent execution | `BF-AGENT-003` invalid output, `BF-AGENT-005` repair exhausted |
| `BF-SCHEMA-NNN` | Schema emission | `BF-SCHEMA-001` IR validation failed, `BF-SCHEMA-002` DDL emission failed |
| `BF-COHERENCE-NNN` | CoherenceGate | `BF-COHERENCE-001` repair did not converge |
| `BF-DATA-NNN` | Data plane | `BF-DATA-001` BYO-DB connection failed |
| `BF-JOB-NNN` | Background jobs | `BF-JOB-001` idempotency conflict, `BF-JOB-002` retries exhausted |

Every error response includes `error_code`, `message`, `details`, and `request_id` for support correspondence.

## 8. Rate Limits & Quotas

| Plan | API requests / min | SDK events / min | Generation runs / hour |
|---|---|---|---|
| Hobby | 60 | 600 | 10 |
| Pro | 300 | 3,000 | 60 |
| Business | 3,000 | 30,000 | 600 |
| Enterprise | Custom | Custom | Custom |

Rate-limit headers on every response: `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`. Exceeded → `429` with `Retry-After`.

## 9. Idempotency

Every write endpoint accepts an `Idempotency-Key` header. Same key + same request body returns the same result for 24 hours; same key + different body returns `BF-VALID-009` to surface client bugs.

## 10. SLAs (Hosted Cloud)

- Uptime: 99.5% Hobby/Pro; 99.9% Business; 99.95% Enterprise.
- Status page: `status.baseflo.com`.
- Incident communication: Twitter @baseflohq + status page + email to org owners.
- Post-mortems published within 5 business days for every P1.

## 11. The Developer's First 10 Minutes

The shortest path from "I heard about Baseflo" to "I'm using Baseflo":

```
1. baseflo init my-shop
2. # answer one prompt
3. # browser opens to workspace
4. # copy the SDK install + API key from "Connect to your frontend"
5. cd my-frontend && pnpm add @baseflo/sdk
6. # paste two lines into your code
7. # frontend hits real API
```

Total time: under 10 minutes if everything is configured right; under 5 once you've done it once. That's the bar.
