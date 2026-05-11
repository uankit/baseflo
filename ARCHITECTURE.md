# Baseflo Architecture v2 — Artifact-Centric Agent OS

## Principles

1. **Agents reason. Code executes.** Agents produce structured artifacts. Deterministic code validates and executes them. No LLM writes SQL directly.
2. **Artifacts are the API between agents.** Typed, versioned, persisted. Not function calls, not messages.
3. **The system is eventually consistent.** Agents run asynchronously when possible. The user sees progress, not blocking spinners.
4. **Fallback is transparency.** If an agent is unsure, it says so with evidence. It does not guess.
5. **Human-in-the-loop for high-stakes actions.** Agents suggest. Humans approve. Low-risk actions can be auto-executed.
6. **No stubs. No dead code. No M2/M3 deferrals.** If a feature is not in v1, it does not exist in the codebase.
7. **Plug-play-extend.** Connectors, agents, and actions are registered via clean protocols. Adding a new connector or agent is one file + one registration call.

---

## Artifact Store

The central shared state. Every agent reads and writes artifacts. Artifacts are immutable versions stored in Postgres.

```python
class Artifact[T](BaseModel):
    artifact_id: UUID
    project_id: UUID
    artifact_type: str           # "source_map", "entity_graph", "schema_ir", "insight_board"
    version: int                 # monotonic per project per type
    payload: T                   # typed artifact content
    produced_by: str             # agent name or "user"
    provenance: ArtifactProvenance  # inputs, model used, tokens, timing
    created_at: datetime
```

Artifact types:
- `SourceMap` — per-connector schema understanding (tables, columns, semantic types, samples)
- `EntityGraph` — canonical entities, cross-source mappings, merge rules, confidence scores
- `SchemaIR` — unified physical schema (tables, columns, relationships, indexes, assumptions)
- `InsightBoard` — KPIs, segments, anomalies, narratives, recommended actions
- `ActionPlan` — list of operations to execute (queries, API calls, emails)

---

## Agent System (4 Agents)

### 1. SourceAgent (per connector)
**Input:** Raw connector data + business description
**Output:** `SourceMap` artifact
**Model tier:** Balanced (gpt-4.1)
**When it runs:** On connector install, on schema change detection, on user request
**Responsibility:** Understand what this source contains. Tables, columns, semantic types, sample values, freshness.

### 2. ReconciliationAgent
**Input:** All `SourceMap` artifacts for a project + business description
**Output:** `EntityGraph` artifact
**Model tier:** Reasoning (o3-mini or Claude Opus)
**When it runs:** After any SourceAgent completes, or when user adds/modifies sources
**Responsibility:** Find the same entity across sources. Resolve conflicts. Define merge rules and authoritative sources.

### 3. SchemaAgent
**Input:** `EntityGraph` + business description
**Output:** `SchemaIR` artifact
**Model tier:** Balanced (gpt-4.1)
**When it runs:** After ReconciliationAgent, or on user request
**Responsibility:** Design the unified physical schema. Tables, columns, types, relationships, indexes. Produce DDL-ready output.

### 4. InsightAgent
**Input:** `SchemaIR` + `EntityGraph` + user question or schedule trigger
**Output:** `InsightBoard` artifact
**Model tier:** Reasoning for complex queries, Balanced for routine
**When it runs:** On-demand (user asks), scheduled (daily/weekly), or event-triggered (anomaly detected)
**Responsibility:** Answer business questions, generate KPIs, detect anomalies, suggest actions.

### Deterministic Layer
**CoherenceValidator** (not an agent) — pure Python structural checks on any artifact. Run before persisting an artifact. No LLM.

**ActionExecutor** (not an agent) — deterministic execution of `ActionPlan`. SQL queries, API calls, email sends. Retry, idempotency, audit logging.

---

## Connector Framework

Protocol-based. Every connector implements:

```python
class Connector(Protocol):
    metadata: ConnectorMetadata
    async def authenticate(self, credentials: ...) -> ConnectorToken: ...
    async def read(self, table: str, *, cursor: str | None = None, limit: int = 1000) -> AsyncIterator[Row]: ...
    async def write(self, table: str, rows: list[Row]) -> WriteResult: ...
    async def introspect_schema(self) -> SourceSchema: ...
    async def health_check(self) -> HealthStatus: ...
```

Webhook-capable connectors additionally implement:
```python
    async def webhook_subscribe(self, url: str, events: list[str]) -> Subscription: ...
    async def webhook_unsubscribe(self, sub_id: str) -> None: ...
    def webhook_verify(self, request_headers: dict, body: bytes, secret: str) -> bool: ...
```

**v1 Connectors:**
- Postgres (read + webhook via LISTEN/NOTIFY)
- CSV (read-only, file upload)
- Excel (read-only, file upload)
- Google Sheets (read + write + webhook via Drive push)
- Shopify (read + write + webhook)
- Stripe (read + write + webhook)

No deferred features. If a connector doesn't support a capability, it raises `BF-CONN-002` with a clear message.

---

## Data Plane

### Ingestion
```
Connector read / Webhook receipt → Normalize → Reconcile → Materialize → Refresh insights
```

**Batching is mandatory.** No row-at-a-time operations.
- `CanonicalUpserter.upsert_many(rows: list[Row])` → single `INSERT … ON CONFLICT … RETURNING`
- `IdResolver.resolve_many(source_ids: list[str])` → single batch query
- `BackfillRunner.backfill_table` → streams from connector in batches, upserts in batches

### Storage
- Control plane: shared Postgres (organizations, users, projects, artifacts, connectors)
- Tenant data: per-tenant Postgres schema (hosted mode) or customer Postgres (BYO-DB mode)
- v1 scope: hosted mode only. BYO-DB is a future feature.

### Analytics
- **Hosted mode:** Compile KPIs to Postgres SQL, execute against tenant schema directly. No DuckDB materialization.
- **BYO-DB mode (future):** Use DuckDB against a read replica or exported snapshot.

### Reconciliation
- `EntityIdMap`: `(project_id, entity_kind, source, source_id) → canonical_id`
- `EntityIdentityIndex`: `(project_id, entity_kind, identity_key, identity_hash) → canonical_id`
- Merge on identity match. Human review for confidence < 0.9.
- DELETE handling: hard-delete canonical row + cascade to id_map. Real implementation.

---

## Action Layer (v1)

Actions are triggered by InsightAgent recommendations or user-defined rules.

v1 action types:
1. **Alert** — Send email (via Resend) or Slack webhook
2. **Tag** — Update customer tags in Shopify, Stripe, Mailchimp
3. **Export** — Generate CSV/Excel report and email it
4. **Webhook** — POST to user-defined URL with event payload

No outbound calling in v1. No cold email automation in v1. The infrastructure for identifying targets exists; the execution layer stays digital.

---

## Orchestration

### Build Flow (schema generation)
Explicit DAG, not a graph framework:
```
SourceAgent(s) in parallel → ReconciliationAgent → SchemaAgent → CoherenceValidator
```
Each step produces an artifact. Steps are idempotent. Same inputs → cached artifact (hash-based).

### Runtime Flow (continuous sync)
Event-driven, not graph-based:
```
Webhook / Poll / File upload → IngestionService → ReconciliationService → MaterializationService → InsightRefreshService
```
Each service is a standalone worker (arq job). Services communicate via artifact updates and events.

### Refinement Flow
```
User request → InsightAgent interprets → SchemaAgent updates SchemaIR → CoherenceValidator → Artifact persisted
```
Runs asynchronously via arq. Not inline in API handler.

---

## Coding Standards

1. **Type everything.** No `Any`, no `dict[str, Any]` in production code. `extra="forbid"` on all Pydantic models.
2. **No print statements.** Use `structlog` with correlation IDs.
3. **No bare except.** Catch specific exceptions. All domain errors are `BasefloError` with typed codes.
4. **Protocols over inheritance.** Use `typing.Protocol` for extensibility points (connectors, agents, actions).
5. **Immutability.** Artifacts are immutable. Models use frozen Pydantic configs where possible.
6. **Fail fast, fail loud.** No silent fallbacks. No stubbed returns. If something isn't implemented, raise a clear error.
7. **One responsibility per module.** Agents live in `app/agents/<name>/`. Each has: `agent.py`, `types.py`, `prompt.py`. Evidence lives in `app/evidence/`.
8. **Register, don't import.** Connectors and agents self-register in their `__init__.py`. No central import lists to maintain.
9. **Test what you ship.** Unit tests for deterministic code. Integration tests for agent runs (with mocked LLM). End-to-end tests for critical paths.
10. **No M2/M3 comments.** If code is not in v1, delete it. The codebase should reflect exactly what ships.

---

## v1 Scope

**In:**
- 6 connectors (Postgres, CSV, Excel, Google Sheets, Shopify, Stripe)
- 4 agents (Source, Reconciliation, Schema, Insight)
- Real-time sync (webhooks + polling)
- Entity reconciliation across sources
- Unified schema generation
- KPI computation against Postgres
- Email alerts and webhook actions
- Web app with saga viewer, admin tables, natural language queries
- Auth (magic link + Google OAuth)
- Multi-tenancy with RLS

**Out (post-v1):**
- BYO-DB mode
- Write-back to all connectors (v1: read-only for Postgres/CSV/Excel)
- Phone/SMS outbound
- Custom connector authoring SDK
- Advanced workflow builder
- EU region / data residency
