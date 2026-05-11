# `SDK-AND-API` — TypeScript SDK + REST API

Status: M1. Combines `SDK-TS` + `API-REST` from [`30-features.md`](../30-features.md). What developers integrate against. Two lines of TypeScript and the friend's frontend has a backend.

---

## 1. Overview

Two cooperating pieces:

- **REST API** at `app.baseflo.com/api/v1/...` — generated OpenAPI spec from FastAPI; idempotency-key support on writes; standard error envelope (`error_code`, `message`, `details`, `request_id`).
- **TypeScript SDK** published as `@baseflo/sdk` — generated from each project's unified `SchemaIR` so types are project-specific (`baseflo.products.list()` instead of `baseflo.entities.list("products")`). Tiny runtime; types-first.

The SDK regenerates on every refinement so types stay in lockstep with the schema. Devs run `pnpm update @baseflo/sdk` after applying a refinement.

## 2. High-Level Design

```
SchemaIR (per project, per version)
        │
        ├──▶ OpenAPI spec generator (fastapi.openapi)
        │            │
        │            ▼
        │      OpenAPI YAML
        │            │
        │            ▼
        │      openapi-typescript ──▶ generated types
        │            │
        │            ▼
        │      Custom codegen (entity methods)
        │            │
        │            ▼
        │      @baseflo/sdk-<project_id>@<version>
        │            │
        │            ▼
        │      npm publish to private registry (or public for hosted)
        │
        └──▶ FastAPI routes auto-derived for entity CRUD
```

## 3. Low-Level Design

### 3.1 Module Layout

```
server/app/api/v1/
├── routes/
│   ├── conversations.py
│   ├── projects.py
│   ├── refinements.py
│   ├── connectors.py
│   ├── exports.py
│   ├── share_links.py
│   ├── feedback.py
│   ├── events.py             # POST /api/v1/projects/:id/events
│   ├── entities.py           # /api/v1/projects/:id/entities/:table  (CRUD; auto-derived)
│   └── health.py
├── errors.py                 # error envelope + BasefloError → HTTP mapping
├── idempotency.py            # Idempotency-Key middleware
├── pagination.py             # cursor-based; never offset
└── tests/

sdk/ts/
├── package.json              # @baseflo/sdk
├── src/
│   ├── client.ts             # createClient(config) factory
│   ├── http.ts               # fetch wrapper; retries; error parsing
│   ├── types.ts              # generated types (per project)
│   ├── entities/             # generated entity methods
│   │   ├── customers.ts
│   │   ├── orders.ts
│   │   └── ...
│   ├── events.ts             # baseflo.events.track(...)
│   ├── refinements.ts        # baseflo.refinements.propose(...).apply(...)
│   ├── sse.ts                # baseflo.events.subscribe(...)
│   └── errors.ts             # BasefloError class
├── codegen/
│   ├── generate.ts           # IR → SDK source files
│   └── templates/            # handlebars-style templates per entity method shape
└── tests/

cli/                          # Go binary (separate; ships M2+)
└── ...
```

### 3.2 The Standard Error Envelope

Every error response:

```json
{
  "error_code": "BF-VALID-002",
  "message": "Required field missing: customer_id",
  "details": { "field": "customer_id", "received": null },
  "request_id": "req_01HZX8ABC..."
}
```

`request_id` is propagated from FastAPI middleware; clients include it in support tickets.

### 3.3 Auto-Derived Entity Endpoints

For every reconciled entity in the unified `SchemaIR`, FastAPI exposes:

- `GET    /api/v1/projects/:id/entities/:table` — list (cursor-paginated; filters per `ColumnIR.semantic_type`).
- `GET    /api/v1/projects/:id/entities/:table/:row_id` — detail.
- `POST   /api/v1/projects/:id/entities/:table` — create (idempotency-key supported).
- `PATCH  /api/v1/projects/:id/entities/:table/:row_id` — update (write-back routed to canonical source per `EntityReconciliationPlan`).
- `DELETE /api/v1/projects/:id/entities/:table/:row_id` — soft-delete (or hard depending on config).
- `GET    /api/v1/projects/:id/entities/:table/:row_id/relationships/:rel_name` — linked entities.

All of these are generated; no per-table hand coding. The route handler reads the IR + plan + connector token and dispatches through the data plane.

### 3.4 The SDK Surface

Generated per project:

```ts
import { createClient } from '@baseflo/sdk';

const baseflo = createClient({
  projectId: process.env.BASEFLO_PROJECT_ID!,
  apiKey: process.env.BASEFLO_API_KEY!,
  baseUrl: 'https://api.baseflo.com',
});

// List
const { data, nextCursor } = await baseflo.products.list({
  limit: 50,
  filter: { in_stock: true },
  sort: { created_at: 'desc' },
});

// Get
const product = await baseflo.products.get('prod_01HZX...');

// Create
const created = await baseflo.products.create({
  title: 'Speckled Mug',
  price_minor: 4500,
  price_currency: 'USD',
  in_stock: true,
});

// Update
await baseflo.products.update('prod_01HZX...', { in_stock: false });

// Relationship traversal
const customer = await baseflo.customers.get('cust_01HZX...');
const orders = await customer.orders.list();

// Events
await baseflo.events.track('order_completed', {
  order_id: 'ord_01HZX...',
  total_minor: 12500,
  total_currency: 'USD',
});

// Refinements
const proposal = await baseflo.refinements.propose({
  intent: 'Add wishlists.',
});
console.log(proposal.diff);
const applied = await baseflo.refinements.apply(proposal.id);

// Live updates
for await (const ev of baseflo.events.subscribe(['orders.created'])) {
  console.log(ev);
}

// Errors
try {
  await baseflo.products.create({ ... });
} catch (e) {
  if (e instanceof BasefloError) {
    console.error(e.code, e.requestId);
  }
}
```

Every method has full typed signatures derived from `ColumnIR`. Money fields are `MoneyMinor` with currency. PII fields are `PII<string>`. Status fields are typed string literals (`"active" | "paused" | "cancelled"`).

### 3.5 Codegen Process

On every committed `project_versions` row:
1. Schema IR + KPI definitions retrieved.
2. OpenAPI spec for that project's entity endpoints generated.
3. `openapi-typescript` produces base types.
4. Custom generator produces entity method files using handlebars templates.
5. Package built and pushed to npm (private scoped tag for non-public projects; public for opted-in).
6. SDK version bumped (semver: minor for additive refinements, major for breaking).
7. Workspace UI surfaces the latest version in the "Connect to your frontend" modal.

## 4. Design Patterns Applied

| Pattern | Where | Why |
|---|---|---|
| **Codegen** | IR → SDK + types | Single source of truth; zero hand-maintained drift. |
| **Adapter** | `http.ts` wraps `fetch` | Retry, error parsing, auth header injection in one place. |
| **Iterator** | `events.subscribe(...)` returns async iterator | Standard for SSE streams. |
| **Builder** | OpenAPI spec generation per project | Composable from IR pieces. |

## 5. Test Plan

- OpenAPI spec stability: same IR → same OpenAPI bytes (deterministic).
- Generated SDK compiles with `tsc --strict`.
- Generated SDK round-trips: create → list → update → delete against test API.
- Idempotency: same key + same body = same result; same key + different body = `BF-VALID-009`.
- Pagination: cursor-based; consistent across pages with concurrent writes.
- Coverage: 90%.

## 6. Error Codes

| Code | Condition | Recovery |
|---|---|---|
| `BF-VALID-001` | Invalid request body | 400; details include the bad field. |
| `BF-VALID-002` | Required field missing | 400; field name in details. |
| `BF-VALID-009` | Idempotency-key conflict | 409. |
| `BF-API-001` | Unknown entity | 404. |
| `BF-API-002` | Rate limit exceeded | 429 with Retry-After. |

## 7. Dependencies

[`IR-CORE`](IR-CORE.md), [`AUTH`](AUTH.md), [`ADMIN-GEN`](ADMIN-GEN.md) (shares the auto-derived entity endpoint logic).

## 8. Milestone

- **M1**: REST API + SDK shipped for the friend's case; auto-derived entity endpoints; events tracking; refinement methods.
- **M2**: SDK regenerates on every refinement; semver-correct version bumps.
- **M3**: Python SDK; per-table fine-grained scopes on API keys.
- **M5+**: GraphQL surface (optional).
