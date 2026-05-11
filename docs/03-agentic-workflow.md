# Baseflo — Agentic Workflow

Status: locked. This document describes how agents are built, composed, prompted, retried, cached, traced, and tested. Defers to `00-decisions.md` for the agentic bar and `01-architecture.md` for the broader system.

---

## 1. Operating Principle

**Agents reason like architects. Deterministic compilers verify and emit. The user sees a polished product, not the machinery.**

This means:
- Every semantic decision (what is a customer, what is money, what should this KPI be, are these the same entity across two sources) is made by a typed-output agent and traceable.
- Every structural step (parse `1..*`, validate `customer_id` is a safe SQL identifier, emit DDL, write audit log) is made by deterministic code.
- Nothing in between. The minute someone writes `if "saas" in prompt.lower()`, that's a violation. The minute someone hand-emits SQL inside an agent prompt, that's a violation.

## 2. Why Pydantic AI + Pydantic Graph

- **Typed outputs:** agents declare a Pydantic `output_type`; structured generation, structured validation, structured retries.
- **`TestModel` and `FunctionModel`:** tests run without provider calls; TDD is realistic for agents.
- **Output validators:** raise `ModelRetry(...)` to make the agent self-correct.
- **Model abstraction:** swap providers per tier without touching agent code.
- **Pydantic Graph:** explicit nodes, edges, joins, human-in-loop pause/resume. The audit flagged we used lambda closures; we move to formal graph nodes.

## 3. Agent Anatomy (every agent looks like this)

```python
# server/app/agents/specialists/column_classifier.py
from pydantic import BaseModel, Field
from pydantic_ai import Agent, ModelRetry, RunContext

from app.agents.registry import register_agent
from app.agents.model_routing import resolve_model
from app.agents.types import AgentDeps

class ColumnClassifierInput(BaseModel):
    source_name: str
    table_name: str
    columns: list[ColumnSample]              # name, observed_type, sample_values

class ColumnClassifierOutput(BaseModel):
    classified: list[ClassifiedColumn]       # canonical_name, semantic_type, rationale, confidence

INSTRUCTIONS = """
You are Baseflo's column classifier. You see a single source table and assign
each column a semantic type from this enum: IDENTITY, FOREIGN_KEY_CANDIDATE,
MONEY, STATUS, TEMPORAL, PII_EMAIL, PII_PHONE, PII_ADDRESS, PII_NAME,
PII_ID_NUMBER, CATEGORY, FREE_TEXT, BOOLEAN, COUNT, DERIVED.

You also produce a canonical_name in snake_case (e.g., "customer_email").

Rules:
- Never invent verticals; classify by observed evidence, not by source-table name.
- For MONEY, also infer the minor unit assumption based on observed values.
- For STATUS, list the observed enum values you would propose.
- If unsure, return CATEGORY with low confidence; the reconciler will resolve.
- If a column is purely synthetic (e.g., row index), return DERIVED.

Output schema: ColumnClassifierOutput (typed). Do not output anything else.
"""

agent = Agent(
    model=resolve_model("ColumnClassifierAgent"),    # tier-routed; do not hardcode
    deps_type=AgentDeps,
    output_type=ColumnClassifierOutput,
    instructions=INSTRUCTIONS,
    retries=2,
)

@agent.output_validator
async def validate(ctx: RunContext[AgentDeps], out: ColumnClassifierOutput) -> ColumnClassifierOutput:
    seen = set()
    for c in out.classified:
        if c.canonical_name in seen:
            raise ModelRetry(f"Duplicate canonical_name: {c.canonical_name}.")
        seen.add(c.canonical_name)
        if c.semantic_type == SemanticType.MONEY and not c.minor_unit:
            raise ModelRetry(f"Column {c.canonical_name} is MONEY; supply minor_unit.")
    return out

register_agent(
    name="ColumnClassifier",
    agent=agent,
    input_type=ColumnClassifierInput,
    output_type=ColumnClassifierOutput,
    model_tier="balanced",
)
```

Every agent in the system has this exact shape. The bar is enforced in code review.

## 4. Agent Registry

`server/app/agents/registry.py` is the single source of truth. Adding an agent:

1. Create `specialists/<name>.py` matching the anatomy above.
2. Call `register_agent(...)` at module import.
3. Add a model tier mapping to `model_routing.py`.
4. Write a unit test using `TestModel` / `FunctionModel` first (TDD).

The registry exposes:

```python
class AgentSpec:
    name: str
    agent: pydantic_ai.Agent
    input_type: type[BaseModel]
    output_type: type[BaseModel]
    model_tier: Literal["fast", "balanced", "reasoning"]
    cache_key_fn: Callable[[BaseModel], str]
```

The orchestration layer never instantiates agents directly. It looks them up by name.

## 5. Model Routing

```python
# server/app/agents/model_routing.py
AGENT_MODEL_TIERS: dict[str, ModelTier] = {
    # Core data-architect graph
    "ClarificationAgent":            "fast",
    "ColumnClassifier":              "balanced",
    "EntityReconciler":              "reasoning",   # poison if wrong; cardinal moat decision
    "CardinalityResolver":           "reasoning",
    "ConstraintProposer":            "reasoning",
    "PhysicalSchemaArchitect":       "reasoning",
    "KPIPlanner":                    "reasoning",
    # Internal terminal gate (never user-surfaced)
    "CoherenceGate":                 "reasoning",   # cross-cutting consistency; emits typed RepairRoute on fail
    # Refinement graph
    "IntentInterpreter":             "balanced",
    "ImpactAnalyzer":                "reasoning",
    "ChangePlanner":                 "reasoning",
}
```

**Removed from the prior list (17 → 11):** `IntentClassifier` (UI routes intent), `ConnectorIntrospector` (mechanical via connector APIs), `DashboardComposer` (deterministic emission from `KPIPlanner` output), `ExplanationAuthor` (lazy on-demand only), `ChildVersionAuthor` (deterministic merge of `change_plan + parent_IR → child_IR`), and `BehaviorPlanner` (dev convenience; deferred). The trust-workspace `CriticReviewer` is replaced by `CoherenceGate` — same intent, sharper contract: internal terminal gate, never a user-visible artifact.

Tier names map to model names from environment-configured settings (v1 defaults are OpenAI; switching to Anthropic is an env-only change):

| Tier | Env var | v1 default (OpenAI) | Future Anthropic equivalent |
|---|---|---|---|
| `fast` | `BASEFLO_AGENT_FAST_MODEL_NAME` | `gpt-4.1-mini` | `claude-haiku-4-5` |
| `balanced` | `BASEFLO_AGENT_BALANCED_MODEL_NAME` | `gpt-4.1` | `claude-sonnet-4-6` |
| `reasoning` | `BASEFLO_AGENT_REASONING_MODEL_NAME` | `o3-mini` | `claude-opus-4-7` |

The audit flagged the existing `gpt-5.2` placeholder in `core/config.py` defaults; that gets deleted and replaced with the values above. Tests use `TestModel` / `FunctionModel` and never call the real provider.

Escalation rule: an agent that fails validation twice on `balanced` is auto-escalated to `reasoning` for the next attempt. Captured in trace metadata.

## 6. Prompt Engineering Standards

The audit flagged prompt caching misalignment, weak instructions, and missing forbidden-pattern guidance. The new bar:

### 6.1 Cache-aligned structure

Every prompt is split into three regions, in this exact order:

1. **Static instructions** (`instructions=` on the `Agent`) — persona, rules, output schema reference, examples, forbidden patterns. These NEVER include user-specific data.
2. **Dependency context** (passed via `deps`) — workspace metadata, cached primitive library hits, structural references.
3. **User input** (passed as the prompt at run time) — the variable part.

This aligns with Anthropic prompt caching and OpenAI prompt caching: stable prefix, variable suffix.

### 6.2 Required prompt sections

Every agent's `INSTRUCTIONS` block contains:

- **Persona:** "You are Baseflo's [role]."
- **Job:** one-paragraph statement of purpose.
- **Inputs:** what they receive (shape, constraints).
- **Output schema:** the Pydantic class signature, inline.
- **Domain rules:** 3–7 bullets the agent must obey.
- **Forbidden patterns:** explicit "do not invent verticals," "do not assume column names," "do not output SQL," etc., per agent.
- **Examples:** at least one clean input → output example. Two if the agent's job is ambiguous.

No agent ships with fewer than 200 words of instructions. The current 7-word `CriticAgent` is a violation; it is being rewritten as part of M0.

### 6.3 Forbidden-pattern guidance (per agent)

Each prompt explicitly forbids the patterns most likely to corrupt the system:

- `ColumnClassifier`: "Do not classify by source-table name. Do not assume `_cents` means money. Classify by observed evidence."
- `EntityReconciler`: "Do not assume two tables with the same name in different sources are the same entity. Verify by join keys and value overlap."
- `PhysicalSchemaArchitect`: "Do not invent generic tables (`events`, `configs`, `settings`) unless explicitly required. Do not output SQL; output schema IR only."
- `KPIPlanner`: "Do not propose KPIs the schema cannot answer. Every KPI must reference real columns and a real grain."
- `CriticReviewer`: "Do not pass output that has missing relationships, contradictory cardinality, or fabricated columns. If unsure, fail."

## 7. Repair Loop

The runtime supports two-level repair:

1. **Output-validator-driven repair (cheap).** The validator raises `ModelRetry(message)`; Pydantic AI re-prompts the same agent with the message; up to `retries=2`. Used for fixable structural slips (duplicate names, missing required field, malformed enum value).
2. **Manager-driven escalation (expensive).** If validator-driven repair exhausts attempts, the manager escalates the model tier (balanced → reasoning) and retries once. If still failing, the manager either:
   - Asks a clarifying question (if a real business decision is missing).
   - Emits a typed failure (`BF-AGENT-003`) with full repair context.

Failures never silently fall back to deterministic generators. The audit flagged that `live_or_fallback()` did exactly this; it is deleted.

## 8. Trace and Telemetry

Every agent run records, atomically, after the artifact is committed:

```python
class AgentRun(SQLAlchemyModel):
    id: UUID
    tenant_id: UUID
    project_id: UUID
    project_version_id: UUID
    job_id: UUID
    agent_name: str
    model_tier: str
    model_name: str
    input_hash: str                      # for cache & dedup
    output_hash: str
    started_at: datetime
    completed_at: datetime
    duration_ms: int
    input_tokens: int                    # real, from provider; not zeroed
    output_tokens: int
    cache_read_tokens: int
    cache_write_tokens: int
    repair_attempts: int
    escalated: bool
    final_status: AgentRunStatus         # PASSED / WARNING / FAILED / NEEDS_CLARIFICATION
```

Plus `agent_run_attempts` rows for each individual attempt within a run.

Trace persistence is non-blocking: the workspace.ready event fires when artifacts are committed; trace writes happen after. The audit flagged a violation here; it's fixed by isolating trace persistence on a separate session/transaction.

The audit also flagged hardcoded zero token counts. Real provider usage is captured from Pydantic AI's `RunResult.usage()`.

## 9. Caching

Two layers:

1. **Agent instance cache.** `Agent` objects are heavy to construct (instructions hash, model name, output schema). Cached by `(agent_name, model_name, instructions_hash, output_schema_hash)` with bounded LRU + 1h TTL. Re-warmed on worker boot.
2. **Run output cache.** For deterministic-input agents (`ColumnClassifier` on a fixed source schema; `KPIPlanner` on a fixed `SchemaIR`), cache the output by `(agent_name, input_hash)`. Invalidate on schema or instruction-version bump.

Cache hits are recorded in trace; cache hit rate is a tracked metric.

## 10. Concurrency

- The orchestration manager runs agents **as a graph**, not as a strict sequence. Independent nodes (e.g., `ConnectorIntrospector` per source) run in parallel.
- Per-tenant concurrency limit (configurable; default 4 parallel agent calls) prevents one tenant from saturating provider quotas.
- The pipeline does not run on the API request thread (audit flagged this). Generation is queued via `arq`; the API returns `202 Accepted` immediately and the client subscribes to SSE for progress.

## 11. Human-in-the-Loop

- Pre-flight clarification: at most 3 questions, only when truly blocking. Implemented as a real `ClarificationAgent` (the audit flagged the current keyword heuristic; it's deleted).
- Mid-flight clarification is forbidden. Once generation starts, unresolved uncertainty becomes explicit assumptions in the artifact, surfaced as warnings on the workspace, never user interruptions.
- Refinement is the post-generation channel for evolution; it never blocks the original generation.

## 12. Testing Strategy (TDD-first)

For every new agent:

1. **Write the input/output Pydantic models.**
2. **Write a `TestModel` or `FunctionModel`-driven unit test** that exercises:
   - Happy path (one canonical input, one expected output).
   - Validator firing (input that should trigger `ModelRetry`).
   - Edge case (e.g., empty input, malformed input).
3. **Run the test; confirm it fails for the expected reason.**
4. **Write the agent module + prompt.**
5. **Re-run; confirm passing.**
6. **Refactor only after green.**

For integration:

- The pipeline integration test runs end-to-end with `TestModel` injected so no provider calls are made; output is asserted.
- A nightly canary run uses a real provider against a small evaluation set; results tracked in a quality dashboard.

## 13. Adding a New Agent — Checklist

- [ ] Input/output Pydantic models with strict types (no `Any`).
- [ ] Unit tests written first.
- [ ] `INSTRUCTIONS` block has all required sections (persona, job, inputs, output schema, rules, forbidden patterns, ≥1 example).
- [ ] Output validator with at least one `ModelRetry` rule.
- [ ] Model tier mapping in `model_routing.py`.
- [ ] Registered in `registry.py`.
- [ ] Trace metadata flowing.
- [ ] Cache key function defined if cacheable.
- [ ] Error code `BF-AGENT-NNN` defined and tested.
- [ ] HLD + LLD entry in `docs/40-features/<feature>.md`.

## 14. The 11 v1 Agents (10 user-flow + 1 internal gate)

Per `01-architecture.md` §3.2:

| Agent | Tier | Surface | Purpose |
|---|---|---|---|
| `ClarificationAgent` | fast | User-facing (preflight) | Max 3 blocking questions. Only when truly blocking; never mid-flight. |
| `ColumnClassifier` | balanced | User-flow | Per-column semantic typing (PII / status / money / id / temporal / category / free-text). Produces canonical names and labels. |
| `EntityReconciler` | reasoning | User-flow | **The moat.** Decides which entities span which sources; conflict resolution policy. |
| `CardinalityResolver` | reasoning | User-flow | Direction, optionality, ownership, M2M across reconciled entities. |
| `ConstraintProposer` | reasoning | User-flow | Keys, uniqueness, status transitions, money minor units, nullability. |
| `PhysicalSchemaArchitect` | reasoning | User-flow | Compose unified `SchemaIR`. |
| `KPIPlanner` | reasoning | User-flow | Business questions answerable; grain; assumptions. Drives analytics tab + daily digest. |
| `CoherenceGate` | reasoning | **Internal only** | Terminal gate. Cross-cutting consistency check across all prior outputs. Emits typed `RepairRoute` on fail; user never sees its report directly. |
| `IntentInterpreter` | balanced | User-flow (refinement) | Refinement intent parsing (no keyword matching). |
| `ImpactAnalyzer` | reasoning | User-flow (refinement) | What changes when refinement applies. |
| `ChangePlanner` | reasoning | User-flow (refinement) | Concrete delta against parent IR. |

Each gets its own `docs/40-features/agent-<name>.md` with HLD, LLD, prompt template, test plan, error codes.

### `CoherenceGate` — the internal-only contract

`CoherenceGate` is the only agent whose output is **never** exposed to the user as an artifact. It exists to catch cross-cutting failures that single-agent validators cannot:

- KPIs that reference columns the schema does not contain.
- Conflicting cardinality between `EntityReconciler` (reconciled entity-level) and `CardinalityResolver` (relationship-level).
- Fundamental concept missing (e-commerce-shaped schema with no order/transaction entity).
- `ConstraintProposer` proposing `NOT NULL` where source data is observably nullable.
- Reconciled entity `merge_strategy` contradicting downstream FK `on_delete`.

**Output schema:**

```python
class RepairRoute(BaseModel):
    target_agent: str                  # which specialist re-runs
    reason: str                        # why
    additional_context: dict           # corrected inputs (typed per agent)

class CoherenceReport(BaseModel):
    passed: bool
    issues: list[CrossCuttingIssue]    # typed issue records (for traces, never user-surfaced)
    repair_routes: list[RepairRoute]   # what to do; empty if passed
    escalate_to_user: Optional[ClarificationRequest]  # set if repair can't auto-resolve
```

**Behavior:**

1. If `passed=True`: workspace.ready emits.
2. If `passed=False` and `repair_routes` non-empty: manager applies routes (re-runs target agents with `additional_context`); after re-runs, `CoherenceGate` runs again. Up to **2 repair cycles**.
3. If still failing after 2 cycles: emits `escalate_to_user` (a typed `ClarificationRequest`); manager surfaces to the conversation as `clarification.required` SSE event.
4. The user-facing SSE during repair is neutral: `validation.warning` with copy like *"Refining your workspace..."*. They never see the internal report.

This pattern (gate-driven repair routing) is the **only** acceptable form of repair loops. Specialists do not loop internally beyond their `output_validator → ModelRetry` (max 2 attempts at the agent level). Cross-agent loops live in the manager, driven by `CoherenceGate` routes.

### Pruned from the original list (kept here for traceability and add-back triggers):

| Removed agent | Reason | Add-back trigger |
|---|---|---|
| `IntentClassifier` | UI affordances route intent — refinement panel, ask box, connector flow are distinct. | If we collapse to a unified chat surface. |
| `ConnectorIntrospector` | Mechanical: every connector has `list_tables`/`describe_table`. Naming-hint sub-task folds into `ColumnClassifier`. | Never (deterministic forever). |
| `DashboardComposer` | Deterministic chart-spec emission from `KPIPlanner` output (counter → number, time-series → line, distribution → histogram, comparison → bar). | If users start composing custom dashboards beyond auto-generation. |
| `CriticReviewer` | Replaced by `CoherenceGate` — same intent, sharper contract: internal-only gate, never a user surface. | n/a (renamed). |
| `ExplanationAuthor` | Lazy on-demand: agent call only fires when user clicks "why is this here?" on a specific artifact. | Never as upfront-batch; always lazy. |
| `ChildVersionAuthor` | Mechanical merge: `parent IR + change_plan → child IR` is typed application of a diff. | If conflicts (e.g., refinement adds something that already exists) need agent reasoning beyond `ChangePlanner`'s scope. |
| `BehaviorPlanner` | Dev convenience for `baseflo testdb` / local-dev demo data; not user-facing. Deferred until customer flow is validated. | When dev-experience surfaces (CLI `testdb`, local-dev sample data, demo seeding) move into scope. |

## 15. Anti-Patterns That Will Fail Code Review

- An agent's prompt that's shorter than 200 words.
- An agent output schema with `Any`, bare `dict`, or `list[dict[str, Any]]`.
- A repair path that silently substitutes deterministic output.
- A `model_name` hardcoded in agent code (must come from `model_routing.py`).
- An agent run that doesn't write a trace.
- A user-context string interpolated into `instructions=` (cache-busting).
- Two specialists collapsed into one agent because "it was easier."
- A keyword check (`if "X" in prompt.lower()`) anywhere in the orchestration path.
