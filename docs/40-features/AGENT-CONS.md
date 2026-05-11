# `AGENT-CONS` — ConstraintProposer

Status: M1. Proposes keys, uniqueness, status enums, money minor units, nullability, and timestamp constraints for every reconciled entity.

---

## 1. Overview

`ConstraintProposer` reads the reconciled entities + classified columns + cardinality decisions and produces typed constraint proposals: primary keys, unique indexes, CHECK constraints (status enum sets, positive money values, valid date ranges), nullability per column, default values, audit timestamps. The deterministic schema compiler turns these into actual DDL; the agent's job is to *decide which constraints are appropriate given the data*.

Wrong constraints either over-restrict (legitimate business cases blocked) or under-restrict (bad data leaks in). Reasoning-tier.

## 2. High-Level Design

```
EntityReconciliationPlan + ColumnClassifier outputs +
CardinalityDecisions + deterministic ColumnObservations
                         │
                         ▼
              ┌──────────────────────────┐
              │  ConstraintProposer      │
              │  (model_tier: reasoning) │
              └────────────┬─────────────┘
                           │
                           ▼
              list[ConstraintProposal]
                           │
                           ▼
              fed to PhysicalSchemaArchitect
```

## 3. Low-Level Design

### 3.1 Module Layout

```
server/app/agents/specialists/constraint_proposer/
├── __init__.py
├── agent.py
├── prompt.py
├── types.py
├── evidence.py            # deterministic helper: ColumnObservations
└── tests/
    ├── test_validator.py
    ├── test_with_test_model.py
    └── fixtures/
        ├── ecommerce_constraints.json
        ├── observed_nullable_actual_required.json
        ├── status_enum_inference.json
        └── money_currency_consistency.json
```

### 3.2 Key Types

```python
class ColumnObservations(BaseModel):
    """Deterministic facts per column: nullability rate, distinct count,
    most-frequent-value frequency, observed range (numeric), observed enum (small finite distinct)."""
    table_name: str
    column_name: str
    sample_size: int
    null_rate: float                                  # 0.0..1.0
    distinct_count: int
    most_frequent: str | int | float | bool | None
    most_frequent_rate: float
    observed_range: tuple[float, float] | None        # for numeric
    observed_enum: list[str] | None                   # for STATUS-classified columns

class ConstraintProposerInput(BaseModel):
    reconciliation_plan: EntityReconciliationPlan
    classified_sources: list[ClassifiedSource]
    cardinalities: list[CardinalityDecision]
    observations: list[ColumnObservations]

class ConstraintKind(StrEnum):
    PRIMARY_KEY        = "primary_key"
    UNIQUE             = "unique"
    NOT_NULL           = "not_null"
    CHECK_ENUM         = "check_enum"
    CHECK_RANGE        = "check_range"
    CHECK_POSITIVE     = "check_positive"
    DEFAULT            = "default"
    AUDIT_TIMESTAMP    = "audit_timestamp"            # created_at / updated_at trigger pair
    CURRENCY_CONSIST   = "currency_consist"           # money_minor + money_currency must agree

class ConstraintProposal(BaseModel):
    kind: ConstraintKind
    table_name: str
    columns: list[str]
    enum_values: list[str] | None = None              # for CHECK_ENUM
    range_min: float | None = None                    # for CHECK_RANGE
    range_max: float | None = None
    default_value: str | int | float | bool | None = None
    rationale: str

class ConstraintProposerOutput(BaseModel):
    proposals: list[ConstraintProposal]
```

### 3.3 Evidence-Feeding Helper

```python
def compute_column_observations(
    plan: EntityReconciliationPlan,
    sample_rows: dict[str, list[Row]],
) -> list[ColumnObservations]:
    """For every column across all reconciled-entity contributing tables,
    compute null_rate, distinct_count, most_frequent (+rate), observed_range
    (numeric), observed_enum (low-cardinality STATUS-classified)."""
```

Agent reads facts. Examples of agent reasoning:
- `null_rate == 0.0` and column is `IDENTITY` → propose `NOT_NULL` and PK candidate.
- `distinct_count / sample_size > 0.99` and `IDENTITY` → propose `UNIQUE`.
- `STATUS` column with `observed_enum = ["active", "paused", "cancelled"]` → propose `CHECK_ENUM` with those values.
- `MONEY` column with `observed_range = (0, 999999)` → propose `CHECK_POSITIVE`.
- `null_rate == 0.0` but `optional_from == True` (per cardinality) → propose `NOT_NULL` and surface as assumption (sample data may not reflect future behavior).

### 3.4 The Prompt (key rules)

- Every reconciled entity must have exactly one `PRIMARY_KEY` proposal.
- Every `IDENTITY` column with `null_rate == 0` and `distinct_count / sample_size > 0.99` is a PK candidate; pick the most stable.
- Every `STATUS` column gets a `CHECK_ENUM` constraint with `observed_enum`. If observed_enum is empty, surface as assumption ("status values not yet observable").
- Every `MONEY` column gets `CHECK_POSITIVE` and `CURRENCY_CONSIST` (paired with sibling `*_currency`).
- Every entity gets `AUDIT_TIMESTAMP` proposals (`created_at`, `updated_at`) — even when source data lacks them; deterministic compiler emits triggers.
- For columns with `null_rate > 0.0`, do not propose `NOT_NULL` — this is the source of `BF-AGENT-CONS-005` if violated.

Forbidden:
- Proposing `NOT_NULL` when `null_rate > 0.0` in observations.
- Proposing `CHECK_ENUM` without `observed_enum` evidence.
- Proposing `UNIQUE` when distinct rate < 0.95 in observations.
- Inventing constraint values (default values must come from observed-most-frequent or be `null`).

### 3.5 The Output Validator

Cross-cutting structural checks; runs the same validators that the IR compiler will run, plus constraint-specific ones (`NOT_NULL` only with `null_rate == 0`; `UNIQUE` only with high distinct rate; `CHECK_ENUM` only with observed enum).

## 4. Design Patterns Applied

| Pattern | Where | Why |
|---|---|---|
| **Evidence-Feeding** | `evidence.py` → `ColumnObservations` | Agent reasons over typed observations, never raw rows. |
| **Specification** | Each `ConstraintKind` is a typed predicate the compiler later applies | Composable, testable. |
| **Validator-Driven Repair** | `@agent.output_validator` | Catches contradictions between observations and proposals. |

## 5. Test Plan

- **Validator tests**: every `ModelRetry` branch.
- **Evidence helper tests**: golden fixtures.
- **TestModel-driven**: each `ConstraintKind` exercised; conflicts (NOT_NULL vs observed nulls) detected.
- **Property test**: every reconciled entity has exactly one PK; every STATUS column has CHECK_ENUM with non-empty values.
- **Coverage**: 90%.

## 6. Error Codes

| Code | Condition | Recovery |
|---|---|---|
| `BF-AGENT-CONS-001` | Validation failed after retries | Manager escalates tier. |
| `BF-AGENT-CONS-002` | Entity missing PK proposal | Validator raises. |
| `BF-AGENT-CONS-003` | Status column missing CHECK_ENUM | Validator raises. |
| `BF-AGENT-CONS-004` | Money column missing CURRENCY_CONSIST | Validator raises. |
| `BF-AGENT-CONS-005` | NOT_NULL proposed where observations show nulls | Validator raises. |
| `BF-AGENT-CONS-006` | UNIQUE proposed with low distinct rate | Validator raises. |
| `BF-AGENT-CONS-007` | CHECK_ENUM proposed without observed_enum | Validator raises. |

## 7. Dependencies

[`AGENT-ENT`](AGENT-ENT.md), [`AGENT-COL`](AGENT-COL.md), [`AGENT-CARD`](AGENT-CARD.md), [`IR-CORE`](IR-CORE.md), [`CONN-FRAMEWORK`](CONN-FRAMEWORK.md).

## 8. Milestone

- **M1**: full implementation; constraint proposals feed `PhysicalSchemaArchitect`.
- **M2**: cross-source observation aggregation (a column observed nullable in one source but required in another → surface as `Ambiguity` for the user, not an automatic NOT_NULL).
- **M3+**: flywheel from production override events.
