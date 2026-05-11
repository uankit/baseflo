# Baseflo — Technology Stack

Status: locked for first build. Every choice has a why and a tradeoff. Disagreements go to a decision-log entry.

---

## Stack Summary

| Layer | Choice | Why | Considered alternatives |
|---|---|---|---|
| **Server runtime** | Python 3.12 + FastAPI + Uvicorn | Existing investment; Pydantic ecosystem is the engine's spine; agent tooling matures fastest in Python. | Go (rejected: AI ecosystem weaker); Node (rejected: Pydantic equivalent doesn't match). |
| **Agent framework** | Pydantic AI + Pydantic Graph | Typed outputs, output validators, model abstraction, `TestModel` for TDD; Graph gives explicit nodes/edges. | LangGraph (rejected: opaque state, less typed); CrewAI (rejected: less mature); custom (rejected: reinventing without benefit). |
| **Schema validation** | Pydantic v2 | De facto standard; performance; first-class FastAPI/Pydantic AI integration. | attrs / msgspec (faster but no ecosystem). |
| **ORM & migrations** | SQLAlchemy 2.x + Alembic | Mature, type-friendly, async support; existing investment. | SQLModel (rejected: limits us to its conventions); raw SQL (rejected: maintenance cost). |
| **Database (control plane)** | Postgres 16 | First-class with SQLAlchemy; `LISTEN/NOTIFY` for SSE; row-level security; extension ecosystem. | MySQL (rejected: weaker JSONB and RLS); SQLite (rejected: not multi-instance). |
| **SQL parsing/dialect** | SQLGlot | Multi-dialect parser/transpiler; existing investment; lets us emit Postgres now and Snowflake/MySQL later through one IR. | sqlparse (rejected: parser only, no transpile); raw string templates (rejected: violates the no-heuristic rule). |
| **In-engine analytics** | DuckDB | Columnar, fast, type-aware in-process SQL for KPI execution against generated rows; far better than text-only SQLite shim flagged in the audit. | SQLite (rejected: type erasure); Postgres temp tables (rejected: round-trip cost). |
| **Dataframes (KPI compute)** | Polars | Fast, typed, lazy; complements DuckDB. | pandas (rejected: weaker types, slower). |
| **Job queue** | arq (Redis-backed) | Async-native, simple, Pydantic-friendly. | Celery (rejected: heavier, sync-first); RQ (rejected: weaker async story); Dramatiq (acceptable; arq wins on Pydantic alignment). |
| **Pub/sub for SSE** | Postgres `LISTEN/NOTIFY` | Free, multi-instance safe, single dependency. | Redis pub/sub (acceptable; we already have Redis for arq, but adding both reduces failure-domain isolation). |
| **HTTP client** | `httpx` | Async; first-class in FastAPI ecosystem; existing investment. | aiohttp (acceptable). |
| **Retry / backoff** | `tenacity` | Standard, declarative, type-safe. | Custom (rejected: not worth it). |
| **Logging** | `structlog` + JSON output | Structured logs; tenant/request/job context propagation. | stdlib logging (rejected: weaker structured story). |
| **Tracing** | OpenTelemetry SDK | Vendor-neutral; sinks to Honeycomb / Datadog / open-source. | Vendor SDKs (rejected: lock-in). |
| **Testing** | pytest + pytest-asyncio + Playwright + k6 | TDD-first; broadest ecosystem; Playwright for E2E; k6 for load. | unittest (rejected: weaker fixtures); JMeter (rejected: heavier than k6). |
| **Linting / formatting** | ruff + mypy --strict | Existing investment; ruff is the right speed; mypy strict matches the typed-output bar. | flake8/black (rejected: ruff replaces both). |
| **Auth** | Lucia for sessions; OAuth via `authlib`; passwordless email magic links via Resend. | Lightweight; framework-agnostic; matches our session model. | Clerk (good UX but vendor lock-in and pricing); Auth0 (heavier, costlier). Revisit at M4 (enterprise SSO needs SAML/OIDC). |
| **Secrets / KMS** | AWS KMS for hosted; per-tenant DEK; envelope encryption. | Industry standard for SaaS at this scale. | HashiCorp Vault (acceptable for self-host customers wanting their own KMS). |
| **Frontend framework** | React 18 + Vite | Existing investment; Vite is fast; no need for Next.js server-rendering at this stage. | Next.js (acceptable; reconsider when SEO matters); Remix (acceptable; not warranted). |
| **Frontend types** | TypeScript strict | Existing investment; non-negotiable. | none (lol). |
| **UI primitives** | Radix UI + Tailwind + shadcn-style components in `@baseflo/ui` | Accessible primitives; full control; spec-aligned (the audit flagged we hadn't integrated these). | MUI (rejected: heavier, harder to brand); Chakra (acceptable). |
| **Code editor in admin (SQL/JSON views)** | Shiki for read-only display; Monaco for editing where needed | Spec-aligned; the audit flagged we'd skipped this. | CodeMirror (acceptable; Monaco is more featureful). |
| **Tables / virtualization** | TanStack Table + TanStack Virtual | Spec-aligned; required for synthetic-data preview and large list views. | ag-grid (rejected: licensing). |
| **Charts** | Recharts | Existing investment. | Vega-Lite (more powerful; consider in M2). |
| **Data fetching** | TanStack Query | Standard; SSE complementary. | SWR (acceptable). |
| **State (UI-only)** | Zustand | Light; existing investment. | Redux (rejected: too heavy). |
| **Runtime validation (client)** | Zod | The audit flagged this gap; required for SSE payload + REST response validation. | valibot (acceptable; Zod has more ecosystem). |
| **Contract codegen** | OpenAPI from FastAPI → `openapi-typescript` for types + custom generator for SDK + admin form schemas | Removes the hand-maintained TypeScript drift the audit flagged. | datamodel-code-generator (acceptable). |
| **Monorepo** | pnpm workspaces + Turbo | Existing investment. | Nx (rejected: heavier; Turbo is enough). |
| **CLI** | Go + Cobra | Single static binary, no runtime install for users; great cross-platform distribution; `baseflo init` should be `curl \| sh` simple. | Node (rejected: requires Node install); Python (rejected: requires Python install); Rust (acceptable; Go is faster to ship in). |
| **CLI distribution** | GitHub Releases + Homebrew tap + `curl \| sh` installer | Standard. | npm (rejected: requires Node). |
| **SDK (TypeScript)** | Generated from schema IR; published as `@baseflo/sdk`; tiny runtime; types-first | Two-line drop-in for AI tools (Claude Code, Cursor). | Hand-written (rejected: drift). |
| **SDK (Python)** | Same generation pipeline; `baseflo` PyPI package. Ships M3+. | Mirror the TS SDK for the Python user segment. | n/a |
| **Container runtime** | Docker; Compose for local dev; Kubernetes/Helm for enterprise self-host | Standard. | n/a |
| **CI/CD** | GitHub Actions | Standard; matches team familiarity. | CircleCI / GitLab CI (acceptable). |
| **Hosting (cloud)** | AWS — ECS Fargate or Fly.io for engine workers; RDS Postgres; ElastiCache Redis; KMS; S3 for exports | Mature, SOC2-friendly, region-flexible. | GCP (acceptable); Render/Railway for early staging only. |

---

## LLM Provider Strategy

- **Default for v1:** OpenAI — `o3-mini` for `reasoning` tier, `gpt-4.1` for `balanced`, `gpt-4.1-mini` for `fast`. Defaults overridable via env (`BASEFLO_AGENT_FAST_MODEL_NAME`, `BASEFLO_AGENT_BALANCED_MODEL_NAME`, `BASEFLO_AGENT_REASONING_MODEL_NAME`).
- **Why OpenAI for v1:** founder already has OpenAI account; structured-output API is mature; prompt caching is automatic on stable prefixes; Pydantic AI's OpenAI integration is the most-tested.
- **Switch path to Anthropic:** the model abstraction is provider-agnostic via Pydantic AI. Switching is an env-level change once the founder has Anthropic provisioned. Suggested mapping: `gpt-4.1-mini` → `claude-haiku-4-5`, `gpt-4.1` → `claude-sonnet-4-6`, `o3-mini` → `claude-opus-4-7`. No code change required.
- **Provider abstraction enforced:** all agents go through `app/agents/model_routing.py`. The agent code NEVER imports `openai` or `anthropic` directly. Pydantic AI is the only provider boundary.
- **Multi-provider routing (M3+):** different agents to different providers based on cost/quality benchmarks. Required for enterprise customers who insist on a specific provider for compliance or contract reasons.
- **Local model fallback (M5+):** small structural agents (e.g., `IntentClassifier`, `ExplanationAuthor`) can run on local models (e.g., a Llama or Qwen variant via Ollama) for self-host customers who refuse cloud LLM calls. Requires evaluation harness to confirm quality non-regression before promoting any agent to local-only.

## Privacy Stack (PII / compliance tooling)

- **PII detection in v1:** agent-driven only (`ColumnClassifier`). No automated free-text PII detection.
- **PII detection in v3:** Microsoft Presidio on free-text columns; OpenAI Privacy Filter as a backup option for hosted customers willing to send text to a privacy-focused model.
- **Compliance posture:** GDPR-ready from day one (data export, deletion, processing record). SOC2 Type 1 within 12 months of first paying customer. HIPAA roadmap unlocked by self-host first.

## Observability Stack

- Logs → Loki (self-host) or Datadog (hosted-cloud) via structlog JSON output.
- Traces → Honeycomb (preferred) or Datadog APM, via OpenTelemetry.
- Metrics → Prometheus-compatible; Grafana dashboards in repo (`infra/grafana/`).
- Errors → Sentry.

## Build / Distribution

- **Server image:** built per push to `main`; tagged with git SHA and semver.
- **CLI binary:** built per release; tagged release on GitHub; updates checked at runtime with opt-out.
- **Frontend:** built and deployed to Cloudflare Pages or Vercel; routes to API via reverse-proxy on the same domain.
- **Self-host Docker image:** monthly stable releases; security patches as needed.

## What We Are Not Using (Explicit Rejections)

- **LangChain / LlamaIndex** — opaque state, weaker typing than Pydantic AI. We have the engine to manage state ourselves.
- **OpenAI Agents SDK** as the primary runtime — single-vendor; less typed; weaker testability.
- **Static template catalogs** (e.g., a SaaS template, a marketplace template) — violates the agentic-bar rule from `00-decisions.md`.
- **Faker as the synthetic-data engine** — it's a leaf-value generator only; behavioral synthetic data lives in the `BehaviorPlanner` agent + deterministic generator.
- **Regex / keyword heuristics for semantic classification** — flagged as forbidden in `00-decisions.md`. The only legitimate regex use is structural validation (e.g., SQL identifier safety).

## Versioning & Compatibility

- **Server:** SemVer; API versioned at the URL (`/api/v1/`); breaking changes require a new version path.
- **SDK:** SemVer aligned with API; `@baseflo/sdk@1.x` ↔ `/api/v1/...`.
- **Schema IR:** internal-only; versioned via the `schemaVersion` field on artifact records (the audit flagged this is currently inert; we'll wire it to actual migration logic in M2).
- **Contracts package:** breaking changes ship in major bumps; SDK and admin UI are pinned together.

## Cost Posture

- **Hosted-cloud unit economics target:** gross margin 75%+ at scale. Per-tenant cost ceiling is monitored on a daily roll-up.
- **LLM cost discipline:** prompt-caching alignment (per `00-decisions.md` and `03-agentic-workflow.md`); model tier routing per agent; usage limits enforced before hitting hard caps.
- **Storage cost:** customer data is bounded by per-plan limits; exports are not stored more than 24h.
- **Egress cost:** sync mode costs are passed through with margin in higher tiers.
