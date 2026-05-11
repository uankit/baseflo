# `AGENT-CHG` — ChangePlanner

Status: M2. Produces the typed delta against the parent IR. Last semantic agent in the refinement graph; deterministic compiler applies the plan to materialize the child version.

---

## 1. Overview

`ChangePlanner` reads `RefinementIntent`, `ImpactSummary`, and parent `SchemaIR` + KPIs, and produces a typed `ChangePlan` — the structured diff the deterministic version compiler will apply to create the immutable child `SchemaIR`. This is the agent that decides *exactly* what to add, remove, rename, or modify at the IR level. It is the last semantic call before code emits new IR/SDK/admin/migrations.

The plan must be *mechanically applicable* — every operation references real names, every added artifact has all required fields, and applying the plan to the parent must yield a valid child IR. The deterministic merge (`apply_diff` in `engines/schema/transforms.py`) is dumb on purpose; the smartness is here.

## 2. High-Level Design

```
RefinementIntent + ImpactSummary + parent_ir + parent_kpis
                    │
                    ▼
        ┌──────────────────────────┐
        │  ChangePlanner           │
        │  (model_tier: reasoning) │
        └────────────┬─────────────┘
                     │
                     ▼
                ChangePlan (typed)
                     │
                     ▼
       deterministic apply_diff(parent_ir, plan) → child_ir
                     │
                     ▼
              CoherenceGate runs on child_ir
              (child must pass before commit)
```

## 3. Low-Level Design

### 3.1 Module Layout

```
server/app/agents/specialists/change_planner/
├── __init__.py
├── agent.py
├── prompt.py
├── types.py
└── tests/
    ├── test_validator.py
    ├── test_with_test_model.py
    ├── test_apply_diff_round_trip.py     # property: apply(parent, plan) → child must be valid IR
    └── fixtures/
        ├── add_wishlists_plan.json
        ├── rename_customers_plan.json
        ├── split_orders_plan.json
        └── modify_status_enum_plan.json
```

### 3.2 Key Types

```python
class ChangeOp(StrEnum):
    ADD_TABLE                 = "add_table"
    REMOVE_TABLE              = "remove_table"
    RENAME_TABLE              = "rename_table"
    ADD_COLUMN                = "add_column"
    REMOVE_COLUMN             = "remove_column"
    RENAME_COLUMN             = "rename_column"
    MODIFY_COLUMN_TYPE        = "modify_column_type"
    MODIFY_COLUMN_NULLABILITY = "modify_column_nullability"
    ADD_RELATIONSHIP          = "add_relationship"
    REMOVE_RELATIONSHIP       = "remove_relationship"
    MODIFY_CARDINALITY        = "modify_cardinality"
    ADD_INDEX                 = "add_index"
    REMOVE_INDEX              = "remove_index"
    ADD_CHECK_CONSTRAINT      = "add_check_constraint"
    REMOVE_CHECK_CONSTRAINT   = "remove_check_constraint"
    ADD_KPI                   = "add_kpi"
    REMOVE_KPI                = "remove_kpi"
    MODIFY_KPI                = "modify_kpi"

class ChangeOperation(BaseModel):
    op: ChangeOp
    target: str                                       # natural key: table_name | "table.column" | relationship_name | kpi_name
    payload: ChangePayload                            # tagged-union per op (typed)
    rationale: str                                    # trace only

class ChangePayload(BaseModel):
    """Discriminated by op; only the relevant fields populated. Validator enforces."""
    new_name: str | None = None
    table_ir: TableIR | None = None
    column_ir: ColumnIR | None = None
    relationship_ir: RelationshipIR | None = None
    kpi_definition: KPIDefinition | None = None
    new_nullability: bool | None = None
    new_physical_type: PhysicalType | None = None
    new_cardinality: Cardinality | None = None
    constraint: ConstraintProposal | None = None
    index_ir: IndexIR | None = None

class ChangePlannerInput(BaseModel):
    intent: RefinementIntent
    impact: ImpactSummary
    parent_ir: SchemaIR
    parent_kpis: list[KPIDefinition]

class ChangePlan(BaseModel):
    operations: list[ChangeOperation]
    new_assumptions: list[Assumption]                 # explicit assumptions surfaced for the child workspace
    backward_compatible: bool                         # mirrors ImpactSummary; agent must agree or justify divergence
    rationale: str                                    # trace only

class ChangePlannerOutput(BaseModel):
    plan: ChangePlan
```

### 3.3 The Prompt (key rules)

≥300 words. Sections:

1. **Persona**: *"You are Baseflo's change planner. You produce the exact typed delta that turns a parent SchemaIR into a child SchemaIR for a refinement. Your output is mechanically applied; if the plan is wrong, the child IR is wrong."*

2. **Job**: detailed paragraph on producing a complete, applicable plan that honors the user's intent and the impact analysis.

3. **Inputs**: typed shapes summarized.

4. **Output schema**: `ChangePlan` reference.

5. **Rules**:
   - Every operation must have a payload populated for the relevant fields (per `op`).
   - For ADD operations, fully populate the new IR object (all required `TableIR` / `ColumnIR` / `RelationshipIR` / `KPIDefinition` fields). Don't expect downstream agents to fill gaps.
   - For REMOVE operations, the target must exist in `parent_ir` / `parent_kpis`. Validator enforces.
   - For RENAME, both `target` (old name) and `payload.new_name` (new name) must be set; new name must not collide with anything else.
   - For MODIFY, only modify what the impact summary says is changing — no opportunistic side-edits.
   - Cascading edits: if removing a column referenced by a KPI, you must also produce a `MODIFY_KPI` or `REMOVE_KPI` operation for every affected KPI listed in `ImpactSummary`.
   - Adding new columns to existing tables: must include a `default_value` if the column is `NOT_NULL` and existing rows are present.
   - Adding new tables: must include primary key, audit timestamps (`created_at`/`updated_at`), and at least one user-meaningful column.
   - `backward_compatible` must agree with `ImpactSummary.backward_compatible`. Disagreement requires a written rationale (the impact analyzer may have been wrong).

6. **Forbidden**:
   - Producing operations that target nonexistent names.
   - Leaving payload fields empty for the op type.
   - Adding columns/tables/KPIs not implied by the intent.
   - Removing artifacts not flagged in `ImpactSummary` (no silent collateral).
   - Plan order that's invalid (e.g., REMOVE_TABLE before REMOVE_RELATIONSHIP that references it). The deterministic apply_diff is order-aware, but the plan must be apply-able.
   - Outputting raw SQL.

7. **Examples** — four:
   - Add wishlists: ADD_TABLE(wishlists), ADD_RELATIONSHIP(customers↔wishlists), ADD_RELATIONSHIP(wishlists↔products), ADD_KPI("Wishlist conversion rate"), ADD_INDEX(wishlists.customer_id), ADD_INDEX(wishlists.product_id).
   - Rename customers→clients: RENAME_TABLE; cascading RENAME for every relationship and KPI referencing customers; MODIFY_KPI for affected KPI display names.
   - Split orders into quotes/invoices: REMOVE_TABLE(orders), ADD_TABLE(quotes), ADD_TABLE(invoices), ADD_RELATIONSHIP(quote → invoice optional), MODIFY all KPIs that depended on orders.
   - Add a status to existing customer: ADD_COLUMN(customers.status), ADD_CHECK_CONSTRAINT(check_enum), default_value="active".

### 3.4 The Output Validator

```python
@agent.output_validator
async def validate(ctx: RunContext[AgentDeps], out: ChangePlannerOutput) -> ChangePlannerOutput:
    plan = out.plan
    parent = ctx.deps.parent_ir
    parent_kpi_names = {k.name for k in ctx.deps.parent_kpis}

    # Every operation has the right payload populated for its op
    for op in plan.operations:
        _validate_payload_completeness(op)              # raises ModelRetry on missing field

    # REMOVE/RENAME/MODIFY targets exist
    for op in plan.operations:
        if op.op in REMOVE_OPS or op.op in RENAME_OPS or op.op in MODIFY_OPS:
            if not _target_exists(op, parent, parent_kpi_names):
                raise ModelRetry(f"{op.op} target {op.target} not in parent.")

    # ADD targets do not collide
    new_names = _collect_added_names(plan)
    existing_names = _collect_all_existing(parent, ctx.deps.parent_kpis)
    collisions = new_names & existing_names
    if collisions:
        raise ModelRetry(f"ADD operations collide with existing names: {collisions}")

    # Cascading edits present: every KPI listed BREAKING in impact has a corresponding MODIFY/REMOVE op
    breaking_kpis = {a.identifier for a in ctx.deps.impact.impacted
                     if a.kind == ArtifactKind.KPI and a.severity == ImpactSeverity.BREAKING}
    addressed_kpis = {op.target for op in plan.operations if op.op in (ChangeOp.MODIFY_KPI, ChangeOp.REMOVE_KPI)}
    missing = breaking_kpis - addressed_kpis
    if missing:
        raise ModelRetry(f"BREAKING KPIs not addressed by plan: {missing}")

    # Test apply_diff on a copy: must produce a structurally valid child IR
    try:
        child = transforms.apply_diff(parent, plan)
        report = ir_compatibility.validate(child)
        if not report.passed:
            raise ModelRetry(f"Applied plan produces invalid child IR: {report.summary()}")
    except transforms.ApplyDiffError as e:
        raise ModelRetry(f"Plan does not apply cleanly: {e}")

    return out
```

The "test apply_diff" check is the killer feature: the validator literally applies the proposed plan and validates the result. If the agent produces a plan that breaks, the validator catches it before the manager commits anything. This is the gate that makes refinement safe.

## 4. Design Patterns Applied

| Pattern | Where | Why |
|---|---|---|
| **Command** | `ChangeOperation` is a typed command applied by deterministic `apply_diff` | Idempotent, replayable, auditable. |
| **Discriminated Union** | `ChangePayload` per `ChangeOp` | Type safety; payload validation per op kind. |
| **Validator-Driven Repair** | `@agent.output_validator` includes a *dry-run application* of the plan | Catches non-applicable plans without committing. |
| **Compositor** | Agent assembles operations from intent + impact; deterministic merge applies them | Same shape as `PhysicalSchemaArchitect`. |

## 5. Test Plan

- Validator tests for each `ModelRetry` branch.
- Property test (`test_apply_diff_round_trip.py`):
  - For every fixture, `apply_diff(parent, plan)` produces a child IR.
  - The child IR passes `ir_compatibility.validate()`.
  - The child IR is hash-stable (deterministic merge).
- TestModel-driven: ADD / REMOVE / RENAME / SPLIT / MODIFY each produce the right operation set.
- Cascading test: removing a column referenced by 3 KPIs produces 3 corresponding MODIFY_KPI/REMOVE_KPI operations.
- Coverage: 95% (refinement is high-stakes; bugs here corrupt projects).

## 6. Error Codes

| Code | Condition | Recovery |
|---|---|---|
| `BF-AGENT-CHG-001` | Validation failed after retries | Manager escalates tier. |
| `BF-AGENT-CHG-002` | Operation payload incomplete for op kind | Validator raises. |
| `BF-AGENT-CHG-003` | Target does not exist in parent | Validator raises. |
| `BF-AGENT-CHG-004` | ADD names collide with existing | Validator raises. |
| `BF-AGENT-CHG-005` | BREAKING KPIs not addressed | Validator raises. |
| `BF-AGENT-CHG-006` | apply_diff fails or produces invalid child IR | Validator raises with the IR validation report. |

## 7. Dependencies

[`AGENT-INT`](AGENT-INT.md), [`AGENT-IMP`](AGENT-IMP.md), [`IR-CORE`](IR-CORE.md), [`AGENT-KPI`](AGENT-KPI.md), [`AGENT-PHYS`](AGENT-PHYS.md), `engines/schema/transforms.py` (`apply_diff`).

## 8. Milestone

- **M2**: full implementation; refinement graph end-to-end produces immutable child versions.
- **M3**: rollback (`baseflo versions rollback`) re-applies an inverse plan; the inverse is computed deterministically from the forward plan.
- **M3+**: flywheel — production refinements that fail `apply_diff` validation feed prompt examples for next-iteration training.
