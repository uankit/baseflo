# Baseflo — System Architecture

Status: locked for first build. Changes require an entry in `00-decisions.md`.

This document describes the entire system. Implementation details are in feature-specific docs under `docs/40-features/`. Coding rules are in `docs/05-coding-rules.md`.

---

## 1. North Star

A small business or developer connects what they already use (Excel, Notion, Postgres, Shopify, Zoho, Stripe, Mailchimp, Twilio, custom DB or REST). Within roughly 90 seconds they receive:

1. A unified, agentically-derived schema that reconciles entities across sources into one coherent business model.
2. A hosted admin panel where they can run their business day-to-day (CRUD, search, filters, exports).
3. A typed REST + TypeScript SDK any frontend (or any AI tool like Claude Code) can wire up in two lines.
4. A schema-aware behavioral intelligence layer (cohorts, funnels, retention, regional, what's selling, who's churning, what customers asked for that you don't carry).
5. A daily digest replacing vendor-email noise.
6. A refinement experience where every change is described in plain English and produces a new immutable workspace version.

The product principle: **agents reason like architects; deterministic compilers verify and emit; the user sees a polished product, not the machinery.**

## 2. System Overview

```
                          ┌─────────────────────────────────────┐
                          │        BASEFLO ENGINE               │
                          │  (one codebase, four runners)       │
                          └───────────────┬─────────────────────┘
                                          │
       ┌──────────────────────────────────┼─────────────────────────────────┐
       │                                  │                                 │
┌──────▼──────┐                  ┌────────▼────────┐                ┌───────▼───────┐
│ Hosted      │                  │  BYO Database   │                │ Self-Host     │
│ Cloud       │                  │ (customer's PG) │                │ Docker        │
│ (multi-tnt) │                  │                 │                │ (cust. infra) │
└─────────────┘                  └─────────────────┘                └───────────────┘
                                          
                                  Local Dev: `baseflo dev` — same engine, container locally.

USER SURFACES (over all four runners):
  ─ Hosted admin panel (browser; CRUD UI generated from unified schema)
  ─ Typed REST + TypeScript SDK (codegen from schema IR; for any frontend or AI tool)
  ─ Daily digest (one notification layer)
  ─ MCP server (AI agents read/write through us with auth)
  ─ CLI (`baseflo init`, `baseflo connect`, `baseflo testdb`, `baseflo deploy`, `baseflo dev`)
  ─ Refinement-by-conversation (structured English diff producing a new version)
```

## 3. Engine Internals

The engine is a multi-agent graph plus deterministic compilers. The boundary is strict: agents reason; compilers verify and emit. No semantic decision is made in deterministic Python; no structural emission is made by an agent.

### 3.1 Layered View

```
┌─────────────────────────────────────────────────────────────────┐
│ API Layer        FastAPI routers, request/response boundary     │
├─────────────────────────────────────────────────────────────────┤
│ Conversation     SSE pub/sub, intent routing, clarification     │
│ Runtime          state machine, refinement intake               │
├─────────────────────────────────────────────────────────────────┤
│ Orchestration    Generation jobs, pipeline stages, repair       │
│                  loops, traces, idempotency                     │
├─────────────────────────────────────────────────────────────────┤
│ Agent Graph      Pydantic-Graph node graph; specialist agents;  │
│ (Pydantic AI)    handoff manager; output validators             │
├─────────────────────────────────────────────────────────────────┤
│ Engine Core      Schema IR, multi-source unification, KPI       │
│                  planner, intelligence layer, refinement diff   │
├─────────────────────────────────────────────────────────────────┤
│ Connector        Adapter plugins (per source), token vault,     │
│ Framework        introspection, sample-row pull, sync mode      │
├─────────────────────────────────────────────────────────────────┤
│ Data Plane       Interface; four implementations                │
│                  (Hosted / BYO / Self-host / Local)             │
├─────────────────────────────────────────────────────────────────┤
│ Repositories     SQLAlchemy access; per-tenant scoping;         │
│                  audit-log writer middleware                    │
├─────────────────────────────────────────────────────────────────┤
│ Database         Control plane (orgs, users, projects, runs,    │
│ (Postgres)       audit) + per-tenant generated schemas          │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 Agent Graph

Specialist agents run as nodes in a Pydantic-Graph. Each has typed input, typed output, an optional output validator, a model tier, and is independently testable with `TestModel`.

```
ConversationManager
  └── ClarificationAgent          (preflight gate; max 3 questions; only when truly blocking)

DataArchitectGraph
  ├── ColumnClassifier            (per-column: PII / status / money / id / temporal / category / free-text;
  │                                also produces canonical names and labels for naming hints)
  ├── EntityReconciler            (decide which entities span which sources; conflict resolution policy — THE MOAT)
  ├── CardinalityResolver         (1..1 / 1..* / *..* across reconciled entities; FK direction)
  ├── ConstraintProposer          (uniqueness, FKs, status transitions, money minor units, nullability)
  ├── PhysicalSchemaArchitect     (compose unified schema IR from reconciled entities + constraints)
  ├── KPIPlanner                  (which business questions are answerable; grain; assumptions; drives analytics tab + daily digest)
  └── CoherenceGate               (INTERNAL gate, never user-surfaced. Cross-cutting consistency check across all
                                   prior outputs. Emits typed RepairRoute on failure; manager re-runs the indicated
                                   specialist with corrected context. User sees a transparent re-run flash, not a report.)

RefinementGraph
  ├── IntentInterpreter           (parse English diff intent: add / remove / rename / split / merge)
  ├── ImpactAnalyzer              (which artifacts change; cascading effects)
  └── ChangePlanner               (concrete delta plan against schema IR; mechanical merge into child IR is deterministic)

Deterministic compilers (no agents needed)
  ─ ConnectorIntrospector        (mechanical: every connector has list_tables / describe_table)
  ─ DashboardSpec emitter        (KPI shape → chart type, dimensions → axes; mechanical from KPIPlanner output)
  ─ ChildVersionCompiler         (parent IR + change plan → child IR via typed merge)
  ─ ExplanationLookup            (lazy on-demand; agent call only when user clicks "why is this here?")

Manager (DB-backed, deterministic)
  ─ Selects which specialist runs next
  ─ Catches typed errors (BF-AGENT-NNN), routes to repair or clarification
  ─ Persists trace envelopes after artifacts commit (never blocks workspace.ready)
```

**v1 agent count: 11.** 10 produce typed artifacts the engine compiles and the user (eventually) sees the *result* of; 1 (`CoherenceGate`) is an internal terminal gate the user never sees directly — it either passes (workspace ships) or emits a typed repair route (manager re-runs the indicated specialist; user sees a transparent re-run flash like "Refining schema...").

Pruned from the original 17 — `IntentClassifier` (UI routes intent), `ConnectorIntrospector` (mechanical via connector APIs), `DashboardComposer` (deterministic emission from `KPIPlanner` output), `ExplanationAuthor` (lazy on-demand only), `ChildVersionAuthor` (deterministic merge), and `BehaviorPlanner` (deferred dev convenience). `CoherenceGate` replaces the trust-workspace `CriticReviewer` with a sharper, internal-only contract.

**The repair-routing pattern (gate-driven, not agent-internal):** `CoherenceGate` does not loop. It is a one-shot gate that returns either `passed=True` or `passed=False` with a list of typed `RepairRoute` items (each naming the agent to re-run and the corrected context to inject). The manager applies repair routes; up to two repair attempts; on still-failing it escalates to `ClarificationAgent` for user input. This pattern is documented as the only acceptable form of repair loops; ad-hoc loops inside specialists are forbidden.

Every node:
- Has a Pydantic input model and a Pydantic output model. Both must be strongly typed (no `Any`, no bare `dict`).
- Declares a `model_tier` (`fast` / `balanced` / `reasoning`).
- Has at least one output validator. Validators raise `ModelRetry(...)` on recoverable issues.
- Is registered in `agents/registry.py`. Adding a new agent edits one file plus the new node module.

### 3.3 Schema IR (canonical layer)

Pydantic data classes representing the post-reconciliation, pre-DDL view of the business.

```python
class ColumnIR(BaseModel):
    name: str                            # snake_case identifier
    label: str                           # user-facing name
    semantic_type: SemanticType          # enum: identity, money, status, temporal, pii_email, ...
    physical_type: PhysicalType          # enum: int, bigint, text, varchar, decimal, ...
    nullable: bool
    default: Optional[Default]
    minor_unit_for: Optional[Currency]   # set when semantic_type == money
    enum_values: Optional[list[str]]     # set when semantic_type == status

class TableIR(BaseModel):
    name: str
    label: str
    purpose: str
    grain: str                           # one row per ___
    primary_key: list[str]
    columns: list[ColumnIR]
    sources: list[SourceRef]             # which connectors contribute to this table

class RelationshipIR(BaseModel):
    from_table: str
    from_columns: list[str]
    to_table: str
    to_columns: list[str]
    cardinality: Cardinality             # enum: ONE_TO_ONE, ONE_TO_MANY, MANY_TO_ONE, MANY_TO_MANY
    on_delete: OnDelete

class SchemaIR(BaseModel):
    version: int
    tables: list[TableIR]
    relationships: list[RelationshipIR]
    indexes: list[IndexIR]
    notes: list[Assumption]              # explicit assumptions surfaced by agents
```

The IR is the contract. Agents emit `SchemaIR`-shaped Pydantic objects (typed). Compilers consume `SchemaIR`. No path between the two uses an untyped dict.

### 3.4 Connector Framework

Adapter pattern. Every connector implements:

```python
class Connector(Protocol):
    name: str
    auth: AuthSpec                       # OAuth2 / API key / database URL / file upload

    async def authenticate(self, credentials: dict) -> ConnectorToken: ...
    async def introspect_schema(self, token: ConnectorToken) -> SourceSchema: ...
    async def sample_rows(self, token: ConnectorToken, table: str, n: int) -> list[dict]: ...
    async def read(self, token: ConnectorToken, query: SourceQuery) -> AsyncIterator[Row]: ...
    async def write(self, token: ConnectorToken, mutation: SourceMutation) -> WriteResult: ...
    async def webhook_subscribe(self, token: ConnectorToken, events: list[str]) -> Subscription: ...
```

Connectors register themselves with `ConnectorRegistry` at import. Adding a new connector creates a new module under `server/app/connectors/<name>/`, implements the protocol, registers itself, ships its OAuth/key handler. The agent layer never touches connector internals; it sees `SourceSchema` and `Row` types.

**v1 connectors:** Postgres, CSV/Excel upload, Shopify (then Stripe and Mailchimp by end of M1).

### 3.5 Multi-Source Unification — the moat

This is the differentiated subsystem and is worth describing in detail.

When a customer has Excel + Shopify + their existing Postgres + Notion, the engine cannot simply concatenate per-source schemas. The same entity (e.g., a customer) may exist in three places with different keys, conflicting fields, and different update frequencies. The agent graph reconciles them into one unified IR.

**Stage 1: Per-source introspection.**
`ConnectorIntrospector` runs once per connected source. It produces a `SourceSchema` (tables, columns, types, sample rows, observed cardinalities). Deterministic; no LLM involved. The output is structurally typed.

**Stage 2: Column classification across sources.**
`ColumnClassifier` (LLM agent) sees all source columns at once and assigns each a `SemanticType` (identity, money, status, temporal, pii_email, pii_phone, address, free_text, foreign_key_candidate, derived). It also produces canonical names ("customer_email" across sources).

**Stage 3: Entity reconciliation.**
`EntityReconciler` (LLM agent) decides which logical entity each source table contributes to. Output is an `EntityReconciliationPlan`:

```python
class ReconciledEntity(BaseModel):
    canonical_name: str                  # "Customer"
    sources: list[SourceContribution]    # which source tables feed this entity
    join_keys: list[JoinKey]             # how rows correspond across sources
    conflict_policy: ConflictPolicy      # which source is authoritative when fields disagree
    merge_strategy: MergeStrategy        # full_union | preferred_source | latest_write_wins
```

This is the part nobody else does agentically. The agent reasons: "Shopify customers (`customers.id`, `customers.email`) and Excel contacts (`Email`, `Name`, `Phone`) appear to be the same entity reconciled by lowercased email; Shopify is authoritative for billing fields; Excel is authoritative for phone."

**Stage 4: Cardinality and constraints.**
`CardinalityResolver` and `ConstraintProposer` operate over the reconciled entities. `MANY_TO_MANY` becomes an explicit join table; FK directions are inferred from cardinality; status fields get enum values; money fields get currency + minor units.

**Stage 5: Physical schema composition.**
`PhysicalSchemaArchitect` emits the unified `SchemaIR`. The deterministic compiler then emits:
- Postgres DDL (via the existing schema IR → DDL compiler).
- A read-side query plan: how to populate each unified table from source connectors (used by the read path).
- A write-side fan-out plan: how to write back to authoritative sources when a user edits in the admin panel.

**Stage 6: Critic review.**
`CriticReviewer` reviews the unified IR against business intent and flags shallow or contradictory output. Failures trigger a typed repair loop (not a silent fix).

The output of this subgraph is the schema the user will see in their admin panel — agentically reconciled, deterministically validated, fully traceable back to source columns.

### 3.6 Intelligence Layer (behavioral analytics)

Schema-aware events. Once the unified schema exists, the engine generates a typed event taxonomy from it: a Shopify-derived schema yields `cart_created`, `checkout_started`, `order_completed`, `refund_issued`. A bookings-derived schema yields `booking_requested`, `booking_confirmed`, `booking_cancelled`, `no_show`. The `KPIPlanner` agent produces the catalog of metrics; the deterministic engine compiles them into typed SQL definitions, executes them against generated rows or live data depending on deployment mode, and renders them as cards in the admin.

The `Intelligence Engine` is responsible for:
- Funnels (signup → first action → conversion → repeat).
- Cohorts (week-of-signup retention; per-source acquisition).
- Geographic distribution (when address columns exist).
- "What's selling" (highest-grossing product, lowest-stock SKU).
- Anomalies ("yesterday's failed-payment count is 3× the trailing average").
- Daily digest composition (the one summary email replacing vendor noise).

This layer reuses the analytics work from the previous Baseflo with the heuristic shims removed — the agent owns metric *selection*; the deterministic compiler owns SQL *emission and execution*.

### 3.7 Hosted Admin UI Generation

The admin panel is rendered from the unified `SchemaIR` plus agent-provided labels and `purpose` strings. The same rendering layer is used in all deployment modes; it's a thin client over the engine's read/write APIs.

Components:
- **List view per table** (TanStack Table; columns derived from `ColumnIR`; PII fields masked by default; one-click reveal, audit-logged).
- **Detail view per row** (form generated from `ColumnIR`; relationships render as linked entities).
- **Search / filter** (server-side; uses the same SQL generation as KPIs).
- **Exports** (CSV / SQL / JSON; one click; goes through audit log).
- **Refinement panel** (right rail; English-language deltas → new version).
- **Daily digest preview** (top of dashboard; configurable).

The UI knows nothing about specific verticals. It renders whatever the unified schema describes, with PII protection and refinement built in.

### 3.8 Refinement & Versioning

Every refinement produces a new immutable `project_version`. Parent lineage is preserved. The user can compare versions, roll back, or fork.

Refinement intent is interpreted by a real agent (`IntentInterpreter`), not by keyword matching. The `ImpactAnalyzer` computes the cascading effects on schema, KPIs, dashboard, and admin views. The `ChangePlanner` produces a typed `ChangePlan`; the compiler emits the new version. No silent rewrites; every change is auditable.

## 4. Deployment Modes

Same engine code; the data plane is an interface with four implementations. Selection is at runtime via configuration.

### 4.1 Hosted Cloud (default)

- Multi-tenant Postgres on our managed AWS instance.
- Per-tenant schemas with row-level security where shared tables exist.
- Per-tenant KMS keys (AWS KMS).
- All connector tokens encrypted with the tenant's KMS key; never logged in plaintext.
- Audit log written for every read/write of customer data.
- Standard SaaS: encrypted at rest (AES-256), encrypted in transit (TLS 1.3).
- Backup: daily snapshots, 30-day retention.
- Region: US-East default; EU region added once first EU customer signs.

### 4.2 BYO Database

- Customer provides a Postgres connection string (Neon / Supabase / RDS / on-prem).
- Engine connects with the same migration system; tenant data lives in customer DB.
- We hold connector tokens in our control-plane Postgres (encrypted with customer-supplied KMS key when possible; otherwise our KMS for the tenant).
- The engine treats the customer DB as the source of truth; we do not replicate to ours.
- Migration tool: Alembic against the customer DB, owned by their connection string.
- Failure mode: if customer DB is unreachable, the admin shows a typed health error and clear remediation; no silent fallback to cached data.

### 4.3 Self-Host Docker

- Single Docker image containing the engine + control-plane Postgres + admin UI + Redis (for arq).
- Distributed via Docker Hub and a Helm chart for Kubernetes.
- License-key activation; offline mode supported (license periodically validated against our license server when online; cached for 30 days when offline).
- Updates: customer pulls a new image; engine handles migrations on boot.
- Telemetry: anonymized usage opt-in only; no customer data leaves their infra.
- Support: license tier dictates response SLA.

### 4.4 Local Dev

- `baseflo dev` from the CLI. Spins up engine + Postgres + Redis in a Docker compose stack.
- Used by indie devs during build phase before going hosted.
- Same code path as Self-Host minus the license check.

## 5. Privacy & Security Architecture

### 5.1 Encryption

- TLS 1.3 in transit; AES-256-GCM at rest.
- Per-tenant data encryption key (DEK) wrapped by per-tenant key encryption key (KEK) in AWS KMS.
- Connector tokens are encrypted with the tenant's KEK before being stored.
- Logs scrub PII fields by default using the agent-classified `SemanticType` (anything classified `pii_*` is masked at log emission).

### 5.2 Tenant Isolation

- Hosted Cloud: Postgres schema per tenant; engine workers scope every query with `tenant_id`; row-level security policies enforced at the DB layer.
- All API requests carry an authenticated tenant context; no engine call can execute without one.
- Cross-tenant queries are impossible by design (no SQL emitted by compilers includes a `WHERE tenant_id = ?` we forgot — the data plane interface refuses to execute without tenant context).

### 5.3 Connector Token Lifecycle

- Token storage: encrypted with tenant KEK.
- Token scope: minimum required by the connector's API (e.g., Shopify scopes are read-only by default; write scopes prompt the user).
- Token revocation: one-click in admin UI; revokes our copy and (when supported) calls the source provider's revoke endpoint.
- Token rotation: refresh tokens used where supported; alerts surface when an integration approaches token expiry.
- Audit: every token use is logged with timestamp, action, and source IP of the engine worker.

### 5.4 PII Detection

- Agent-driven: `ColumnClassifier` labels each column with a `SemanticType` including `pii_email`, `pii_phone`, `pii_address`, `pii_name`, `pii_id_number`.
- Deterministic guards:
  - Admin UI masks PII columns by default; reveal requires user action and is audit-logged.
  - Exports of PII columns require explicit confirmation.
  - Logs scrub PII columns automatically.
- v1 does not include automated detection of PII inside free-text columns (e.g., "John's email is …" inside a notes field). Flagged as v3 — Presidio integration on the architecture roadmap.

### 5.5 Audit Log

- Every read and write of customer data writes an `audit_events` row (control-plane DB).
- Fields: tenant, actor (user or agent), action, target (table + row id), timestamp, source IP, request id.
- Retention: 1 year hosted-cloud default; configurable in BYO/self-host.
- Surfaced in admin UI under Settings → Audit.

### 5.6 Data Export & "Take Your Data and Leave"

- One-click full export from Settings → Export.
- Formats: CSV (per table), SQL (DDL + INSERTs), JSON (full project blob including IR + KPI definitions + connector configs minus tokens).
- Goes through a job; user is emailed when ready; signed URL expires in 24h.
- This is a brand promise on the landing page. It is non-negotiable.

## 6. Control Plane

The control-plane database is detailed in `docs/04-database-schema.md`. Briefly, the entities are:

- `organizations` — billing entities; one or more users, one or more workspaces.
- `users` — auth identities; belong to one or more organizations via memberships.
- `memberships` — user ↔ organization with role (owner/admin/editor/viewer).
- `workspaces` — a project's container; belongs to one organization.
- `projects` — a connected business; belongs to one workspace.
- `project_versions` — immutable versions of a project's IR + KPIs + dashboards.
- `connectors` — per-project source connections.
- `connector_tokens` — encrypted credentials for connectors.
- `generation_jobs` and `generation_steps` — pipeline run records.
- `agent_runs` and `agent_run_attempts` — per-agent telemetry.
- `audit_events` — security audit log.
- `digest_subscriptions` — daily digest preferences.
- `share_links` — read-only project sharing.
- `feedback_events` — user corrections feeding the data flywheel.

Per-tenant generated schemas (the actual customer data) live separately, named by `tenant_id`, and are managed by the engine through the data plane.

## 7. Job Queue and Event Stream

### 7.1 Background Jobs

- `arq` (Redis-backed) for async work.
- Job categories: connector sync, generation pipeline, refinement, export, digest composition, scheduled re-introspection.
- Idempotency: every job has a deterministic key; redrives don't duplicate work.
- Retries: exponential backoff with a typed terminal-failure path; failures emit a `BF-JOB-NNN` error.
- Dead-letter queue: persistent failures land in `failed_jobs` with operator review.

### 7.2 SSE Event Stream

- Live conversation/generation progress streamed via Server-Sent Events.
- Pub/sub backbone: Postgres `LISTEN/NOTIFY` (works in single-instance and multi-instance deploys without Redis).
- Event categories: `conversation.message`, `clarification.required`, `agent.start`, `agent.complete`, `validation.passed`, `validation.warning`, `validation.failed`, `artifact.ready`, `workspace.ready`, `error.recoverable`, `error.terminal`.
- Replay: events are persisted with monotonic sequence numbers; client can resume from last seen.

## 8. Observability

- Structured logs (JSON) via `structlog`. Every log has `tenant_id`, `request_id`, `job_id` where applicable.
- OpenTelemetry traces: every API request, every agent run, every connector call.
- Metrics: per-agent latency, token usage, repair-loop fire counts, connector success/failure rates, queue depth, job duration.
- Sentry for unhandled exceptions.
- Cost dashboard: token usage rolled up per tenant per day → input to billing and per-customer profitability tracking.

## 9. Scalability

- Engine workers are stateless; horizontally scalable.
- Pub/sub via Postgres `LISTEN/NOTIFY` works across worker instances.
- Per-tenant rate limits enforced at the API gateway and per-connector at the worker.
- Heavy work (generation, sync, export) runs in `arq` queues, not in the API request thread.
- Pydantic AI agents are cached by `(tenant, agent_name, output_schema, instructions_hash, model_name)` with bounded LRU + 1h TTL.
- The agent registry is read-only at runtime; warming the cache on worker boot is cheap.
- Database scaling: read replicas for analytics queries; primary for writes; per-tenant connection pool.

## 10. Failure Modes & Repair

The architecture document is a living promise; failures are first-class.

- **Connector source unavailable:** typed health error in admin; cached "last known good" for read-side display where appropriate; no silent stale data.
- **Agent output invalid:** repair loop fires (max 2 attempts) using `ModelRetry`; if still invalid after repair, escalates to a higher model tier; if still invalid, emits `BF-AGENT-003` and asks the user a clarifying question.
- **Schema unification ambiguous:** the `EntityReconciler` produces an `AmbiguityReport`; if the ambiguity is business-decisive, the user sees a clarifying question; if not, the agent picks with an explicit assumption surfaced as a warning on the workspace.
- **DDL emission fails:** structural failure in the compiler; emits `BF-SCHEMA-NNN` with the offending IR fragment; never patches silently.
- **Job worker crash:** `arq` retry; idempotency key prevents duplication; persistent failure surfaces in admin Settings → Health.
- **Connector token expired/revoked:** specific error path; admin shows a "reconnect" prompt; no fallback to stale data.

Every failure has a `BF-AREA-NNN` code, a test asserting it, and a defined recovery path.

## 11. Test Topology

- **Unit tests:** every agent (`TestModel` / `FunctionModel`), every compiler, every repository, every connector adapter.
- **Integration tests:** API → service → engine → DB happy paths; SSE replay; connector OAuth flows (against connector sandboxes).
- **Contract tests:** schema-IR ↔ SDK codegen ↔ admin UI rendering.
- **End-to-end tests:** Playwright on the hosted admin in a test tenant.
- **Load tests:** k6 against the API; goals defined per release.
- TDD-first is enforced: no PR mergeable without tests written before the implementation.

## 12. Roadmap Anchors (full list in `docs/30-features.md`)

The architecture supports the entire product. The build sequences only when a slice is shippable end-to-end.

- **M0 — Engine refactor.** Delete heuristics, tighten schemas, wire `pydantic-graph`, set up control plane, ship local dev mode.
- **M1 — Single-source magic moment.** Postgres + CSV connectors. ColumnClassifier, EntityReconciler (single-source path), KPIPlanner, hosted admin UI, daily digest. Validation: your friend's case.
- **M2 — Multi-source unification.** Add Shopify; flip on full reconciliation graph. Validation: a real e-commerce SMB drops Excel + Shopify and sees one view.
- **M3 — BYO-DB + Stripe + Mailchimp.** First privacy-conscious tier; one billing+marketing connector each.
- **M4 — Self-host Docker + license server.** First enterprise tier.
- **M5 — MCP server + AI-agent surface.** Claude/Cursor read/write through us.

Subsequent features (per `docs/30-features.md`): scenario simulation, connector marketplace, mobile companion, EU region, SOC2, additional verticals as horizontal extensions.
