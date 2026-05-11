# Baseflo

> Run your business from one place. Connected to what you already use.

Baseflo is the agentic business operations layer. Connect existing tools (Excel, Notion, Postgres, Shopify, Stripe, Mailchimp, Zoho, or a custom internal system), and receive a unified schema agentically reconciled across sources, a hosted admin panel, typed REST + TypeScript SDK, behavioral analytics, and a daily digest. No migration. No backend code.

This repo is at **M0 — Foundation Reset** (2026-05-06). The pre-pivot codebase has been archived; the active tree is a clean slate built against the architecture and patterns locked in [`docs/00-decisions.md`](docs/00-decisions.md).

## Where to start

1. [`docs/00-decisions.md`](docs/00-decisions.md) — single source of truth for every locked decision. Read first.
2. [`docs/01-architecture.md`](docs/01-architecture.md) — full system architecture: engine, agents, connectors, deployment modes.
3. [`docs/05-coding-rules.md`](docs/05-coding-rules.md) — TDD-first, no LLM-wrapper, no regex/heuristics, layer boundaries, code review checklist.
4. [`docs/31-todolist.md`](docs/31-todolist.md) — milestone-grouped build tasks, M0 onward.

## Repository structure

| Directory | Purpose |
|---|---|
| [`docs/`](docs/) | Architecture, product, GTM, per-feature HLDs. Single source of truth. |
| [`system_docs/`](system_docs/) | Legacy product blueprints + audit findings. Institutional memory. |
| `server/` | Python FastAPI engine + agents + connector framework (M0 build target). |
| `client/` | TypeScript / React monorepo: admin UI, marketing, contracts, error system. |
| `sdk/ts/` | TypeScript SDK published as `@baseflo/sdk`. Generated from schema IR. |
| `cli/` | Go single-binary CLI: `baseflo init`, `connect`, `dev`, `deploy`. |
| `connectors/` | Per-connector plugin implementations (built-in + custom-authoring scaffold). |
| `infra/` | Docker image, Helm chart, Terraform. |
| `examples/` | Reference frontends + test fixtures. |
| `archive/` | Pre-pivot codebase preserved for reference. Will graduate to a separate branch once M1 ships. |

## Working norms

- TDD-first. No PR reviewable without a preceding test commit.
- No regex / keyword heuristics for semantic decisions. Agents reason; deterministic compilers verify and emit.
- Every error coded `BF-AREA-NNN` and documented in `docs/40-features/<feature>.md`.
- Every public boundary strongly typed. No `dict[str, Any]` in critical paths.
- Layer boundaries enforced by `import-linter`.
- Industry-grade or it doesn't ship.

## License

TBD.
