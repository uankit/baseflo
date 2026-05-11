# `AGENT-COHE` — CoherenceGate (Internal Terminal Gate)

Status: M1. The only agent in the system whose output is **never** a user-visible artifact. It's the cross-cutting consistency check + repair-routing entry point.

---

## 1. Overview

`CoherenceGate` runs as the terminal node of the data-architect graph, after `KPIPlanner`. It looks at the entire workspace state — unified `SchemaIR`, KPI definitions, reconciliation plan, constraint set — and checks for cross-cutting failures that single-agent validators **cannot** catch:

- A KPI references a column that doesn't exist in the schema.
- Cardinality between reconciled entities is internally consistent across `EntityReconciler` and `CardinalityResolver`.
- Fundamental concept missing (e.g., e-commerce-shaped schema with no order/transaction entity).
- Reconciled entity merge strategy contradicts an FK's `on_delete` policy.
- Constraint proposals contradict observed source-data nullability.

If it passes (`passed=True`), the workspace ships and `workspace.ready` SSE event fires. If it fails, it emits typed `RepairRoute`s telling the manager which specialists to re-run with corrected context. Up to 2 repair cycles, then escalation to `ClarificationAgent` for user input. **The user never sees the gate's report directly** — they see either a clean workspace, a transparent re-run flash ("Refining your workspace…"), or a clarifying question.

This is the only acceptable form of cross-agent loops in the system. Specialists do not loop across each other on their own.

## 2. High-Level Design

```
┌──────────────────────────────────────────────┐
│ Workspace state (after KPIPlanner runs):     │
│   SchemaIR + KPI defs + Reconciliation Plan  │
│   + Constraints + Cardinalities              │
└─────────────────┬────────────────────────────┘
                  │
                  ▼
        ┌──────────────────────────┐
        │  CoherenceGate           │
        │  (model_tier: reasoning) │
        └────────────┬─────────────┘
                     │
                     ▼
        ┌──────────────────────────────────────┐
        │ CoherenceReport                      │
        │   passed: bool                       │
        │   issues: list[CrossCuttingIssue]    │
        │   repair_routes: list[RepairRoute]   │
        │   escalate_to_user: ClarificationRequest? │
        └─────────────┬────────────────────────┘
                      │
              ┌───────┴───────┐
              ▼               ▼
         passed=true    passed=false
              │              │
              ▼              ▼
       workspace.ready    Manager applies routes:
                          re-run target specialist
                          → re-run gate (cycle 2)
                          → if still failing →
                              escalate to user
```

## 3. Low-Level Design

### 3.1 Module Layout

```
server/app/agents/specialists/coherence_gate/
├── __init__.py
├── agent.py
├── prompt.py
├── types.py
├── checks.py            # Deterministic pre-checks the agent uses as evidence (NOT decisions)
└── tests/
    ├── test_validator.py
    ├── test_with_test_model.py
    └── fixtures/
        ├── coherent_workspace.json
        ├── kpi_references_missing_column.json
        ├── cardinality_contradiction.json
        ├── missing_fundamental_concept.json
        └── on_delete_vs_merge_strategy_conflict.json
```

### 3.2 Key Types

```python
# types.py
class CoherenceGateInput(BaseModel):
    schema_ir: SchemaIR
    kpi_definitions: list[KPIDefinition]
    reconciliation_plan: EntityReconciliationPlan
    cardinalities: list[CardinalityDecision]
    constraints: list[ConstraintProposal]
    deterministic_findings: list[DeterministicFinding]   # see §3.4

class IssueSeverity(StrEnum):
    BLOCKING  = "blocking"     # cannot ship
    WARNING   = "warning"      # ships with surfaced assumption

class CrossCuttingIssue(BaseModel):
    severity: IssueSeverity
    category: IssueCategory                              # KPI_COLUMN_MISSING | CARDINALITY_INCONSISTENT | FUNDAMENTAL_CONCEPT_MISSING | MERGE_STRATEGY_CONFLICT | CONSTRAINT_VS_SOURCE_DATA | OTHER
    description: str                                     # plain English; goes into trace, never UI
    affected_artifacts: list[str]                        # "schema:tables.orders" | "kpi:revenue" | "relationship:orders↔customers"

class RepairRoute(BaseModel):
    target_agent: str                                    # "ColumnClassifier" | "EntityReconciler" | ...
    reason: str
    additional_context: dict                             # typed payload merged into target's input
    affected_artifacts: list[str]

class ClarificationRequest(BaseModel):
    questions: list[ClarificationQuestion]               # max 3; plain business language
    blocking: bool = True

class CoherenceReport(BaseModel):
    passed: bool
    issues: list[CrossCuttingIssue]
    repair_routes: list[RepairRoute]                     # populated only when passed=False
    escalate_to_user: ClarificationRequest | None = None
    rationale: str                                       # for traces only
```

### 3.3 The Prompt

≥300 words. Sections:

1. **Persona**: *"You are Baseflo's coherence gate. You are not a critic the user reads. You are an internal quality gate that runs after every other architect agent. Your job is to find cross-cutting inconsistencies that single-agent validators cannot."*

2. **Job**: detailed paragraph on what cross-cutting means; emphasize the agent does NOT re-decide things upstream agents already decided — it checks for inconsistencies *between* their outputs.

3. **Inputs**: explanation of `deterministic_findings` (pre-computed structural checks the agent should treat as facts, not opinions).

4. **Output schema**: `CoherenceReport` reference.

5. **Rules**:
   - Always start by reviewing `deterministic_findings`. They are facts.
   - For each fact, decide whether it's BLOCKING or WARNING.
   - For BLOCKING issues, emit a `RepairRoute` naming a specific specialist to re-run with corrected `additional_context`.
   - Use these specialist mappings:
     - KPI references missing column → `KPIPlanner` re-run with `additional_context = {"available_columns": [...]}`
     - Cardinality inconsistent → `CardinalityResolver` re-run with `additional_context = {"contradiction": "..."}`
     - Fundamental concept missing → `EntityReconciler` re-run with `additional_context = {"required_concept": "..."}`
     - Merge strategy contradicts FK on_delete → `EntityReconciler` re-run
     - Constraint contradicts source-data nullability → `ConstraintProposer` re-run
   - WARNINGs ship; convert to assumptions surfaced on the workspace.
   - If after considering all evidence you cannot route a repair (the failure requires user input), populate `escalate_to_user` with a clear, plain-English question.
   - You may NOT emit more than 5 repair routes per run. If more, prioritize blocking ones; warn the rest.

6. **Forbidden**:
   - Do not re-classify columns, re-compose schema, or invent KPIs. You only assess.
   - Do not produce text the user will see directly — `description` and `rationale` go to traces only.
   - Do not produce ambiguous routes. Every route names exactly one specialist and one corrected context.
   - Do not pass when blocking issues exist.

7. **Examples**:
   - Coherent workspace → `passed=True, issues=[], repair_routes=[]`.
   - KPI references missing column → `passed=False, repair_route(KPIPlanner)`.
   - Fundamental concept missing → `passed=False, escalate_to_user(...)`.

### 3.4 `checks.py` — Deterministic Pre-Computation

The orchestrator runs these structural checks **before** the agent runs and feeds them as `deterministic_findings`. These are not decisions; they are typed facts:

```python
def check_kpi_columns_exist(ir: SchemaIR, kpis: list[KPIDefinition]) -> list[DeterministicFinding]:
    """For each KPI's source columns, check they exist in the IR."""
    ...

def check_relationship_endpoints_exist(ir: SchemaIR) -> list[DeterministicFinding]:
    """For each relationship, check both endpoint tables and columns exist."""
    ...

def check_cardinality_internal_consistency(
    ir: SchemaIR,
    cardinalities: list[CardinalityDecision],
    plan: EntityReconciliationPlan,
) -> list[DeterministicFinding]:
    """Cross-check IR relationship cardinality matches CardinalityResolver decisions."""
    ...

def check_pii_masking_propagation(ir: SchemaIR) -> list[DeterministicFinding]:
    """Every PII column has masking enabled."""
    ...

def check_money_minor_unit_consistency(ir: SchemaIR) -> list[DeterministicFinding]:
    """Every money column is BIGINT minor-unit + sibling currency."""
    ...
```

The agent sees facts, not "scores." It then decides severity and routing.

### 3.5 The Output Validator

```python
@agent.output_validator
async def validate(ctx: RunContext[AgentDeps], out: CoherenceReport) -> CoherenceReport:
    # Internal consistency: passed iff no BLOCKING issues
    has_blocking = any(i.severity == IssueSeverity.BLOCKING for i in out.issues)
    if has_blocking and out.passed:
        raise ModelRetry("Cannot pass with BLOCKING issues.")
    if not has_blocking and not out.passed:
        raise ModelRetry("No BLOCKING issues but passed=False; check rationale.")

    # If not passed, must have at least one repair_route OR escalate_to_user
    if not out.passed and not out.repair_routes and not out.escalate_to_user:
        raise ModelRetry("Failed gate must specify at least one repair_route or escalate_to_user.")

    # Repair routes target known specialists
    valid_specialists = AgentRegistry.list_specialist_names()
    for r in out.repair_routes:
        if r.target_agent not in valid_specialists:
            raise ModelRetry(f"RepairRoute targets unknown specialist: {r.target_agent}")

    # Max 5 repair routes
    if len(out.repair_routes) > 5:
        raise ModelRetry("Max 5 repair routes per run; prioritize blocking issues.")

    # Escalation has at most 3 questions
    if out.escalate_to_user and len(out.escalate_to_user.questions) > 3:
        raise ModelRetry("Max 3 clarification questions.")

    return out
```

### 3.6 Manager Loop (in orchestration)

The manager applies the gate's output:

```python
# server/app/orchestration/sagas/architect.py
MAX_REPAIR_CYCLES = 2

async def run_data_architect_graph(ctx: RunContext) -> WorkspaceState:
    state = await run_specialists(ctx)        # ColumnClassifier → ... → KPIPlanner

    for cycle in range(1 + MAX_REPAIR_CYCLES):
        deterministic = compute_deterministic_findings(state)
        report = await coherence_gate.run(CoherenceGateInput(**state, deterministic_findings=deterministic))

        if report.passed:
            return state                        # workspace.ready

        if report.escalate_to_user:
            await emit_clarification(report.escalate_to_user)
            return state.with_status(NEEDS_CLARIFICATION)

        if cycle == MAX_REPAIR_CYCLES:
            raise BasefloError(error_code="BF-COHERENCE-001", message="Repair did not converge.")

        await emit_sse_event("validation.warning", payload={"copy": "Refining your workspace..."})
        for route in report.repair_routes:
            specialist = AgentRegistry.get(route.target_agent)
            corrected_input = merge_context(state, route.additional_context)
            new_output = await specialist.run(corrected_input)
            state = state.replace(target=route.target_agent, output=new_output)
```

## 4. Design Patterns Applied

| Pattern | Where | Why |
|---|---|---|
| **Gate** | `CoherenceGate` itself; the only cross-agent loop entry | Single source of truth for "is the workspace ready?" |
| **Saga** | Manager's repair loop in `orchestration/sagas/architect.py` | Multi-step, with bounded compensation cycles. |
| **Specification** | `checks.py` deterministic findings | Each check is a typed predicate; agent reasons over typed facts. |
| **Strategy** | Repair-route routing per issue category | Each category maps to a specialist; mapping is data, not code. |

## 5. Test Plan

- **Validator tests**: every `ModelRetry` branch fires under the wrong shape.
- **Deterministic-check tests**: each `checks.py` function tested against fixtures.
- **TestModel-driven coverage**:
  - Coherent fixture → `passed=True`.
  - KPI-references-missing-column fixture → `passed=False`, route targets `KPIPlanner`.
  - Cardinality-contradiction fixture → route targets `CardinalityResolver`.
  - Fundamental-concept-missing fixture → escalates to user.
- **Manager-loop integration test** (in `orchestration/tests/`):
  - Cycle 1 fails, repair re-runs the right specialist, cycle 2 passes → workspace.ready emitted.
  - Both cycles fail → `BF-COHERENCE-001` raised; user-visible error.
  - Escalation fires → `clarification.required` SSE event with the agent's questions.
- **Coverage**: 95% (this is the system's last quality gate).

## 6. Error Codes

| Code | Condition | Recovery |
|---|---|---|
| `BF-COHERENCE-001` | Repair did not converge after `MAX_REPAIR_CYCLES` | Surface as terminal failure to user with neutral copy + retry path. |
| `BF-COHERENCE-002` | Output validation failed after agent retries | Manager escalates tier; if still failing, surfaces as `BF-AGENT-005`. |
| `BF-COHERENCE-003` | Repair route targets unknown specialist | Validator raises; agent re-runs. |
| `BF-COHERENCE-004` | More than 5 repair routes | Validator raises; agent re-runs with prioritization hint. |
| `BF-COHERENCE-005` | Escalation has more than 3 questions | Validator raises; agent re-runs. |

## 7. Dependencies

- [`IR-CORE`](IR-CORE.md) — input.
- [`AGENT-ENT`](AGENT-ENT.md) — input.
- [`AGENT-PHYS`](AGENT-PHYS.md) — input.
- All other architect specialists — repair routing targets them.

## 8. Milestone

- **M1:** initial implementation; `deterministic_findings` cover the 5 main check categories; manager loop wires repair routing for fixture-level coverage.
- **M2:** richer `IssueCategory` enum as we observe new failure modes in practice; example bank in prompt grows from real production traces.
- **M3+:** flywheel — production failures that the gate catches feed `feedback_events`; categories that recur become deterministic checks (move out of agent reasoning into structural pre-computation), shrinking the agent's surface and improving determinism.
