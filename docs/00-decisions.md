# Baseflo — Decisions Log

Status: living document. Every change requires co-founder sign-off and a dated entry in the Changelog at the bottom.

This file is the single source of truth for *what we decided and why*. Every other document in `docs/` defers to this one.

---

## 1. Brand

- **Name:** `Baseflo` (no `w`). All assets, code namespaces, package names (`@baseflo/sdk`, `baseflo-cli`, `app.baseflo.com`), and copy use this spelling.
- **Tagline (working):** *"Run your business from one place. Connected to what you already use."*
- **Category we operate in:** *business operations layer*. Not "AI app builder," not "backend tool," not "data warehouse."

## 2. Product Frame

- **What we are:** the agentic operations layer that connects existing business tools, reconciles them into a single coherent data model, and gives the customer a hosted admin panel + APIs + intelligence built from their actual data.
- **What we are not:** a code generator, a backend-from-prompt tool, a CRM template catalog, a no-code form builder, a generic LLM wrapper.
- **Three-stack moat:**
  1. **Universal ingestion** of the tools customers already use (Excel, Notion, Postgres, Shopify, Stripe, Mailchimp, Zoho, Twilio, custom DBs).
  2. **Agentic semantic understanding** — multi-agent decomposition where sub-agents act like data architects: column classification, entity reconciliation across sources, cardinality resolution, constraint proposing, KPI selection.
  3. **Hosted intelligence + management surface** — admin UI, schema-aware behavioral analytics, daily digest, refinement-by-conversation.

## 3. Privacy & Data Residency (locked, changeable)

- **v1 hosted-cloud default: Option B — encrypted at rest, per-tenant KMS, audit-logged, one-click deletable.** Standard SaaS practice (Linear, Notion, Stripe, Shopify itself). Fast, full intelligence, smallest engineering surface, sufficient privacy claim for the SMB and indie-dev ICPs.
- **Day-one architectural options also shipped:**
  - **BYO-DB mode:** customer points us at their Postgres (Neon, Supabase, RDS, on-prem). The engine runs on our infra; the data lives in their database; we hold encrypted connector tokens but never persist customer rows.
  - **Self-Host Docker:** our Docker image runs entirely on customer infra; we never touch their data. License + support revenue model.
- **Migration path to Option C (full passthrough + derived-only cache):** architecturally permitted, not built in v1. The data-plane interface is designed so a future runner can swap "store rows" for "live-query connector" without rewriting the engine.
- **Constraint:** no decision in v1 may foreclose the move to Option C. If a feature requires permanent PII storage to function, we revisit before shipping.

## 4. Agentic Bar — the "no LLM wrapper" rule

This rule is enforced in code review.

### Agents own all semantic decisions
- Entity meaning (what is a customer, an order, a SKU)
- Relationships and cardinality across sources
- What is PII, status, money, identity, temporal
- Refinement intent ("add wishlists" → which schema deltas?)
- Multi-source entity reconciliation (Shopify customer ≡ Excel contact?)
- KPI selection, dashboard composition, behavioral plans
- Critic-level review of the final unified system

### Deterministic compilers own only structural verification and emission
- Schema-IR-to-Postgres-DDL emission
- SQL parsing and dialect translation via SQLGlot
- FK target existence checks
- Cardinality form normalization (`1..*` → typed enum)
- Audit-log writes, idempotency keys, hash checkpoints
- File/CSV emission, manifest assembly

### Forbidden
- Keyword-driven business detection (`if "saas" in prompt`)
- Substring vertical templates (`if column.endswith("_cents")`)
- Fallback heuristic generators that "patch" agent output silently
- Any code that makes a semantic decision without an agent's typed output backing it
- `dict[str, Any]` in agent output schemas (every agent output must be a strongly-typed Pydantic model)

### Multi-agent decomposition is required
- One agent per architect's task. Never one big agent doing five jobs.
- Each sub-agent has typed input, typed output, narrow purpose, isolatable test.
- Composition is via an explicit graph (Pydantic Graph), not lambda closures or `if`-chains in a runner.

## 5. Deployment Modes (locked, day one)

| Mode | Purpose | Data location | Engine location |
|---|---|---|---|
| **Hosted Cloud** | Default for SMB and indie devs. Fastest signup. | Our managed Postgres, encrypted, per-tenant KMS. | Our infra. |
| **BYO Database** | Mid-market & privacy-conscious customers. | Customer's Postgres (Neon/Supabase/RDS/on-prem). | Our infra. |
| **Self-Host Docker** | Enterprise / regulated industries. | Customer infra. | Customer infra. |
| **Local Dev** | Developer experience: `baseflo dev`. | Local Postgres in container. | Local. |

One engine codebase, four runners. The data plane is an interface; the agent and surface code is identical across modes.

## 6. Naming & Code Conventions

- Python packages and code use `baseflo` (matches brand).
- TypeScript packages: `@baseflo/contracts`, `@baseflo/sdk`, `@baseflo/api-client`, `@baseflo/ui`.
- CLI binary: `baseflo` (Go single-binary).
- API: `app.baseflo.com/api/v1/...`
- Error codes: `BF-AREA-NNN` (existing convention; keep).

## 7. Existing Code: Keep / Delete / Add

### Keep
- Pydantic AI agent runtime (`server/app/agents/runtime.py`) with the cache and repair-loop scaffold.
- Schema IR (`server/app/engines/schema/ir.py`).
- DDL compiler (`server/app/engines/schema/designer.py`) including the legitimate `_IDENTIFIER` regex for SQL identifier safety.
- Contracts package (`client/packages/contracts`).
- Error registry and `BF-AREA-NNN` system.
- Alembic migrations base.
- Agent runs telemetry tables.
- Client monorepo skeleton (Turbo + pnpm + workspace dependencies).

### Delete
- Keyword vertical detection in `server/app/agents/business.py:64–72`.
- `_cents` / `status` substring KPI scoring in `server/app/engines/analytics/kpis.py`.
- Offline schema/dataset fixtures in `server/app/agents/graph.py:449–715`.
- Preflight clarification keyword heuristic in `server/app/orchestration/pipeline.py:393–459`.
- Substring privacy/compliance/refinement heuristics in `server/app/engines/{privacy,compliance,refinement}/`.
- `dict[str, Any]` escape hatches in `server/app/schemas/artifacts.py`.
- KPI Trust Cards / Critic / Simulation as user-facing surfaces (the underlying engine work is repurposed for behavioral analytics).
- Hardcoded `gpt-5.2` placeholder model defaults in `server/app/core/config.py`.
- Unused specialist agent wrappers in `server/app/agents/specialists/`.

### Add (new subsystems)
- Connector framework (per-connector adapter plugins).
- Multi-source schema unification subgraph (the moat).
- Deployment-mode abstraction (data plane interface, four runners).
- Hosted admin UI generated from schema IR.
- Control-plane DB schema: orgs, users, workspaces, projects, connectors, connector_tokens, runs, audit_logs.
- Background job queue (`arq` on Redis).
- SSE pub/sub via Postgres `LISTEN/NOTIFY`.
- Go single-binary CLI (`baseflo init`, `baseflo connect`, `baseflo testdb`, `baseflo deploy`, `baseflo dev`).
- TypeScript SDK codegen from schema IR.
- Real `ClarificationAgent` and `RefinementAgent` (currently declared but unwired).
- MCP server surface for AI agents to read/write through us.

## 7B. LLM Provider (locked, switchable)

- **v1 primary: OpenAI** — `gpt-4.1-mini` for `fast`, `gpt-4.1` for `balanced`, `o3-mini` for `reasoning`.
- **Reason for v1:** founder has OpenAI account; Anthropic provisioning pending.
- **Switch trigger:** when Anthropic account is provisioned, env-flip to `claude-haiku-4-5` / `claude-sonnet-4-6` / `claude-opus-4-7`. No code change. Re-run agent eval harness to confirm quality non-regression before flipping production.
- **Code rule:** no agent file imports `openai` or `anthropic`. Pydantic AI is the only provider boundary.

## 8. Open Decisions (deferred — explicit, not buried)

These are not blocking; they will be locked at the noted milestone.

- **v1 connector list:** recommendation is Postgres + CSV/Excel + Shopify, then Stripe + Mailchimp by end of M1. Locked at start of M1.
- **Pricing values:** locked after first 10 validation conversations.
- **SOC2 timeline:** locked after first paying customer.
- **MCP server priority:** locked at start of M2 (after core engine).
- **EU data region:** locked at start of M3.

## 9. Working Norms (enforced)

- TDD-first: failing test → implementation → green test → refactor. No PR is reviewable without tests written first.
- No assumption-driven coding. When unclear, pause and ask.
- No regex / keyword heuristic in semantic code paths. Period.
- Every agent has a typed Pydantic output schema. Period.
- Every feature has an HLD, LLD, design-pattern note, error codes, and test plan in `docs/40-features/<feature>.md` before implementation begins.
- Industry-grade or it doesn't ship. No "it works on my machine" merges.

## 10. Web Application in Alpha Scope (locked 2026-05-07)

**Reversal of prior alpha-cut decision.** The original `ALPHA-TEST-PLAN.md` §1 + §7 scoped alpha as CLI/SDK only with web UI in "next milestone." Reversed: **the hosted web application (`app.baseflo.com`) is in alpha scope and ships at production grade — not a wrapper, not a stub, not a founder-dogfood console.**

**Why:** The CLI/SDK alpha cannot validate ICP-B (SMB) — the canonical 90-second demo (`20-gtm.md` §5) requires a visual workspace. ICP-A devs also expect a hosted dashboard alongside the CLI for project management and connector status. Shipping CLI-only delays both ICP validations and the public-launch milestone (`20-gtm.md` §9.2). Building the UI now, alongside the engine, lets the milestones land together.

**What this means concretely:**

- A new feature group **`WEB-APP`** (with sub-IDs `WEB-SHELL`, `WEB-AUTH`, `WEB-ONBOARD`, `WEB-PROJECT`, `WEB-CONNECT`, `WEB-SAGA`, `WEB-WORKSPACE`, `WEB-REFINE`, `WEB-EXPORT`, `WEB-SHARE`, `WEB-SETTINGS`, `WEB-DESIGN-SYSTEM`, `WEB-ERROR-SYSTEM`, `WEB-A11Y`) is added to `30-features.md` §P. The hosted web app is the *meta-app shell* — distinct from `ADMIN-GEN` (the auto-generated per-tenant admin tabs rendered from `SchemaIR`). `ADMIN-GEN` becomes the workspace pane *inside* the meta-app.
- Frontend stack remains as locked in `02-tech-stack.md`: React 18 + Vite + Radix + Tailwind + TanStack Router + TanStack Query + TanStack Table + TanStack Virtual + Zustand + Zod + Recharts + Shiki/Monaco + lucide-react + Vitest + Playwright. No additions.
- Specced in `docs/40-features/WEB-APP.md` before any implementation, per §9 working norms.
- TDD-first applies: every feature folder ships failing test → implementation → green → refactor. Playwright covers golden-path flows.
- The `system_docs/frontend_*.md` files (May 3, 2026) and the entire `archive/client-pre-pivot/` + `archive/server-pre-pivot/` directories described pre-pivot trust-workspace surfaces (KPI Trust Cards, Synthetic Data Lab, Critic Report, Simulation as user tabs) that §7 above explicitly deletes. **Deleted 2026-05-07.** The new spec lives in `docs/40-features/WEB-APP.md`. The frontend architecture + design system + design process is locked in [`docs/06-design.md`](06-design.md) (also locked 2026-05-07).
- ICP coverage: the same web app serves ICP-A (developer self-serve) and ICP-B (founder-driven SMB onboarding). Per `20-gtm.md` §2.5, v1 weighting is 60/30/10 ICP-A/B/C+D. The IA defaults to ICP-A discovery and routes ICP-B through a `/start` business-first onboarding lane on the same screens.

**How to apply:** When working on Baseflo, treat the web app as a first-class subsystem peer to the engine, control-plane DB, and connector framework — not a thin client. The boundary `01-architecture.md` §3.7 ("admin panel rendered from `SchemaIR`") still holds inside the workspace; the meta-app shell around it is hand-coded React with the schema-driven admin nested inside.

## Changelog

| Date | Change | Author |
|---|---|---|
| 2026-05-06 | Initial decisions log. Q1 = Option B; Q2 = Baseflo; Q3 = agentic decomposition + structural verification only. | Founders + AI architect |
| 2026-05-06 | LLM provider for v1: OpenAI (gpt-4.1-mini / gpt-4.1 / o3-mini). Switch to Anthropic deferred until account provisioning. | Founders |
| 2026-05-07 | §10 Web App in alpha scope; reverses CLI/SDK-only alpha cut from `ALPHA-TEST-PLAN.md`. New `WEB-APP` feature group; spec in `docs/40-features/WEB-APP.md`. `system_docs/frontend_*.md` flagged stale (pre-pivot). | Founder + AI architect |
| 2026-05-07 | `system_docs/frontend_*.md` archived under `system_docs/_archive_pre_pivot/`. Frontend architecture & design system locked in `docs/06-design.md` (React 18 + Vite, TanStack Router/Query, Radix + Tailwind tokens, Recharts, Vitest + Playwright, Storybook 8, `@baseflo/ui` shadcn-style internal lib). | Founder + AI architect |
| 2026-05-07 | All pre-pivot artifacts deleted: `archive/client-pre-pivot/`, `archive/server-pre-pivot/`, `system_docs/_archive_pre_pivot/`. Reason: `archive/client-pre-pivot/` was a `baseflo-client` workspace name collision causing `pnpm dev` to serve the old trust-workspace UI instead of the new web app. Single source of truth = `client/`. | Founder + AI architect |
| 2026-05-08 | **Design language pivot.** Initial `06-design.md` §4.8 forbade glow/orbs/decoration outright, which produced a bland "data dump" feel. Pivot allows **state-bearing motion** (active-stage pulse rings, count-up animations on trust counters, slide-in for fresh artifacts/activity), **editorial serif beyond hero strings** (any moment of trust or reveal — sign-in, workspace counts, share summary, refinement title), and **two registers within one app** (calm in tables and admin; confident-with-motion at agent activity, reveal, and trust moments). Still locked: no purple/pink AI gradients, no glassmorphism, no marketing-hero composition mid-app, status conveyed by color + icon + label, all motion respects `prefers-reduced-motion`. Anti-pattern fence is now "decoration vs state-bearing" rather than "no motion at all." `06-design.md` §4.8 updated. | Founder + AI architect |
