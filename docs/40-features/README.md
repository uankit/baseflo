# Per-Feature Design Docs

Status: living. Each feature listed in [`30-features.md`](../30-features.md) gets its own file here with HLD, LLD, design patterns applied, test plan, and error codes. New features are speccd here **before** implementation begins, per the rule in [`05-coding-rules.md`](../05-coding-rules.md) §11.

## Document Template

Every feature doc follows this structure:

1. **Overview** — what it does, who calls it, what it produces (1 paragraph).
2. **High-Level Design** — architectural view, data flow, where it sits.
3. **Low-Level Design** — module layout, key types, core logic.
4. **Design Patterns Applied** — which patterns from [`50-design-patterns.md`](../50-design-patterns.md), with rationale.
5. **Test Plan** — unit, integration, contract, fixtures.
6. **Error Codes** — `BF-AREA-NNN` codes with conditions and recovery.
7. **Dependencies** — other features this depends on.
8. **Milestone** — when it ships.

## Tier 1 — Engine Moat (M0–M1)

| Feature ID | Doc | Status |
|---|---|---|
| `IR-CORE` | [Schema IR](IR-CORE.md) | written |
| `CONN-FRAMEWORK` | [Connector Framework + Custom Connector Authoring](CONN-FRAMEWORK.md) | written |
| `AGENT-COL` | [ColumnClassifier](AGENT-COL.md) | written |
| `AGENT-ENT` | [EntityReconciler — the moat](AGENT-ENT.md) | written |
| `AGENT-PHYS` | [PhysicalSchemaArchitect](AGENT-PHYS.md) | written |
| `AGENT-COHE` | [CoherenceGate](AGENT-COHE.md) | written |
| `AGENT-CLAR` | [ClarificationAgent](AGENT-CLAR.md) | pending |
| `AGENT-CARD` | [CardinalityResolver](AGENT-CARD.md) | pending |
| `AGENT-CONS` | [ConstraintProposer](AGENT-CONS.md) | pending |
| `AGENT-KPI` | [KPIPlanner](AGENT-KPI.md) | pending |
| `AGENT-INT` | [IntentInterpreter](AGENT-INT.md) | pending |
| `AGENT-IMP` | [ImpactAnalyzer](AGENT-IMP.md) | pending |
| `AGENT-CHG` | [ChangePlanner](AGENT-CHG.md) | pending |

## Tier 2 — Engines, Surfaces, Runners, Infra (M0–M3)

| Feature | Doc | Status |
|---|---|---|
| `ENG-RUNTIME` (+ `REGISTRY`/`ROUTING`/`REPAIR`/`CACHE`/`TRACE`/`CONC`) | [Agent Runtime Infrastructure](ENG-RUNTIME.md) | written |
| `IR-DDL` | [DDL Compiler (Postgres)](IR-DDL.md) | written |
| `JOB-QUEUE` (+ `RETRY`/`SCHED`) + `SSE-PUBSUB` (+ `REPLAY`) | [Background Jobs + SSE Pub/Sub](JOBS-AND-SSE.md) | written |
| `ADMIN-GEN` (+ `LIST`/`DETAIL`/`MASK`) | [Admin UI Generator](ADMIN-GEN.md) | written |
| `REF-PANEL` (+ `PIPELINE`/`DIFF`/`ROLLBACK`) | [Refinement Pipeline + Versioning](REFINEMENT.md) | written |
| `ANA-*` (full analytics suite) | [Analytics & Intelligence Layer](ANALYTICS.md) | written |
| `DIG-COMPOSE` (+ `CADENCE`) | [Daily Digest](DIGEST.md) | written |
| `AUTH-SESSION` (+ `OAUTH`/`SSO`/`SCIM`) + `RBAC-ROLES` | [Sessions, OAuth, Roles](AUTH.md) | written |
| `SEC-KMS` + `SEC-TOKENS` + `SEC-PII-MASK` + `SEC-EXPORT` + `SEC-DELETE` + `AUDIT-CORE` | [Privacy & Security Primitives](SECURITY.md) | written |
| `SDK-TS` + `API-REST` | [TypeScript SDK + REST API](SDK-AND-API.md) | written |
| `DEP-HOSTED` + `DEP-BYO` + `DEP-LOCAL` (+ `SELFHOST`/`LICENSE`) | [Deployment Runners](DEPLOYMENT.md) | written |
| `OPS-LOGS` + `OPS-TRACES` + `OPS-METRICS` + `OPS-SENTRY` + `OPS-STATUS` | [Observability](OBSERVABILITY.md) | written |

## Tier 3 — Per-Connector Implementations (M1+)

| Feature | Doc | Status |
|---|---|---|
| `CONN-PG` | [Postgres Connector](CONN-PG.md) | written |
| `CONN-CSV` | [CSV / Excel Upload Connector](CONN-CSV.md) | written |
| `CONN-SHEETS` | [Google Sheets Connector](CONN-SHEETS.md) | written |
| `CONN-NOTION` | Notion Connector | M2; spec at implementation time |
| `CONN-SHOPIFY` | Shopify Connector | M2; spec at implementation time |
| `CONN-STRIPE` | Stripe Connector | M2; spec at implementation time |
| `CONN-MAILCHIMP` | Mailchimp Connector | M3; spec at implementation time |
| `CONN-HUBSPOT` / `ZOHO` / `SALESFORCE` / `AIRTABLE` / `MYSQL` / `MONGO` / `REST` | Per [`30-features.md`](../30-features.md) | M3+; spec at implementation time |

Per-connector docs after the v1 set follow the [`CONN-PG`](CONN-PG.md) template; they're spec'd at implementation time per the [`Connector Framework`](CONN-FRAMEWORK.md) protocol — adding one is a documented procedure, not a per-connector architectural decision.
