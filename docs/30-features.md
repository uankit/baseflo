# Baseflo — Feature Inventory

Status: living. Every feature listed here gets its own `docs/40-features/<feature>.md` with full HLD, LLD, design patterns, test plan, and error codes per `00-decisions.md` §9. New features are added here first, then specced under `40-features/`, then implemented.

Status legend: 🟢 ship in v1 (M0–M3) · 🟡 ship in v2 (M4–M6) · 🔵 v3+ · ⚫ deferred / unscheduled.

---

## A. Agentic Engine (the core)

### A.1 Specialist Agents (11)

| ID | Feature | Status | One-liner |
|---|---|---|---|
| AGENT-CLAR | `ClarificationAgent` | 🟢 | Preflight gate; max 3 blocking questions in plain business language. |
| AGENT-COL | `ColumnClassifier` | 🟢 | Per-column semantic typing with canonical names and labels. |
| AGENT-ENT | `EntityReconciler` | 🟢 | Cross-source entity unification — the moat. |
| AGENT-CARD | `CardinalityResolver` | 🟢 | 1..1 / 1..* / *..* + FK direction across reconciled entities. |
| AGENT-CONS | `ConstraintProposer` | 🟢 | Keys, uniqueness, status enums, money minor units, nullability. |
| AGENT-PHYS | `PhysicalSchemaArchitect` | 🟢 | Compose unified `SchemaIR` from prior outputs. |
| AGENT-KPI | `KPIPlanner` | 🟢 | Pick answerable KPIs with grain and assumptions. |
| AGENT-COHE | `CoherenceGate` | 🟢 | Internal terminal gate; emits typed `RepairRoute` on cross-cutting failure. |
| AGENT-INT | `IntentInterpreter` | 🟢 | Refinement intent parsing (no keyword matching). |
| AGENT-IMP | `ImpactAnalyzer` | 🟢 | What changes when a refinement applies. |
| AGENT-CHG | `ChangePlanner` | 🟢 | Concrete delta against parent IR. |

### A.2 Agent Runtime Infrastructure

| ID | Feature | Status | One-liner |
|---|---|---|---|
| ENG-RUNTIME | Pydantic AI Agent Runtime | 🟢 | Typed input/output, output validators, `ModelRetry`, model abstraction. |
| ENG-REGISTRY | Agent Registry | 🟢 | Single source of truth for agent specs; adding new agents is a one-file edit. |
| ENG-ROUTING | Model Routing (fast/balanced/reasoning) | 🟢 | Tier-based provider routing; OpenAI v1, Anthropic via env-flip. |
| ENG-REPAIR | Two-Level Repair Loop | 🟢 | Validator-driven `ModelRetry` + manager-driven gate-routed repairs. |
| ENG-CACHE | Agent Instance + Run Cache | 🟢 | LRU + TTL cache by `(name, schema, instructions_hash, model)`. |
| ENG-TRACE | Agent Run Telemetry | 🟢 | `agent_runs` + `agent_run_attempts` rows with real token usage. |
| ENG-CONC | Concurrency Manager | 🟢 | Per-tenant concurrency limits; graph-parallel where independent. |
| ENG-FLYWHEEL | Feedback Capture / Data Flywheel | 🟡 | `feedback_events` ingestion → curated knowledge updates. |

## B. Schema IR + Compilers

| ID | Feature | Status | One-liner |
|---|---|---|---|
| IR-CORE | Schema IR (canonical layer) | 🟢 | `TableIR`, `ColumnIR`, `RelationshipIR`, `IndexIR`; the contract between agents and compilers. |
| IR-DDL | DDL Compiler (Postgres) | 🟢 | Schema IR → safe Postgres DDL via SQLGlot. |
| IR-DDL-MULTI | DDL Compiler (multi-dialect) | 🔵 | MySQL, Snowflake adapters via dialect strategy pattern. |
| IR-DIFF | IR Diff & Migration Generator | 🟢 | Parent IR + change plan → child IR + alembic-style migration. |
| IR-VALIDATE | Cross-Cutting Validator | 🟢 | Deterministic post-compilation checks (KPI ↔ schema, FKs both-ended, etc.). |

## C. Connector Framework

| ID | Feature | Status | One-liner |
|---|---|---|---|
| CONN-FRAMEWORK | Connector Protocol & Plugin Framework | 🟢 | Adapter pattern; n built-ins + custom-connector extensibility. |
| CONN-AUTH | Custom Connector Authoring Spec | 🟢 | Documented spec + scaffolding; user-built connectors register at boot. |
| CONN-SCAFFOLD | `baseflo connector init` Scaffolding | 🟡 | CLI command to bootstrap a new connector module. |
| CONN-MARKETPLACE | Connector Marketplace | 🔵 | Community-built connectors with quality verification. |
| CONN-SANDBOX | Custom Connector Sandbox | 🟡 | Self-host: untrusted custom connectors run in restricted environment. |

### Per-connector implementations

| ID | Feature | Status | One-liner |
|---|---|---|---|
| CONN-PG | Postgres Connector | 🟢 | Direct connection string; introspect, sample, read, write. |
| CONN-CSV | CSV / Excel Upload | 🟢 | Drag-drop file upload; one-time import; refresh by re-upload. |
| CONN-SHEETS | Google Sheets Connector | 🟢 | OAuth; live read; periodic poll for sync. |
| CONN-NOTION | Notion Connector | 🟡 | OAuth; database-as-table read; write-back for notes/fields. |
| CONN-SHOPIFY | Shopify Connector | 🟡 | OAuth; products, customers, orders, inventory; webhook support. |
| CONN-STRIPE | Stripe Connector | 🟡 | OAuth; customers, charges, subscriptions, refunds; webhook support. |
| CONN-MAILCHIMP | Mailchimp Connector | 🟡 | API key; audiences, contacts, segments; segment write-back. |
| CONN-HUBSPOT | HubSpot Connector | 🔵 | OAuth; contacts, companies, deals; bidirectional. |
| CONN-ZOHO | Zoho Connector | 🔵 | OAuth; CRM module; bidirectional. |
| CONN-AIRTABLE | Airtable Connector | 🔵 | OAuth; bases as schemas; bidirectional. |
| CONN-SALESFORCE | Salesforce Connector | 🔵 | OAuth; objects; bidirectional. Enterprise pull. |
| CONN-REST | Generic REST/GraphQL Connector | 🟡 | User-configured endpoints; OpenAPI ingestion; manual schema mapping fallback. |
| CONN-MYSQL | MySQL Connector | 🔵 | Same shape as Postgres connector; alternate DB. |
| CONN-MONGO | MongoDB Connector | 🔵 | Document-shaped reconciliation. |

## D. Hosted Admin UI

| ID | Feature | Status | One-liner |
|---|---|---|---|
| ADMIN-GEN | Admin UI Generator | 🟢 | Renders CRUD UI from schema IR + agent labels; no per-project hand coding. |
| ADMIN-LIST | List View (TanStack Table) | 🟢 | Sort, filter, search, virtualized, source-badge per row. |
| ADMIN-DETAIL | Detail / Edit View | 🟢 | Full record with reconciliation panel + write-back to canonical source. |
| ADMIN-MASK | PII Masking + Reveal | 🟢 | Click-to-reveal logged in audit; masked by default per `ColumnClassifier`. |
| ADMIN-IMPORT | Inline Import (CSV) | 🟡 | Per-table CSV upload that respects schema constraints. |
| ADMIN-SHARE | Read-Only Share Links | 🟢 | Per-record or per-tab; expirable; passworded; audit-logged. |
| ADMIN-EXPORT | Export (CSV/SQL/JSON) | 🟢 | One-click full export; goes through job; signed URL. |
| ADMIN-VERSIONS | Version History UI | 🟢 | Browse refinement versions; compare; rollback. |
| ADMIN-BRAND | Custom Branding | 🟡 | Logo / color / domain per workspace (Pro and above). |

## E. Refinement (English-language Evolution)

| ID | Feature | Status | One-liner |
|---|---|---|---|
| REF-PANEL | Refinement Panel UI | 🟢 | Right-rail; English input; preview diff; apply. |
| REF-PIPELINE | Refinement Pipeline | 🟢 | `IntentInterpreter` → `ImpactAnalyzer` → `ChangePlanner` → versioning. |
| REF-DIFF | Plain-Language Diff Renderer | 🟢 | Translates change plan into user-readable bullets. |
| REF-ROLLBACK | Version Rollback | 🟢 | One-click restore of any prior version. |
| REF-COMPARE | Side-by-Side Version Compare | 🟡 | Visual schema/KPI diff between two versions. |

## F. Analytics & Intelligence

| ID | Feature | Status | One-liner |
|---|---|---|---|
| ANA-EVENTS | Schema-Aware Event Taxonomy | 🟢 | Generated from `KPIPlanner`'s output; events tied to schema. |
| ANA-INGEST | Event Ingestion API | 🟢 | Typed event ingestion through SDK; rate-limited; batched. |
| ANA-FUNNEL | Funnel Analysis | 🟢 | Auto-rendered from event taxonomy. |
| ANA-COHORT | Cohort Retention | 🟢 | Week-of-signup cohorts; per-source acquisition. |
| ANA-GEO | Geographic Distribution | 🟢 | When address columns exist. |
| ANA-TOPN | Top-N Lists | 🟢 | Top customers, products, regions, sources. |
| ANA-LAPSE | Lapsing / At-Risk Detection | 🟢 | Decay-pattern surfacing for any active-frequency entity. |
| ANA-ANOM | Anomaly Detection | 🟡 | Rolling-window threshold violations + agent-authored explanation. |

## G. Daily Digest

| ID | Feature | Status | One-liner |
|---|---|---|---|
| DIG-COMPOSE | Digest Composer | 🟢 | Daily summary email composed from analytics + anomalies. |
| DIG-CADENCE | Cadence & Subscriptions | 🟢 | Daily / weekly / off; per-user; per-channel (email / Slack / webhook). |
| DIG-SLACK | Slack Channel Delivery | 🟡 | Bot integration; inline buttons. |
| DIG-WEBHOOK | Webhook Delivery | 🟡 | Generic webhook for custom channels. |

## H. Auth, Roles, Audit

| ID | Feature | Status | One-liner |
|---|---|---|---|
| AUTH-SESSION | Sessions (Lucia) | 🟢 | Email magic link + password; session token rotation. |
| AUTH-OAUTH | OAuth Sign-In | 🟢 | Google / GitHub / Microsoft. |
| AUTH-SSO | SSO (OIDC + SAML) | 🟡 | M3+ enterprise; Okta, Azure AD. |
| AUTH-SCIM | SCIM Provisioning | 🟡 | M3+ enterprise. |
| RBAC-ROLES | Roles (Owner/Admin/Editor/Viewer) | 🟢 | Standard four-role model. |
| RBAC-CUSTOM | Custom Roles | 🟡 | M3+ enterprise; granular permissions. |
| RBAC-APPROVAL | Two-Person Approval | 🔵 | Destructive operations require co-sign. |
| AUDIT-CORE | Audit Log | 🟢 | Append-only `audit_events`; UI in Settings. |
| AUDIT-SIEM | SIEM Export | 🟡 | M3+ enterprise; Splunk/Datadog. |
| AUDIT-TAMPER | Tamper-Evident Chain | 🟡 | Cryptographic hash chain on audit rows; daily transparency receipt. |

## I. Privacy & Security

| ID | Feature | Status | One-liner |
|---|---|---|---|
| SEC-KMS | Per-Tenant KMS | 🟢 | AWS KMS; per-tenant DEK + KEK envelope. |
| SEC-TOKENS | Encrypted Connector Tokens | 🟢 | Token vault using tenant KMS. |
| SEC-PII-MASK | PII Field Masking | 🟢 | Default-masked in admin + log scrub. |
| SEC-PII-FREETEXT | PII Detection in Free-Text (Presidio) | 🔵 | Microsoft Presidio integration for unstructured PII. |
| SEC-EXPORT | One-Click Data Export | 🟢 | "Take everything and leave" — brand promise. |
| SEC-DELETE | One-Click Data Deletion | 🟢 | 30-day soft delete + hard delete; audit-logged. |
| SEC-ALLOWLIST | IP Allowlist | 🟡 | M3+ enterprise. |
| SEC-EU | EU Region | 🟡 | M3+ enterprise; data residency lock. |

## J. Deployment Modes

| ID | Feature | Status | One-liner |
|---|---|---|---|
| DEP-HOSTED | Hosted Cloud Runner | 🟢 | Multi-tenant Postgres on our AWS. |
| DEP-BYO | BYO-Database Runner | 🟢 | Customer's Postgres connection; engine on us. |
| DEP-SELFHOST | Self-Host Docker | 🟡 | Docker image + Helm chart; license server. |
| DEP-LOCAL | Local Dev (`baseflo dev`) | 🟢 | Docker compose on developer's machine. |
| DEP-LICENSE | License Activation Server | 🟡 | Self-host license validation + 30-day offline grace. |

## K. Background Jobs & Eventing

| ID | Feature | Status | One-liner |
|---|---|---|---|
| JOB-QUEUE | arq Job Queue | 🟢 | Redis-backed async work; idempotency keys. |
| JOB-RETRY | Exponential Backoff & DLQ | 🟢 | `failed_jobs` table for terminal failures. |
| JOB-SCHED | Scheduled Jobs | 🟢 | Daily digest, periodic connector sync. |
| SSE-PUBSUB | SSE via Postgres LISTEN/NOTIFY | 🟢 | Multi-instance-safe pub/sub for live progress. |
| SSE-REPLAY | SSE Event Replay | 🟢 | Persisted; client can resume from sequence number. |

## L. SDK & Public API

| ID | Feature | Status | One-liner |
|---|---|---|---|
| SDK-TS | TypeScript SDK Codegen | 🟢 | Generated from schema IR; `@baseflo/sdk`; tiny runtime. |
| SDK-PY | Python SDK | 🟡 | Same generation pipeline. |
| API-REST | REST API (`/api/v1/...`) | 🟢 | Generated OpenAPI; idempotency-key support. |
| API-GRAPHQL | GraphQL API | 🔵 | Optional surface; auto-derived from schema IR. |
| API-WEBHOOK | Outbound Webhooks | 🟡 | Subscribe to events; signed payloads. |

## M. AI Agent Surfaces (M3+)

| ID | Feature | Status | One-liner |
|---|---|---|---|
| MCP-SERVER | MCP Server | 🟡 | Model-Context-Protocol server so Claude/Cursor can read/write through us. |
| AI-COPILOT | In-product AI Copilot | 🔵 | "Show me lapsing customers" → executes safely. |

## N. CLI (Developer Surface)

| ID | Feature | Status | One-liner |
|---|---|---|---|
| CLI-INIT | `baseflo init` | 🟡 | Bootstrap a project from a config file. |
| CLI-CONNECT | `baseflo connect <source>` | 🟡 | OAuth flow / token entry from terminal. |
| CLI-DEPLOY | `baseflo deploy` | 🟡 | Push project config + custom connectors to hosted/self-host. |
| CLI-DEV | `baseflo dev` | 🟡 | Local docker-compose engine + UI. |
| CLI-TESTDB | `baseflo testdb` | 🔵 | Synthetic data seeding; requires `BehaviorPlanner` add-back. |
| CLI-CONN-INIT | `baseflo connector init <name>` | 🟡 | Scaffold a custom connector module. |
| CLI-CONN-PUBLISH | `baseflo connector publish` | 🔵 | Publish to marketplace (M5+). |

## O. Operations

| ID | Feature | Status | One-liner |
|---|---|---|---|
| OPS-LOGS | Structured Logs (structlog) | 🟢 | Per-tenant context propagation. |
| OPS-TRACES | OpenTelemetry Traces | 🟢 | Spans on every API call, agent run, connector hit. |
| OPS-METRICS | Prometheus Metrics | 🟢 | Latency, queue depth, repair rates, token usage. |
| OPS-SENTRY | Sentry Integration | 🟢 | Unhandled exceptions. |
| OPS-STATUS | Status Page | 🟢 | `status.baseflo.com` real-time. |
| OPS-COST | Per-Tenant Cost Dashboard | 🟡 | Token usage roll-up; profitability per customer. |

## P. Web Application (Meta-App Shell)

The hosted SaaS web app at `app.baseflo.com`. Production grade per `00-decisions.md` §10. Distinct from `ADMIN-GEN` (auto-generated per-tenant admin) — the WEB-APP is the meta-app shell that *contains* the ADMIN-GEN workspace as one of its panes. Full spec in [`40-features/WEB-APP.md`](40-features/WEB-APP.md).

| ID | Feature | Status | One-liner |
|---|---|---|---|
| WEB-SHELL | App Shell (router, layouts, top bar, side nav, panel system) | 🟢 | TanStack Router file-based routes; AppShell / AuthShell / WorkspaceShell / ShareShell / SettingsShell. |
| WEB-AUTH | Auth UX (sign-in, sign-up, magic-link, OAuth, password reset) | 🟢 | Frontend for `AUTH-SESSION` + `AUTH-OAUTH`; protected routes; session refresh. |
| WEB-ONBOARD | First-Run Onboarding (ICP-A dev path + ICP-B SMB `/start` lane) | 🟢 | Decides org/workspace name, deployment mode, first project, and routes to connect-first or describe-first. |
| WEB-PROJECT | Project List + Create + Settings | 🟢 | Recent projects, create new, archive, deployment-mode badge, version selector. |
| WEB-CONNECT | Connector Hub (install, status, reconnect, revoke, OAuth callback) | 🟢 | Per-connector cards, OAuth dance, API-key form, sample-data preview, last-sync indicator. |
| WEB-SAGA | Generation Saga Viewer (live SSE stream of agent runs) | 🟢 | Stage rail, agent activity, validation gates, repair-loop flash, workspace.ready CTA. |
| WEB-WORKSPACE | Workspace Shell (hosts ADMIN-GEN tabs + analytics + digest) | 🟢 | Top bar, schema-driven side nav (`ADMIN-GEN`), main pane router, right refine rail, version selector. |
| WEB-REFINE | Refinement Panel UI | 🟢 | English composer, plan preview, apply, version-switch, rollback affordance. (Frontend for `REF-PANEL`.) |
| WEB-EXPORT | Export Center | 🟢 | Format picker (CSV/SQL/JSON/full), job progress, signed-URL retrieval, download history. |
| WEB-SHARE | Read-Only Share Page (`/s/<token>`) | 🟢 | Polished public summary; redacts traces, audit, PII; expirable; password-gated. |
| WEB-SETTINGS | Settings (Org, Team, Billing, Audit, API Keys, Custom Domain, Deployment Mode, SSO M3+) | 🟢 | Tabs map 1:1 to control-plane subsystems; gates writes via RBAC. |
| WEB-DESIGN-SYSTEM | `@baseflo/ui` Component Library + Tokens | 🟢 | Radix primitives wrapped with brand tokens; semantic CSS variables; Tailwind preset; lucide-react icons. |
| WEB-ERROR-SYSTEM | Centralized Frontend Error Registry (`BF-WEB-NNN` + backend mapping) | 🟢 | Error normalizer, callout/toast/dialog renderers, unknown-code fallback. |
| WEB-A11Y | WCAG 2.1 AA Accessibility | 🟢 | Keyboard navigation, focus management, ARIA, contrast tokens, screen-reader announcements for SSE. |
| WEB-MARKETING | Marketing site (`baseflo.com`) | 🟡 | Static landing; ships separately on Cloudflare Pages; not in alpha web-app scope but tracked here. |
| WEB-DESKTOP | Desktop Wrapper (Tauri v2) | 🔵 | Same web app, native shell. M5+. |

## Total v1 (🟢) feature count

58 features ship in v1 milestones M0–M3 (44 prior + 14 added in §P per `00-decisions.md` §10). Each gets a `docs/40-features/<feature-id>.md` with HLD, LLD, design patterns, test plan, and error codes per `00-decisions.md` §9. The WEB-APP sub-IDs are documented together in [`40-features/WEB-APP.md`](40-features/WEB-APP.md).
