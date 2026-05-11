"""Chart-spec emitter — KPI shape → typed chart spec for the React client.

Per docs/40-features/ANALYTICS.md §3.9. Pure deterministic mapping; no agent.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from app.agents.specialists.kpi_planner.types import KPIDefinition, KPIKind


__all__ = [
    "ChartKind",
    "ChartSpec",
    "build_chart_spec",
]


class ChartKind(StrEnum):
    NUMBER_CARD = "number_card"
    LINE = "line"
    HISTOGRAM = "histogram"
    BAR = "bar"
    FUNNEL = "funnel"
    HEATMAP = "heatmap"
    RANKED_TABLE = "ranked_table"


_CHART_BY_KPI_KIND: dict[KPIKind, ChartKind] = {
    KPIKind.COUNTER: ChartKind.NUMBER_CARD,
    KPIKind.TIME_SERIES: ChartKind.LINE,
    KPIKind.DISTRIBUTION: ChartKind.HISTOGRAM,
    KPIKind.COMPARISON: ChartKind.BAR,
    KPIKind.FUNNEL: ChartKind.FUNNEL,
    KPIKind.COHORT: ChartKind.HEATMAP,
    KPIKind.TOP_N: ChartKind.RANKED_TABLE,
}


class ChartSpec(BaseModel):
    """Typed chart spec the client renders. Mechanical from KPI shape."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kpi_name: str = Field(min_length=2)
    kind: ChartKind
    sql_view: str
    """The compiled KPI SQL the client / executor runs to populate the chart."""
    x_axis: str | None = None
    y_axis: str | None = None
    legend: str | None = None
    show_delta: bool = False
    """Number cards show a delta-vs-prior-period when True."""


def build_chart_spec(*, kpi: KPIDefinition, sql: str) -> ChartSpec:
    """Compose a chart spec for the given KPI + its compiled SQL.

    Mapping:
      COUNTER       → NUMBER_CARD with delta-vs-prior shown.
      TIME_SERIES   → LINE; x=bucket, y=value.
      DISTRIBUTION  → HISTOGRAM; x=dimension, y=value.
      COMPARISON    → BAR; x=dimension, y=value.
      FUNNEL        → FUNNEL.
      COHORT        → HEATMAP; x=bucket, y=cohort.
      TOP_N         → RANKED_TABLE.
    """
    kind = _CHART_BY_KPI_KIND[kpi.kind]
    spec = ChartSpec(
        kpi_name=kpi.name,
        kind=kind,
        sql_view=sql,
        x_axis=_x_axis(kpi),
        y_axis=_y_axis(kpi),
        legend=_legend(kpi),
        show_delta=(kind == ChartKind.NUMBER_CARD),
    )
    return spec


def _x_axis(kpi: KPIDefinition) -> str | None:
    if kpi.kind in {KPIKind.TIME_SERIES, KPIKind.COHORT}:
        return "bucket"
    if kpi.kind in {KPIKind.COMPARISON, KPIKind.DISTRIBUTION, KPIKind.TOP_N}:
        return "dimension"
    return None


def _y_axis(kpi: KPIDefinition) -> str | None:
    """Y-axis label for chart shapes that need one. FUNNEL has no y axis."""
    if kpi.kind == KPIKind.FUNNEL:
        return None
    return "value"


def _legend(kpi: KPIDefinition) -> str | None:
    if kpi.kind == KPIKind.COHORT:
        return "cohort"
    return None
