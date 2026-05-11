# Baseflo — Coding Rules

Status: enforced. Every PR is reviewed against this document. Violations block merge regardless of how clever the code is.

This document is short on purpose. The rules are the rules.

---

## 1. The Three Non-Negotiables

### 1.1 No LLM-Wrapper Pattern

We are not a wrapper around a model API.

- **Every semantic decision is owned by a typed-output agent in `app/agents/specialists/`.**
- **Every structural step is owned by deterministic code in `app/engines/`.**
- **The boundary is strict.** A function that decides what something *means* is an agent. A function that *parses, validates, or emits* a known structure is deterministic.

If you find yourself writing one big function that "asks the LLM and then patches up the answer with `if`s," stop. That's the wrapper pattern. Decompose into:
1. A narrow agent with a typed input/output.
2. A deterministic compiler that consumes the agent's typed output.
3. A validator that rejects malformed output via `ModelRetry`.

### 1.2 No Regex / No Keyword Heuristics for Semantic Decisions

The audit caught eight of these in the prior code. They will not return.

**Forbidden, no exceptions:**

```python
# FORBIDDEN
if "marketplace" in prompt.lower():
    interaction_label = "Order"

# FORBIDDEN
if column_name.endswith("_cents"):
    money_columns.append(column_name)

# FORBIDDEN
edge_terms = ("cancel", "churn", "refund", "ticket")
score = sum(10 for term in edge_terms if term in table_name)

# FORBIDDEN
if any(word in lower for word in ("remove", "delete", "exclude")):
    return "delete"
```

**Allowed (structural, deterministic):**

```python
# ALLOWED — SQL identifier safety, not a semantic decision
_IDENTIFIER = re.compile(r"^[a-z][a-z0-9_]*$")

# ALLOWED — case-insensitive dedup of agent-emitted names
key = entity_name.lower()
if key in seen: ...

# ALLOWED — cardinality form parsing into a typed enum
if cardinality_str in {"1..*", "one_to_many", "1:n"}:
    return Cardinality.ONE_TO_MANY
```

The test: *if a human architect would reason about this case-by-case based on context, an agent makes the call*. *If the rule is mechanical and finite, deterministic code makes the call*.

### 1.3 TDD-First, Always

Every feature, every agent, every compiler:

1. Write the failing test.
2. Run it. Confirm it fails *for the expected reason*.
3. Write the smallest implementation that makes it pass.
4. Re-run. Confirm green.
5. Refactor only after green.

PRs that arrive with implementation code and no preceding test commit are not reviewable. The git log is the audit trail.

For agents, "the test" uses Pydantic AI's `TestModel` or `FunctionModel`. Real provider calls in unit tests are forbidden — they're slow, non-deterministic, and cost money.

For compilers and repositories, "the test" is pytest with fixtures.

For end-to-end, "the test" is Playwright against a test tenant with `TestModel` injected.

## 2. Typing Rules

### 2.1 Every Public Boundary Is Typed

- Pydantic models for DTOs, agent I/O, artifact storage.
- SQLAlchemy 2.x typed mappers for ORM.
- TypeScript strict mode on the client.
- Function signatures use full type hints; mypy `--strict` runs in CI; `Any` requires a comment justifying why.

### 2.2 No `dict[str, Any]` in Critical Paths

Forbidden in:
- Agent input/output models.
- Artifact records (`schema_ir`, `kpi_definitions`, etc.).
- API request/response models.
- Connector schema descriptions.
- Schema IR.

Allowed in:
- Adapter glue code where the upstream library returns untyped dicts (immediately convert to a typed model on entry).
- Logging structured fields.

### 2.3 No Optional Fields That Aren't Truly Optional

If a field is required for the system to function, it's required. Don't sprinkle `Optional[...]` to dodge validation; let the validation fail loudly when something is missing.

## 3. Layering & Boundary Rules

### 3.1 Layer Order (downward only)

```
api → services → engines / agents → repositories → db
                          ↓
                     data plane
```

- API layer is thin: it parses requests, calls services, returns responses. No business logic.
- Services orchestrate use cases; they call engines and agents; they coordinate repositories.
- Engines and agents are pure-ish: deterministic compilers and Pydantic AI agents.
- Repositories are the only place SQLAlchemy sessions are touched.
- The data plane is the only place per-tenant data is read or written.

Reverse imports are forbidden by convention and enforced by `import-linter`.

### 3.2 Repositories, Not Sessions in Services

A service receives a repository (by DI). It does not import `Session` and does not call `db.flush()`. The audit caught a violation here; it stays caught.

### 3.3 Agents Don't Touch the Database

An agent receives typed input and produces typed output. If it needs project metadata, it gets it via `deps`. The trace recorder writes the agent run row *after* the artifact commits, on a separate session.

## 4. Async vs Sync

- API is FastAPI async. All API handlers are `async def`.
- Repositories are async (SQLAlchemy 2.x async).
- Agents are async (Pydantic AI's `await agent.run(...)`).
- **Never** `asyncio.run(...)` inside a function called from an async context. The audit caught this; it doesn't return.
- CPU-bound work goes to a thread pool via `asyncio.to_thread(...)`; it doesn't block the event loop.

## 5. Error Handling

### 5.1 Typed Errors With Codes

Every failure path raises a `BasefloError(error_code="BF-AREA-NNN", ...)`. The error code:

- `BF-AGENT-NNN` — agent execution failures (invalid output, repair exhausted, model provider error).
- `BF-SCHEMA-NNN` — schema emission failures.
- `BF-DATA-NNN` — data-plane failures.
- `BF-CONN-NNN` — connector failures.
- `BF-AUTH-NNN` — authentication / authorization.
- `BF-VALID-NNN` — request validation.
- `BF-JOB-NNN` — background job failures.

Every error code is documented in `docs/40-features/<feature>.md`. Every error code has a test asserting it fires under the expected condition.

### 5.2 No Bare `except`

`except Exception` requires a comment explaining why and a re-raise or typed conversion. `except:` is never allowed.

### 5.3 No Silent Fallbacks

If an operation can't complete, it raises. It does not return a "default" object or silently substitute fixture data. The audit caught `live_or_fallback()` doing exactly this; it stays gone.

## 6. Logging

- `structlog` JSON output.
- Every log line includes `tenant_id`, `request_id`, `job_id` where applicable (set on context vars at request entry).
- PII columns (per `ColumnClassifier`'s labels) are masked at log time. The masker is a single function used by the logger configurator.
- No `print()` statements outside of CLI tools.
- Log levels:
  - `DEBUG` — verbose internal state, off in prod by default.
  - `INFO` — successful key state transitions (job started, agent completed).
  - `WARNING` — recoverable failures, retry events.
  - `ERROR` — failures requiring operator attention.
  - `CRITICAL` — paging conditions.

## 7. Secrets

- Secrets come from env via `pydantic-settings`. Never from command-line flags, never from code constants.
- Connector tokens, KMS keys, OAuth refresh tokens use the envelope encryption helpers in `app/core/crypto.py`.
- `.env` files are git-ignored. The repo's `.env.example` lists every variable with a placeholder.

## 8. Naming

### 8.1 Python

- Modules `snake_case.py`.
- Classes `PascalCase`.
- Functions and variables `snake_case`.
- Constants `UPPER_SNAKE_CASE`.
- No abbreviations except universal ones (`db`, `id`, `url`).

### 8.2 Database

- Tables `snake_case`, plural (`organizations`, `connector_tokens`).
- Columns `snake_case`.
- Foreign keys `<referenced_table_singular>_id`.
- Timestamps `<noun>_at`.
- Money columns `<noun>_minor` + `<noun>_currency`.

### 8.3 TypeScript

- Files `kebab-case.ts` or `PascalCase.tsx` for components.
- Types `PascalCase`.
- Variables and functions `camelCase`.
- Contracts mirror server names exactly (`workspaceId` not `workspace_id` — the codegen handles the boundary).

### 8.4 Agents

- Specialist files `app/agents/specialists/<role>.py`.
- Agent class names match registry name (`ColumnClassifier`).
- Prompts kept in the same file as the agent; never imported from a string blob outside the module.

## 9. Code Review Checklist

Reviewer runs this list. If any answer is "no," request changes.

- [ ] Tests committed before implementation? (Check git log.)
- [ ] All new agents have typed input + typed output Pydantic models?
- [ ] Output models contain no `Any`, no bare `dict`, no `list[dict[str, Any]]`?
- [ ] Agent prompt has persona, job, inputs, output schema reference, rules, forbidden patterns, ≥1 example, ≥200 words?
- [ ] Agent has output validator with `ModelRetry`?
- [ ] Model name not hardcoded in agent code (uses `model_routing.py`)?
- [ ] Trace persistence wired and not blocking the workspace.ready path?
- [ ] No regex / keyword heuristic doing semantic classification?
- [ ] No `dict[str, Any]` in critical paths?
- [ ] No `asyncio.run(...)` inside async-callable code?
- [ ] No service touching `Session` directly?
- [ ] No agent touching the database?
- [ ] No bare `except`?
- [ ] No silent fallback to deterministic stub?
- [ ] Every error path has a `BF-AREA-NNN` code and a test?
- [ ] Migration ships with downgrade?
- [ ] CI: ruff, mypy --strict, pytest, type-check pass?
- [ ] Feature has HLD/LLD entry in `docs/40-features/`?

## 10. Pre-Merge Gate

CI must be green. Specifically:

1. `ruff check` — no errors.
2. `ruff format --check` — formatted.
3. `mypy --strict app/` — no errors.
4. `pytest` — green; coverage threshold per area (engines/agents target 90%, repositories 85%, services 80%).
5. `import-linter` — no boundary violations.
6. `alembic check` — no auto-generated migrations missed.
7. `pnpm typecheck` — TS strict passes.
8. `pnpm test` — client tests pass.
9. `playwright test` — at least the smoke suite passes against the test tenant.

`--no-verify` is forbidden. Hooks run on every commit.

## 11. Industry-Grade Defaults

These are not negotiable for v1:

- All HTTP responses include a `request_id` header.
- All API errors include a JSON body with `error_code`, `message`, `details`, `request_id`.
- All write endpoints support an `Idempotency-Key` header.
- All large responses paginate (cursor-based; never offset for cross-tenant tables).
- All long-running operations return `202 Accepted` with a job id and an SSE channel.
- All exports go through a job; no inline export of arbitrary size.
- Every API key, session token, and connector token is hashed in storage.
- TLS 1.3 only.
- Strict `Content-Security-Policy`, `X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin` on the admin app.
- Rate limits per-tenant and per-IP.

## 12. When You're Stuck — Pause and Ask

Founder note (locked into the working norms): when an assumption would be expensive to undo, **stop coding and ask**. Cheap to ask, expensive to retro-fit. This is one of the few cases where slowing down is faster.

Examples of questions worth pausing for:
- Schema-shaping decisions that would require a data migration to undo.
- Privacy-affecting choices (where data lives, what's logged).
- Cross-cutting agent decisions (a new prompt convention, a new tier rule).
- Any naming that becomes part of the public API.

Questions not worth pausing for:
- Internal helper function names.
- Whether to use `for` or `while` (the answer is `for`).
- Anything you can decide and revert in 30 minutes.
