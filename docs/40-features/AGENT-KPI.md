# `AGENT-KPI` — KPIPlanner

Status: M1. Decides which business questions the unified schema can answer, with what grain, and surfaces explicit assumptions. Drives the analytics tab and the daily digest.

---

## 1. Overview

`KPIPlanner` reads the unified `SchemaIR` and produces a typed list of `KPIDefinition`s — what to measure, at what grain, with what filters and assumptions. The deterministic compiler turns these into runnable SQL (executed against DuckDB or the data plane), event-taxonomy entries, dashboard chart specs, and daily-digest sections.

Wrong KPIs mean: silent grain bugs (double-counting), misleading numbers, or the analytics tab is an empty echo of the schema. Reasoning-tier.

The agent picks KPIs answerable by the schema. It does **not** propose KPIs the schema can't compute. It does **not** invent data; if the schema lacks order timestamps, it doesn't propose "orders per week."

## 2. High-Level Design

```
SchemaIR + EntityReconciliationPlan + sample row counts
                    │
                    ▼
        ┌──────────────────────────┐
        │  KPIPlanner              │
        │  (model_tier: reasoning) │
        └────────────┬─────────────┘
                     │
                     ▼
              list[KPIDefinition]
                     │
              ┌──────┴──────┐
              ▼             ▼
       deterministic      CoherenceGate
       chart-spec         cross-checks
       emission           (KPI ↔ schema columns)
              │
              ▼
       Analytics tab + Daily digest
```

## 3. Low-Level Design

### 3.1 Module Layout

```
server/app/agents/specialists/kpi_planner/
├── __init__.py
├── agent.py
├── prompt.py
├── types.py
├── evidence.py            # SchemaCapability: which KPI types are answerable from which tables
└── tests/
    ├── test_validator.py
    ├── test_with_test_model.py
    └── fixtures/
        ├── ecommerce_kpis.json
        ├── booking_kpis.json
        ├── community_kpis.json
        ├── insufficient_schema.json
        └── multi_grain_revenue.json
```

### 3.2 Key Types

```python
class SchemaCapability(BaseModel):
    """Deterministic helper output: what the schema can answer, structurally."""
    has_money_column: bool
    money_tables: list[str]
    has_status_with_completion: bool                  # status enum contains "completed" / "successful" / etc.
    has_temporal_column: bool
    temporal_tables: list[str]
    has_geographic: bool
    has_active_user_concept: bool
    has_customer_entity: bool
    candidate_event_tables: list[str]                 # tables with timestamps + status (event-shaped)

class KPIKind(StrEnum):
    COUNTER             = "counter"                   # single number; "Total orders today"
    TIME_SERIES         = "time_series"               # over time
    DISTRIBUTION        = "distribution"              # histogram
    COMPARISON          = "comparison"                # bar/segmented
    FUNNEL              = "funnel"                    # multi-stage
    COHORT              = "cohort"                    # retention by acquisition cohort
    TOP_N               = "top_n"                     # ranked list

class KPIGrain(BaseModel):
    """One row per ___ — the grain at which the metric is computed."""
    description: str                                  # "one row per order"
    table: str
    deduplication_columns: list[str]                  # to prevent double-counting on joins

class KPIDefinition(BaseModel):
    name: str = Field(min_length=2, max_length=80)    # "Revenue this week"
    description: str                                  # one sentence; user-facing
    kind: KPIKind
    grain: KPIGrain
    formula: KPIFormula                               # typed formula tree (no raw SQL strings)
    time_dimension: ColumnRef | None = None           # for TIME_SERIES, COHORT
    breakdown_dimension: ColumnRef | None = None      # for COMPARISON, TOP_N
    filters: list[KPIFilter]
    assumptions: list[str]                            # "Refunds excluded from revenue"
    rationale: str                                    # trace only

class KPIFormula(BaseModel):
    """Typed formula tree, never a string."""
    op: KPIOp                                         # SUM | COUNT | COUNT_DISTINCT | AVG | RATIO | ...
    column: ColumnRef | None = None                   # for SUM/AVG/COUNT_DISTINCT
    numerator: 'KPIFormula' | None = None             # for RATIO
    denominator: 'KPIFormula' | None = None
    distinct: bool = False

class ColumnRef(BaseModel):
    table: str
    column: str

class KPIFilter(BaseModel):
    column: ColumnRef
    op: FilterOp                                      # EQ | NE | IN | NOT_IN | GTE | LTE | BETWEEN
    value: str | int | float | list

class KPIPlannerOutput(BaseModel):
    kpis: list[KPIDefinition]
    skipped: list[SkippedKPI]                         # KPIs the agent considered but the schema can't answer
```

### 3.3 Evidence-Feeding Helper

```python
def compute_schema_capability(ir: SchemaIR, plan: EntityReconciliationPlan) -> SchemaCapability:
    """Structural inspection of the IR: which KPI shapes are answerable.
    No keyword matching on table or column names — uses semantic_type
    classifications produced by ColumnClassifier."""
```

Examples of agent reasoning:
- `has_money_column == True` and `has_temporal_column == True` → can plan revenue time-series.
- `has_status_with_completion == True` → can plan conversion-rate funnel.
- `has_geographic == True` → can plan regional distribution.
- `has_active_user_concept == True` → can plan retention cohort.
- `candidate_event_tables` are the event-shaped tables suitable for funnel KPIs.

### 3.4 The Prompt (key rules)

- Every KPI must have an explicit `grain` and the `formula` must respect it (no double-counting through joins).
- Every KPI must reference real columns via `ColumnRef`. Validator enforces.
- Every KPI must declare its `assumptions` plainly ("Refunded orders excluded").
- For a schema with money + temporal + status: propose at minimum revenue time-series + conversion-rate funnel + top-N customers/products.
- For a schema with active-user concept: propose retention cohort.
- Skip KPIs whose required columns are absent. Surface in `skipped` with reason.
- Maximum 12 KPIs per project (avoid analytics-tab overload). Pick the most operationally useful.
- Never assume a column type — always check `SchemaCapability` and `SchemaIR.tables[*].columns[*].semantic_type`.

Forbidden:
- Inventing columns. Validator catches; the agent must always reference real columns.
- Assuming `_cents` suffix, `status` name, etc. — that's the column-name heuristic anti-pattern. Use `SemanticType` only.
- Outputting raw SQL. Use `KPIFormula` typed tree only; the deterministic compiler emits SQL.
- Proposing more than 12.

### 3.5 The Output Validator

```python
@agent.output_validator
async def validate(ctx: RunContext[AgentDeps], out: KPIPlannerOutput) -> KPIPlannerOutput:
    if len(out.kpis) > 12:
        raise ModelRetry("Max 12 KPIs.")

    # Every column referenced exists in the IR
    ir_columns = {(t.name, c.name) for t in ctx.deps.schema_ir.tables for c in t.columns}
    for kpi in out.kpis:
        for ref in collect_column_refs(kpi):
            if (ref.table, ref.column) not in ir_columns:
                raise ModelRetry(f"KPI {kpi.name!r} references unknown column {ref.table}.{ref.column}.")

    # Grain table exists
    ir_tables = {t.name for t in ctx.deps.schema_ir.tables}
    for kpi in out.kpis:
        if kpi.grain.table not in ir_tables:
            raise ModelRetry(f"KPI {kpi.name!r} grain references unknown table {kpi.grain.table}.")

    # Time-series KPIs have time_dimension
    for kpi in out.kpis:
        if kpi.kind in (KPIKind.TIME_SERIES, KPIKind.COHORT) and kpi.time_dimension is None:
            raise ModelRetry(f"KPI {kpi.name!r} kind={kpi.kind} requires time_dimension.")

    # Money KPIs reference MONEY-typed columns
    for kpi in out.kpis:
        if kpi.formula.op in (KPIOp.SUM, KPIOp.AVG) and kpi.formula.column:
            col = _find_column(ctx.deps.schema_ir, kpi.formula.column)
            if col.semantic_type != SemanticType.MONEY and "revenue" in kpi.name.lower():
                raise ModelRetry(f"KPI {kpi.name!r} sums non-MONEY column.")

    return out
```

## 4. Design Patterns Applied

| Pattern | Where | Why |
|---|---|---|
| **Evidence-Feeding** | `evidence.py` → `SchemaCapability` | Agent picks answerable KPIs from typed structural facts. |
| **Strategy** | `KPIKind` + `KPIOp` enums | Agent picks the right shape per business question. |
| **Composite** | `KPIFormula` typed tree | Recursive formulas (RATIO of two SUMs, etc.) without string SQL. |
| **Validator-Driven Repair** | `@agent.output_validator` | Catches column-existence and grain-mismatch issues. |

## 5. Test Plan

- Validator tests: each `ModelRetry` branch.
- Evidence helper tests: structural detection across fixtures (e-commerce / booking / community / insufficient).
- TestModel-driven: per fixture, expected KPI set produced; column refs check out.
- Property test: every produced `KPIDefinition` round-trips through the deterministic SQL emitter and executes successfully against generated test rows.
- Coverage: 92%.

## 6. Error Codes

| Code | Condition | Recovery |
|---|---|---|
| `BF-AGENT-KPI-001` | Validation failed after retries | Manager escalates tier. |
| `BF-AGENT-KPI-002` | KPI references unknown column | Validator raises; `CoherenceGate` will additionally route. |
| `BF-AGENT-KPI-003` | Time-series KPI missing time_dimension | Validator raises. |
| `BF-AGENT-KPI-004` | More than 12 KPIs | Validator raises. |
| `BF-AGENT-KPI-005` | Grain table missing | Validator raises. |
| `BF-AGENT-KPI-006` | "Revenue"-named KPI sums non-MONEY column | Validator raises. |

## 7. Dependencies

[`IR-CORE`](IR-CORE.md), [`AGENT-PHYS`](AGENT-PHYS.md), [`AGENT-ENT`](AGENT-ENT.md).

## 8. Milestone

- **M1**: full implementation; ≥3 KPI shapes per fixture exercised; deterministic SQL emitter ships alongside.
- **M2**: KPIs adapted to multi-source unified IR; cross-source revenue/lapse computation.
- **M3**: anomaly-detection KPIs added (rolling-window thresholds).
- **M4+**: flywheel — when users repeatedly hide certain KPIs, the agent learns to skip them by category.
