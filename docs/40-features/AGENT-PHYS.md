# `AGENT-PHYS` — PhysicalSchemaArchitect

Status: M1. The compositor that turns reconciled entities + cardinalities + constraints into the unified `SchemaIR` the rest of the system consumes.

---

## 1. Overview

`PhysicalSchemaArchitect` is the agent that takes the outputs of `EntityReconciler`, `CardinalityResolver`, and `ConstraintProposer` and composes the final, deterministically-validatable `SchemaIR`. It owns physical decisions: table names (snake_case business words), column names, primary keys, indexes-worth-declaring, and the precise shape that maps cleanly to the DDL compiler. It does not invent business semantics — those came from upstream agents — but it does decide table layout, column ordering for readability, index strategy, and minor-unit physical types for money.

This is the last semantic agent before the DDL compiler. After this, deterministic compilers take over: DDL emission, admin-UI spec, SDK codegen, KPI SQL, audit-log scaffolding.

## 2. High-Level Design

```
┌──────────────────────┐    ┌────────────────────────┐    ┌───────────────────────┐
│ EntityReconciliation │    │ CardinalityResolution  │    │ ConstraintProposal    │
│ Plan                 │    │ Plan                   │    │                       │
└─────────────┬────────┘    └────────────┬───────────┘    └───────────┬───────────┘
              │                          │                            │
              └──────────────────────────┼────────────────────────────┘
                                         │
                                         ▼
                          ┌──────────────────────────┐
                          │ PhysicalSchemaArchitect  │
                          │ (model_tier: reasoning)  │
                          └────────────┬─────────────┘
                                       │
                                       ▼
                          ┌──────────────────────────┐
                          │       SchemaIR           │
                          └────────────┬─────────────┘
                                       │
                  ┌────────────────────┼────────────────────────┐
                  ▼                    ▼                        ▼
            DDL Compiler         Admin UI Spec           KPIPlanner input
            (Postgres)           (TanStack render)       (downstream agent)
```

## 3. Low-Level Design

### 3.1 Module Layout

```
server/app/agents/specialists/physical_schema_architect/
├── __init__.py
├── agent.py
├── prompt.py
├── types.py
└── tests/
    ├── test_validator.py
    ├── test_with_test_model.py
    └── fixtures/
        ├── single_source_ecommerce.json
        ├── multi_source_yoga_studio.json
        └── refinement_add_wishlists.json
```

### 3.2 Key Types

```python
# types.py
class PhysicalSchemaArchitectInput(BaseModel):
    reconciliation_plan: EntityReconciliationPlan         # from AGENT-ENT
    cardinalities: list[CardinalityDecision]              # from AGENT-CARD
    constraints: list[ConstraintProposal]                 # from AGENT-CONS
    parent_ir: SchemaIR | None = None                     # for refinement: parent version

class PhysicalSchemaArchitectOutput(BaseModel):
    schema_ir: SchemaIR                                   # the final composed IR
    composition_notes: list[str]                          # decisions like "Renamed Stripe.customers to customer_billing because customers was reserved by reconciled view"
```

The output is just a `SchemaIR` plus rationale. The agent's job is composition: take typed proposals from earlier specialists and lay them out.

### 3.3 The Prompt

≥250 words. Sections:

1. **Persona**: *"You are Baseflo's senior physical schema architect. You compose the final unified data model from reconciled entities, resolved cardinalities, and proposed constraints."*

2. **Job**: detailed paragraph emphasizing composition over invention. *"You do not invent entities, money handling, or status semantics — those came from earlier agents. You decide physical layout: table names, column ordering for readability, index choice, primary-key materialization."*

3. **Inputs**: typed shapes summarized.

4. **Output schema**: `SchemaIR` reference.

5. **Rules**:
   - Table names are snake_case plurals derived from the entity's `canonical_name` (`Customer` → `customers`).
   - Reconciled entities become first-class tables; unreconciled tables retain their source-prefixed names if collision risk (`stripe_charges` not `charges` if Notion also has a `charges` table).
   - Money columns are BIGINT minor-unit + sibling `*_currency` CHAR(3).
   - Status columns are TEXT with CHECK constraint (the constraint comes from `ConstraintProposer`; you compose it into the IR).
   - PII columns inherit `pii_masked_by_default = true` from `ColumnClassifier`.
   - Primary keys are UUIDv7 (`uuid` physical type) by default; only use composite or inherited keys when `EntityReconciler.primary_key_strategy` says so.
   - Index choice: indexes on every FK column, `(organization_id, created_at DESC)` for activity feeds, plus any explicit constraint-driven uniques. Do not speculatively index.
   - For refinement (`parent_ir != None`): preserve all parent table/column ids that don't conflict with the change plan; add new tables/columns; never silently rename.

6. **Forbidden**:
   - Do not invent tables not present in `reconciliation_plan` or required by a `CardinalityDecision` join table.
   - Do not output SQL.
   - Do not place foreign keys against the cardinality direction (`1..*` puts FK on the many-side; the validator will catch but the agent must follow).
   - Do not use generic table names (`events`, `data`, `meta`) — every table is a specific business concept.

7. **Examples**: one single-source case, one multi-source case, one refinement case.

### 3.4 The Output Validator

```python
@agent.output_validator
async def validate(ctx: RunContext[AgentDeps], out: PhysicalSchemaArchitectOutput) -> PhysicalSchemaArchitectOutput:
    ir = out.schema_ir

    # Run every IR validator from engines/schema/compatibility.py — same checks the compiler will use
    report = ir_compatibility.validate(ir)
    if not report.passed:
        # Compose a structured ModelRetry message listing all violations
        raise ModelRetry(f"IR failed validation: {report.summary()}")

    # Every entity in the reconciliation plan has a corresponding table
    plan_entities = {e.canonical_table_name for e in ctx.deps.reconciliation_plan.reconciled_entities}
    ir_tables = {t.name for t in ir.tables}
    missing = plan_entities - ir_tables
    if missing:
        raise ModelRetry(f"Missing tables for reconciled entities: {missing}")

    # Cardinality direction respected: 1..* puts FK on the many-side
    for rel in ir.relationships:
        cardinality_decision = next((c for c in ctx.deps.cardinalities if c.matches(rel)), None)
        if cardinality_decision and not cardinality_decision.fk_on_many_side(rel):
            raise ModelRetry(f"Relationship {rel.name} places FK on the wrong side for cardinality {rel.cardinality}.")

    # Money columns are BIGINT minor units with explicit currency evidence
    for tbl in ir.tables:
        for col in tbl.columns:
            if col.semantic_type == SemanticType.MONEY:
                if col.physical_type != PhysicalType.BIGINT or not col.is_minor_unit:
                    raise ModelRetry(f"Money column {tbl.name}.{col.name} must be BIGINT minor-unit.")
                if not col.currency:
                    raise ModelRetry(f"Money column {tbl.name}.{col.name} must carry an ISO currency or explicit assumption.")

    # PII columns are masked by default
    for tbl in ir.tables:
        for col in tbl.columns:
            if str(col.semantic_type).startswith("pii_") and not col.pii_masked_by_default:
                raise ModelRetry(f"PII column {tbl.name}.{col.name} must have pii_masked_by_default=True.")

    return out
```

The validator runs the **same** structural checks the deterministic compiler will run. If the agent produces something the compiler will reject, the validator catches it first and re-prompts — saving one round-trip and providing better error context.

## 4. Design Patterns Applied

| Pattern | Where | Why |
|---|---|---|
| **Compositor** | The agent's role: combine typed inputs from three upstream agents | Pure composition; no semantic invention. |
| **Validator-Driven Repair** | `@agent.output_validator` raises `ModelRetry` with structured violations | Catches structural issues before the compiler does. |
| **Reuse of Compiler Checks** | Validator runs `ir_compatibility.validate()` from `engines/schema/compatibility.py` | One source of truth for what's valid; same code, two contexts. |

## 5. Test Plan

- **Validator tests**: every IR violation type fires the right `ModelRetry`.
- **TestModel-driven tests**: canonical fixture inputs → expected `SchemaIR` outputs.
- **Refinement test**: parent IR + change plan input → child IR preserves parent ids and adds new tables.
- **Cardinality direction test**: malformed agent output (FK on wrong side) → validator catches.
- **Compiler equivalence test**: every test case's output IR survives the deterministic compiler unchanged (round-trip: composer → validator → compiler succeeds).
- **Coverage**: 92%.

## 6. Error Codes

| Code | Condition | Recovery |
|---|---|---|
| `BF-AGENT-PHYS-001` | Output validation failed after retries | Manager escalates tier; if still failing, surfaces as `BF-AGENT-005`. |
| `BF-AGENT-PHYS-002` | Missing table for reconciled entity | Validator raises; agent re-runs with explicit reminder. |
| `BF-AGENT-PHYS-003` | FK placed against cardinality direction | Validator raises; agent re-runs. |
| `BF-AGENT-PHYS-004` | Money column not BIGINT minor-unit with currency evidence | Validator raises; agent re-runs. |
| `BF-AGENT-PHYS-005` | Generic / forbidden table name (`events`, `data`, `meta`, etc.) | Validator raises with the offending name. |

## 7. Dependencies

- [`IR-CORE`](IR-CORE.md) — produces `SchemaIR`; uses `ir_compatibility` validators.
- [`AGENT-ENT`](AGENT-ENT.md) — input.
- `AGENT-CARD` — input.
- `AGENT-CONS` — input.

## 8. Milestone

- **M1:** single-source path; emits a clean unified IR for ceramics-shop / yoga-studio fixtures.
- **M2:** multi-source composition exercises the reconciliation plan; refinement parent-IR preservation tested end-to-end.
- **M3+:** flywheel — when the compiler or `CoherenceGate` finds patterns the architect repeatedly gets wrong, examples accumulate in the prompt's example bank.
