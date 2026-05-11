# `AGENT-CARD` — CardinalityResolver

Status: M1. Decides direction, optionality, ownership, and many-to-many treatment for every relationship in the unified entity set.

---

## 1. Overview

`CardinalityResolver` reads the `EntityReconciliationPlan` (which entities exist) and produces typed `CardinalityDecision`s for each relationship implied by FK candidates and reconciled-entity links. It picks one of `ONE_TO_ONE`, `ONE_TO_MANY`, `MANY_TO_ONE`, `MANY_TO_MANY`; for many-to-many it proposes a join-table; for every relationship it sets optionality (whether either side may be null) and on-delete policy (RESTRICT, CASCADE, SET_NULL).

Wrong cardinality silently breaks joins, doubles aggregations, or destroys data on delete. This is reasoning-tier work.

## 2. High-Level Design

```
EntityReconciliationPlan + ColumnClassifier outputs +
deterministic FK-candidate row-count stats
                         │
                         ▼
              ┌──────────────────────────┐
              │  CardinalityResolver     │
              │  (model_tier: reasoning) │
              └────────────┬─────────────┘
                           │
                           ▼
              list[CardinalityDecision]
                           │
                           ▼
              fed to PhysicalSchemaArchitect
                + CoherenceGate (cross-check)
```

## 3. Low-Level Design

### 3.1 Module Layout

```
server/app/agents/specialists/cardinality_resolver/
├── __init__.py
├── agent.py
├── prompt.py
├── types.py
├── evidence.py            # deterministic helper: row-count distribution per FK candidate
└── tests/
    ├── test_validator.py
    ├── test_with_test_model.py
    └── fixtures/
        ├── customer_orders_one_to_many.json
        ├── product_categories_many_to_many.json
        ├── ambiguous_self_reference.json
        └── optional_vs_required_fk.json
```

### 3.2 Key Types

```python
class FKCandidate(BaseModel):
    name: str
    from_table: str
    from_column: str
    to_table: str
    to_column: str
    semantic_type_from: SemanticType
    semantic_type_to: SemanticType
    distribution: FKDistribution                      # from evidence.py

class FKDistribution(BaseModel):
    """Deterministic helper output: how many distinct values on each side, how often referenced."""
    distinct_from_values: int
    distinct_to_values: int
    nulls_in_from: int
    rows_per_referenced_to: dict[str, int]            # histogram-style; bucketed
    sample_size: int

class CardinalityResolverInput(BaseModel):
    reconciliation_plan: EntityReconciliationPlan
    fk_candidates: list[FKCandidate]                  # from evidence.py

class CardinalityDecision(BaseModel):
    relationship_name: str
    from_table: str
    from_columns: list[str]
    to_table: str
    to_columns: list[str]
    cardinality: Cardinality                          # 1..1 | 1..* | *..1 | *..*
    optional_from: bool
    optional_to: bool
    on_delete: OnDelete                               # RESTRICT | CASCADE | SET_NULL
    join_table_name: str | None = None                # required when cardinality == *..*
    rationale: str                                    # trace only

class CardinalityResolverOutput(BaseModel):
    decisions: list[CardinalityDecision]
```

### 3.3 Evidence-Feeding Helper (`evidence.py`)

```python
async def compute_fk_distributions(
    candidates: list[FKCandidate],
    sample_rows_per_table: dict[str, list[Row]],
) -> list[FKDistribution]:
    """For each FK candidate, count distinct values on each side
    and the per-referenced-target reference frequency. Pure function
    over typed inputs."""
```

The agent sees: *"FK candidate `orders.customer_id → customers.id`: 200 distinct customers, 1,247 distinct orders, average 6.2 orders per customer, 0 nulls in `orders.customer_id`."* The agent decides: *"Many orders per customer; not optional from order side; CASCADE on customer delete probably wrong (preserve order history); SET_NULL safer. Cardinality: `MANY_TO_ONE` (orders→customer)."*

### 3.4 The Prompt (key rules)

- Use `FKDistribution` as evidence. Reasoning examples:
  - `distinct_from == distinct_to` and both ≈ rows → `ONE_TO_ONE`.
  - `rows_per_referenced_to` ≫ 1 on average → `MANY_TO_ONE` from the from-side.
  - Both sides have many references via a bridge table → `MANY_TO_MANY` with explicit join table.
- Optionality: `optional_from = (nulls_in_from > 0)`; `optional_to` rarely true (target should usually exist).
- on_delete:
  - Money-bearing relationships (orders → customer): `SET_NULL` or `RESTRICT` (preserve financial history).
  - Owned relationships (line_items → order): `CASCADE`.
  - Reference relationships (orders → product): `RESTRICT`.
- For `MANY_TO_MANY`, propose a join table named `<entity_a>_<entity_b>` (alphabetical).
- Self-references must declare and explain.

Forbidden:
- Never declare cardinality without `FKDistribution` evidence (or explicit user-supplied constraint).
- Never use `CASCADE` on relationships involving money or audit-relevant data.

### 3.5 The Output Validator

```python
@agent.output_validator
async def validate(ctx: RunContext[AgentDeps], out: CardinalityResolverOutput) -> CardinalityResolverOutput:
    for d in out.decisions:
        # M2M requires join table
        if d.cardinality == Cardinality.MANY_TO_MANY and not d.join_table_name:
            raise ModelRetry(f"{d.relationship_name} is *..* but no join_table_name.")
        # Money-bearing relationships do not CASCADE
        is_money_path = _has_money_columns(ctx.deps.reconciliation_plan, d.from_table) or \
                        _has_money_columns(ctx.deps.reconciliation_plan, d.to_table)
        if is_money_path and d.on_delete == OnDelete.CASCADE:
            raise ModelRetry(f"{d.relationship_name} touches money columns; CASCADE forbidden.")
        # Endpoint columns must exist
        ...
    return out
```

## 4. Design Patterns Applied

| Pattern | Where | Why |
|---|---|---|
| **Evidence-Feeding** | `evidence.py` → `FKDistribution` | Agent decides cardinality from typed row-count facts, never by inspecting raw rows. |
| **Strategy** | `OnDelete` enum + per-relationship choice | Agent picks per case from typed options. |
| **Validator-Driven Repair** | `@agent.output_validator` | Structural enforcement of invariants (M2M ⇒ join table; money path ⇒ no CASCADE). |

## 5. Test Plan

- **Validator tests**: every `ModelRetry` branch fires.
- **Evidence helper tests**: golden fixtures (sample rows → expected `FKDistribution`).
- **TestModel-driven coverage**: each cardinality variant + each on_delete policy + self-reference + ambiguous case.
- **Property test**: every relationship in `EntityReconciliationPlan` produces exactly one decision.
- **Coverage**: 90%.

## 6. Error Codes

| Code | Condition | Recovery |
|---|---|---|
| `BF-AGENT-CARD-001` | Validation failed after retries | Manager escalates tier. |
| `BF-AGENT-CARD-002` | M2M missing join table | Validator raises. |
| `BF-AGENT-CARD-003` | Money path with CASCADE | Validator raises. |
| `BF-AGENT-CARD-004` | Endpoint column missing | Validator raises. |
| `BF-AGENT-CARD-005` | Cardinality declared without `FKDistribution` evidence | Validator raises. |

## 7. Dependencies

- [`AGENT-ENT`](AGENT-ENT.md), [`AGENT-COL`](AGENT-COL.md), [`CONN-FRAMEWORK`](CONN-FRAMEWORK.md), [`IR-CORE`](IR-CORE.md).

## 8. Milestone

- **M1**: single-source implementation (FK candidates within one source).
- **M2**: cross-source FK-candidate handling once `EntityReconciler` reconciles entities across sources.
- **M3+**: flywheel — track production cardinality overrides; re-prompt examples from real corrections.
