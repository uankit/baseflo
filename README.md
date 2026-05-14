# Baseflo

> Run your business from one place. Connected to what you already use.

Baseflo is the adaptive operating intelligence layer for a business. Connect existing tools (spreadsheets, databases, SaaS exports, Stripe, CRM, HR tools, support tools, or a custom internal system), and Baseflo learns the shape of the data, watches for meaningful change, explains why it matters, and proposes controlled next moves. No templates. No AI employee cosplay. Grounded intelligence first, governed action next.

The active product direction is captured in [`docs/ADAPTIVE-OPERATING-INTELLIGENCE.md`](docs/ADAPTIVE-OPERATING-INTELLIGENCE.md). Older planning docs may remain for historical reference, but executable code should follow the adaptive operating intelligence workflow.

## Where to start

1. [`docs/ADAPTIVE-OPERATING-INTELLIGENCE.md`](docs/ADAPTIVE-OPERATING-INTELLIGENCE.md) — current product stance: problem, loop, surfaces, and engineering boundary.
2. [`docs/05-coding-rules.md`](docs/05-coding-rules.md) — engineering guardrails.

## Repository structure

| Directory | Purpose |
|---|---|
| [`docs/`](docs/) | Product stance, architecture notes, and historical planning docs. |
| `server/` | Python FastAPI engine: auth, connectors, substrate, ask, operating intelligence. |
| `client/` | TypeScript / React monorepo for the hosted operating workspace. |
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
