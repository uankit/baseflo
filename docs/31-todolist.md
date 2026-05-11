# Baseflo — Master Build Todolist

Status: living. Grouped by milestone. Each task points to the feature ID in `30-features.md` and (where applicable) the per-feature doc in `40-features/`.

Rule: a task is not "done" until tests are green, docs are updated, and a real `BF-AREA-NNN` error code exists for every failure path.

Status legend: ⬜ pending · 🟦 in progress · ✅ done · 🚧 blocked.

---

## M0 — Foundation Reset (week 1-2)

Goal: clean slate engine + control plane + minimal end-to-end loop. No connector real, no admin UI yet. Proves the pipeline plumbing.

### M0.1 — Codebase cleanup
- ⬜ Delete `business.py:64-72` keyword vertical detection (per audit).
- ⬜ Delete `_cents`/`status` keyword scoring in `analytics/kpis.py`.
- ⬜ Delete offline fixtures in `graph.py:449-715`.
- ⬜ Delete `pipeline.py:393-459` preflight keyword heuristic.
- ⬜ Delete substring privacy/compliance/refinement heuristics.
- ⬜ Delete `dict[str, Any]` escape hatches in `schemas/artifacts.py`; replace with strongly-typed Pydantic models.
- ⬜ Delete KPI Trust Cards / Critic / Simulation / Scenario as user surfaces (engine pieces are repurposed).
- ⬜ Delete hardcoded `gpt-5.2` placeholder; wire `BASEFLO_AGENT_*_MODEL_NAME` env vars.
- ⬜ Delete unused specialist agent wrappers in `agents/specialists/`.

### M0.2 — Project structure
- ⬜ Create top-level `connectors/`, `sdk/ts/`, `cli/`, `infra/` directories.
- ⬜ Move docs already written into `docs/` (already done).
- ⬜ Update `pyproject.toml` to declare new dependencies (arq, structlog, opentelemetry, etc.).
- ⬜ Configure `import-linter` to enforce layer boundaries per `05-coding-rules.md` §3.

### M0.3 — Control plane DB
- ⬜ Write migration `20260507_0001_init_organizations_users_memberships.py` (per `04-database-schema.md` §10).
- ⬜ Write migration `20260507_0002_workspaces_projects_versions.py`.
- ⬜ Write migration `20260507_0003_connectors_tokens.py`.
- ⬜ Write migration `20260507_0004_conversations_events.py`.
- ⬜ Write migration `20260507_0005_generation_jobs_steps_agents.py`.
- ⬜ Write migration `20260507_0006_refinements_exports_shares_feedback.py`.
- ⬜ Write migration `20260507_0007_audit_digests_apikeys_billing.py`.
- ⬜ Write migration `20260507_0008_system_health_failed_jobs.py`.
- ⬜ Write migration `20260507_0009_rls_policies.py`.
- ⬜ Write migration `20260507_0010_indexes.py`.
- ⬜ Tests: every migration has up/down; CI runs all migrations against an empty DB before merge.

### M0.4 — Agent runtime
- ⬜ Refactor `app/agents/runtime.py`: make `run_pydantic_ai` actually `async`; remove `asyncio.run(...)`.
- ⬜ Wire `run_structured` repair loop into the live pipeline.
- ⬜ Capture real `usage` from Pydantic AI run results (replace zeroed counts).
- ⬜ Implement `app/agents/registry.py` with `register_agent` decorator.
- ⬜ Update `model_routing.py` to current 11-agent table (per `03-agentic-workflow.md` §6).
- ⬜ Implement bounded LRU + 1h TTL cache for agent instances.
- ⬜ Tests: `TestModel`/`FunctionModel` happy-path + repair-path for runtime; never call real provider in unit tests.

### M0.5 — Job queue + SSE
- ⬜ Provision Redis (local docker-compose for dev).
- ⬜ Set up `arq` worker process; idempotency-key infrastructure.
- ⬜ Build SSE pub/sub via Postgres `LISTEN/NOTIFY`.
- ⬜ Tests: emit → persist → notify → SSE client receives in real time.
- ⬜ Tests: client resume from last sequence number.

### M0.6 — Move pipeline off API thread
- ⬜ Refactor `services/conversation.py`: enqueue generation job; return `202 Accepted`.
- ⬜ Worker picks up job, runs through agent graph, emits SSE events live.
- ⬜ Workspace ready event fires only after `CoherenceGate` passes.
- ⬜ Tests: API returns 202 immediately; client receives staged events; worker process runs the pipeline.

### M0.7 — End-to-end smoke
- ⬜ Single integration test: POST `/api/v1/conversations/messages` with a description → SSE shows stages → workspace doc returned.
- ⬜ Use `TestModel` so no real provider is called.
- ⬜ Stage labels match the production stage list.

**M0 done when:** the pipeline runs end-to-end on `TestModel`, control plane is fully migrated, no audit-flagged code remains, layer boundaries are enforced, and CI is green.

---

## M1 — Single-Source Magic Moment (week 3-5)

Goal: one connected source (Postgres or CSV) → unified IR → admin UI → analytics. Proves the friend's case.

### M1.1 — Schema IR + DDL compiler
- ⬜ Implement `app/engines/schema/ir.py` with strict typed models per `01-architecture.md` §3.3.
- ⬜ Implement `app/engines/schema/ddl_postgres.py` (rename from existing `designer.py`); SQLGlot integration.
- ⬜ Tests: round-trip IR → DDL → parse-back gives equivalent IR.
- ⬜ Tests: invalid IR raises `BF-SCHEMA-NNN`.

### M1.2 — Connector framework + Postgres + CSV
- ⬜ Implement `app/connectors/base.py` (Connector Protocol).
- ⬜ Implement `app/connectors/registry.py` (plugin discovery at startup).
- ⬜ Implement `app/connectors/postgres/` with full protocol coverage.
- ⬜ Implement `app/connectors/csv/` with file-upload + sample-rows.
- ⬜ Tests: per-connector contract tests; reject malformed credentials with typed errors.

### M1.3 — Core agents (single-source path)
- ⬜ `ClarificationAgent`: prompt + output validator + tests.
- ⬜ `ColumnClassifier`: prompt + output validator + tests against fixture columns.
- ⬜ `EntityReconciler`: single-source path (no cross-source reconciliation yet).
- ⬜ `CardinalityResolver`: full implementation.
- ⬜ `ConstraintProposer`: full implementation.
- ⬜ `PhysicalSchemaArchitect`: full implementation.
- ⬜ `KPIPlanner`: full implementation; KPIs reference real schema columns.
- ⬜ `CoherenceGate`: cross-cutting checks; emits typed `RepairRoute`.
- ⬜ All tests use `TestModel`; integration test exercises full graph with fixtures.

### M1.4 — Admin UI generator
- ⬜ Build `app/services/admin_ui_spec.py`: schema IR → UI spec.
- ⬜ Client: build generic List view (TanStack Table).
- ⬜ Client: build generic Detail/Edit view (forms generated from `ColumnIR`).
- ⬜ Client: PII masking + click-to-reveal (audit-logged).
- ⬜ Tests: schema with 3 tables produces 3 navigable tabs with working CRUD.

### M1.5 — Analytics layer (basic)
- ⬜ Implement event-taxonomy generation from `KPIPlanner` output.
- ⬜ Implement deterministic chart-spec emission (KPI shape → chart type).
- ⬜ Implement `KPI SQL execution` against DuckDB (replace text-only SQLite shim).
- ⬜ Client: build Analytics tab with charts, top-N, lapsing list.

### M1.6 — Daily digest (basic)
- ⬜ Implement digest composer.
- ⬜ Worker job runs at user-local 7am; sends via Resend or Postmark.
- ⬜ Email template: text + minimal HTML.
- ⬜ Tests: integration test with frozen time + asserted email body.

### M1.7 — TypeScript SDK codegen
- ⬜ OpenAPI generation from FastAPI.
- ⬜ Custom codegen step: schema IR → typed entity methods (`baseflo.products.list()`, etc.).
- ⬜ Publish `@baseflo/sdk` to npm.
- ⬜ Tests: generated SDK compiles with strict TypeScript; basic CRUD works against test API.

### M1.8 — Auth + tenant scoping
- ⬜ Implement Lucia-style sessions; magic-link email; password fallback.
- ⬜ OAuth (Google/GitHub) sign-in.
- ⬜ Per-request `tenant_id` context var; RLS enforcement in repositories.
- ⬜ Tests: cross-tenant queries impossible; RLS verified.

**M1 done when:** the friend's case works end-to-end. They sign up, describe their business, see a generated admin in 90s, paste the SDK into Cursor, and their frontend reads from the API.

---

## M2 — Multi-Source Unification (week 6-8)

Goal: connect 2+ sources → reconciled unified schema → unified Customers tab. Proves the moat.

### M2.1 — Add 2 more connectors
- ⬜ `Google Sheets` connector (OAuth, periodic poll).
- ⬜ Choose one of: `Shopify` or `Stripe` (pick based on validation conversations).
- ⬜ Per-connector tests against sandbox accounts.

### M2.2 — Multi-source reconciliation
- ⬜ Upgrade `EntityReconciler` to full cross-source path.
- ⬜ Implement conflict-resolution policies + authoritative-source assignment.
- ⬜ Implement write-back routing (edits in admin write to the canonical source).
- ⬜ Tests: 3 sources with overlapping customer data → unified count is correct; edits write back to correct source.

### M2.3 — Refinement loop
- ⬜ `IntentInterpreter` + `ImpactAnalyzer` + `ChangePlanner`.
- ⬜ Plain-language diff renderer.
- ⬜ Child version creation; immutable; rollback.
- ⬜ Tests: refinement requests "add wishlists" produces correct child IR + admin updates.

### M2.4 — Source health + reconnect
- ⬜ Per-connector health monitoring.
- ⬜ Connector token expiry detection + reconnect prompt.
- ⬜ "Conflict log" UI surfacing reconciliation decisions with override.

### M2.5 — Sharing + exports
- ⬜ Read-only share link generation; expiring tokens.
- ⬜ Full data export (CSV + SQL + JSON); signed URL; 24h expiry.
- ⬜ Tests: export of full project produces re-importable artifacts.

**M2 done when:** an SMB user with Excel + Stripe + (Shopify or Sheets) sees the unified Customers moment and edits write back to the right source.

---

## M3 — BYO-DB + Privacy Tier + More Connectors (week 9-12)

Goal: privacy-conscious customers can use Baseflo without their data living on us. SSO foundations.

### M3.1 — BYO Database mode
- ⬜ Implement `BYODataPlane` adapter.
- ⬜ Settings UI: switch deployment mode; test connection.
- ⬜ Tenant-data DDL emission to customer DB.
- ⬜ Tests: BYO-DB project works end-to-end against external Postgres.

### M3.2 — KMS + per-tenant encryption
- ⬜ Per-tenant DEK + KEK envelope encryption.
- ⬜ Connector token encryption with tenant KEK.
- ⬜ Audit log scrubbing for PII fields per `ColumnClassifier`.

### M3.3 — Audit log surfaces
- ⬜ UI for audit log: filter, export.
- ⬜ Per-org retention policy (1y default; 7y enterprise).

### M3.4 — Add 2-3 more connectors
- ⬜ `Notion`, `Mailchimp`, plus whichever of Shopify/Stripe wasn't built in M2.
- ⬜ Webhook subscription for connectors that support it.

### M3.5 — Custom connector authoring path
- ⬜ Document the Connector Protocol fully (in `40-features/CONN-FRAMEWORK.md`).
- ⬜ Reference example: a "Toy CRM" connector against a fixture API.
- ⬜ Self-host customers can register a custom module at boot.

### M3.6 — SSO scaffolding
- ⬜ OIDC flow (Google Workspace, Microsoft Entra ID).
- ⬜ Settings UI for IdP configuration; test mode before flip-to-required.

**M3 done when:** a privacy-conscious customer can connect their own Postgres, see the same product, and pass a basic security review.

---

## M4-M6 — Self-Host, Enterprise Features (quarter 2)

- Self-Host Docker image + Helm chart.
- License-key activation server.
- SAML 2.0; SCIM provisioning.
- Custom roles + two-person approval.
- SIEM export (Splunk, Datadog).
- IP allowlists.
- Tamper-evident audit chain.
- White-label / agency mode.
- EU region.
- HubSpot, Zoho, Salesforce connectors (one per quarter).
- MCP server (AI tools read/write through us).
- SOC 2 Type 1.

## M7+ — Marketplace, AI Copilot, More (quarter 3+)

- Connector marketplace (community-built).
- In-product AI Copilot (safe natural-language commands).
- Two-way sync v2 (live, not poll).
- Automated PII detection in free-text via Presidio.
- GraphQL API surface.
- Mobile companion (read-only).
- `BehaviorPlanner` returns for `baseflo testdb` and demo-data flows.
- SOC 2 Type 2; HIPAA BAA path.

---

## Cross-Cutting Tasks (always running)

- ⬜ Each feature has a `docs/40-features/<feature-id>.md` written **before** implementation begins.
- ⬜ Each error path has a `BF-AREA-NNN` code documented in the corresponding feature doc.
- ⬜ Each agent has prompt + output validator + tests using `TestModel` before production wiring.
- ⬜ Code review checklist per `05-coding-rules.md` §9 enforced on every PR.
- ⬜ Coverage thresholds maintained (engines/agents 90%, repositories 85%, services 80%).
- ⬜ Migrations always ship with downgrades; tested in CI.
- ⬜ Status page kept current; incidents documented post-mortem within 48h.
- ⬜ Validation conversations: 1-2 per week; insights folded into roadmap weekly.

---

## Definition of "Shipped" (per milestone)

A milestone is shipped when:
1. All in-scope features have green tests.
2. All in-scope features have docs in `40-features/`.
3. End-to-end demo for the milestone runs flawlessly on a fresh tenant.
4. At least 3 real customers have used the milestone's flow.
5. Cost per generation is within target (`02-tech-stack.md` §Cost Posture).
6. Status page shows >99% uptime for the prior 7 days.
7. No P1 incidents open.
8. Founder records the next milestone's 90-second demo.

---

## Post-Alpha Backlog — pick up after first 10 design partners

Cut from alpha scope after the auth pipeline landed (2026-05-07). Each entry: what it is, why we deferred, the trigger that should pull it back in.

### Auth & identity

- ⬜ **GitHub + Microsoft user-sign-in OAuth.** Spec: `40-features/AUTH.md` §3.4. Why deferred: Google + magic-link cover ≥95% of design-partner audience; adding two providers triples QA surface for marginal user gain. Trigger: first design partner asks for it OR enterprise prospect requires SSO.
- ⬜ **API-key issuance routes** (`POST /auth/api-keys`, `DELETE /auth/api-keys/:id`). The validation surface for inbound `Authorization: Bearer baseflo_…` already exists in `AuthMiddleware`. Why deferred: design partners use the UI; programmatic API access is M1+. Trigger: SDK or CLI lands and needs server-side issuance.
- ⬜ **CSRF protection on state-mutating routes.** Why deferred: SameSite=Lax on the session cookie blocks the worst CSRF surface; full CSRF tokens add friction for low residual risk. Trigger: external pen-test OR pre-SOC-2.
- ⬜ **DEK rotation cron (monthly).** Per `40-features/SECURITY.md` §3.3. Why deferred: per-blob DEK + KEK is sufficient for M0; monthly rotation is defense-in-depth. Trigger: first paying customer OR SOC 2 prep.
- ⬜ **AWS KMS impl** (`AwsKmsClient` is a stub today). Why deferred: LocalKMS works for self-host + single-region hosted; AWS KMS lights up when the hosted plane provisions on AWS. Trigger: hosted Cloud deployment to AWS.
- ⬜ **PII reveal endpoint + 30-second auto-remask.** Per `40-features/SECURITY.md` §3.4. Why deferred: no admin UI yet — nothing renders PII to a user. Trigger: admin UI row-detail views ship.
- ⬜ **Audit-event chain-hashing.** M3+ per spec. Trigger: enterprise customer asks for tamper-evident audit log.

### Connectors

- ⬜ **Google Sheets OAuth user-install route + `TokenVault.put` wiring.** Auth helpers exist (`app/connectors/google_sheets/auth.py`); `/api/v1/oauth/google_sheets/{install,callback}` route is not yet built. Why deferred: separate slice — needs new route + `redirect_to` + spreadsheet-id capture in install URL. Trigger: design partner needs Sheets sync. **~4 hours.**
- ⬜ **Stripe restricted-key onboarding UI flow.** Today the connector accepts an API key via metadata — fine for founder-driven first installs, friction for self-serve. Trigger: first self-serve signup attempt.

### UI / front-end

- ⬜ **Thin admin UI for design partners** (Next.js, Linear-density, throwaway). Screens: connector setup wizard, schema browser, KPI builder, dashboard, write-back review queue, sign-in (magic-link + Google). Trigger: auth pipeline merged ✅ + first 3 design partners lined up. **This is the immediate next slice.**

### Operations / CI

- ⬜ **CI workflow** that runs migrations + integration tests on every PR. Today `pytest -m integration` is gated by a local Postgres. Trigger: second engineer joins OR first non-trivial regression slips past local checks.
- ⬜ **Status page + uptime monitoring** for the hosted plane. Trigger: hosted deployment.
- ⬜ **DR / backup playbook.** Trigger: first paying customer.

### Privacy / compliance

- ⬜ **One-click full data export** (`/exports`). Per `40-features/SECURITY.md` §3.5. Route skeleton exists; the SQL+CSV+JSON packagers are unwritten. Trigger: first deletion request OR EU customer.
- ⬜ **Soft-then-hard project deletion + 30-day scheduler.** Per §3.6. Trigger: same as above.
- ⬜ **EU data region.** Trigger: first EU enterprise customer (locked at start of M3 per `00-decisions.md` §8).
- ⬜ **SOC 2 prep.** Trigger: first paying customer (locked per §8).
