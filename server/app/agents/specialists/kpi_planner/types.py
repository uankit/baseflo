"""Typed I/O for KPIPlanner.

Per docs/40-features/AGENT-KPI.md §3.2.

The KPI formula is a typed RECURSIVE tree (Composite pattern from
docs/50-design-patterns.md §1) — never a SQL string. The deterministic
KPI compiler (M1.5) walks this tree and emits SQL via SQLGlot.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


__all__ = [
    "ColumnRef",
    "FilterOp",
    "KPIDefinition",
    "KPIFilter",
    "KPIFormula",
    "KPIGrain",
    "KPIKind",
    "KPIOp",
    "KPIPlannerInput",
    "KPIPlannerOutput",
    "SchemaCapability",
    "StatusColumnCapability",
    "SkippedKPI",
]


class KPIKind(StrEnum):
    COUNTER = "counter"
    TIME_SERIES = "time_series"
    DISTRIBUTION = "distribution"
    COMPARISON = "comparison"
    FUNNEL = "funnel"
    COHORT = "cohort"
    TOP_N = "top_n"


class KPIOp(StrEnum):
    SUM = "sum"
    COUNT = "count"
    COUNT_DISTINCT = "count_distinct"
    AVG = "avg"
    MIN = "min"
    MAX = "max"
    RATIO = "ratio"


class FilterOp(StrEnum):
    EQ = "eq"
    NE = "ne"
    IN = "in"
    NOT_IN = "not_in"
    GTE = "gte"
    LTE = "lte"
    BETWEEN = "between"
    IS_NULL = "is_null"
    IS_NOT_NULL = "is_not_null"


class ColumnRef(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    table: str = Field(min_length=1, max_length=63)
    column: str = Field(min_length=1, max_length=63)


class KPIFilter(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    column: ColumnRef
    op: FilterOp
    value: str | int | float | bool | list[str] | list[int] | list[float] | None = None


class KPIFormula(BaseModel):
    """Recursive formula tree.

    `op == SUM | COUNT | COUNT_DISTINCT | AVG | MIN | MAX` requires `column`.
    `op == COUNT` may have `column = None` (count *).
    `op == RATIO` requires `numerator` + `denominator` (both KPIFormula);
    `column` MUST be None.
    """

    model_config = ConfigDict(extra="forbid")
    op: KPIOp
    column: ColumnRef | None = None
    numerator: "KPIFormula | None" = None
    denominator: "KPIFormula | None" = None
    distinct: bool = False


class KPIGrain(BaseModel):
    """`grain.description` is the user-facing 'one row per ___'.

    `grain.table` is the canonical entity the metric counts/aggregates over;
    `grain.deduplication_columns` lists the columns that uniquely identify a
    row at this grain (typically `[id]`) so the deterministic compiler can
    detect and prevent double-counting on joins.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")
    description: str = Field(min_length=1, max_length=200)
    table: str = Field(min_length=1, max_length=63)
    deduplication_columns: list[str] = Field(min_length=1)


class KPIDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=2, max_length=80)
    description: str = Field(min_length=1, max_length=500)
    kind: KPIKind
    grain: KPIGrain
    formula: KPIFormula
    time_dimension: ColumnRef | None = None
    """Required for kind in (TIME_SERIES, COHORT)."""
    breakdown_dimension: ColumnRef | None = None
    """Used by COMPARISON, TOP_N."""
    filters: list[KPIFilter] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list, max_length=10)
    rationale: str = Field(min_length=1, max_length=500)
    """Trace-only; never user-surfaced directly."""


class StatusColumnCapability(BaseModel):
    """Observed enum facts for one STATUS column.

    KPIPlanner may filter on these values, but must not invent lifecycle
    states that were not present in the schema.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")
    table: str = Field(min_length=1, max_length=63)
    column: str = Field(min_length=1, max_length=63)
    enum_values: list[str] = Field(min_length=1)
    completion_values: list[str] = Field(default_factory=list)


class SchemaCapability(BaseModel):
    """Deterministic facts about what the schema can answer structurally.

    See `evidence.compute_schema_capability`. The agent reads these as
    typed facts and decides which KPI shapes to propose.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")
    has_money_column: bool
    money_tables: list[str] = Field(default_factory=list)
    money_columns: list[ColumnRef] = Field(default_factory=list)
    has_status_with_completion: bool
    status_columns: list[StatusColumnCapability] = Field(default_factory=list)
    has_temporal_column: bool
    temporal_tables: list[str] = Field(default_factory=list)
    temporal_columns: list[ColumnRef] = Field(default_factory=list)
    has_geographic: bool
    has_active_user_concept: bool
    has_customer_entity: bool
    candidate_event_tables: list[str] = Field(default_factory=list)


class SkippedKPI(BaseModel):
    """A KPI the agent considered but the schema can't answer.

    Surfaced for transparency: the workspace can show 'we wanted to compute
    X but you don't have a Y column'. Lets users add what's missing.
    """

    model_config = ConfigDict(extra="forbid")
    name: str
    reason: str
    missing: list[str] = Field(default_factory=list)
    """Columns/relationships the user could add to unblock this metric."""


class KPIPlannerInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    business_context: str | None = Field(default=None, max_length=5000)
    """User-provided business context for selecting useful metrics."""
    # We carry the full SchemaIR in by reference; the agent reads structure
    # off it. SchemaIR is heavy but typed cleanly through Pydantic.
    schema_capability: SchemaCapability
    schema_summary: dict[str, list[str]] = Field(default_factory=dict)
    """Map of table_name -> list of (canonical) column names. Lighter than full IR."""


class KPIPlannerOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kpis: list[KPIDefinition] = Field(default_factory=list, max_length=12)
    """Hard cap of 12 KPIs per project to avoid analytics-tab overload."""
    skipped: list[SkippedKPI] = Field(default_factory=list)
