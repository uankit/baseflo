"""Analytics engine — KPI SQL compilation, chart-spec emission, event ingestion.

Per docs/40-features/ANALYTICS.md.

M1 ships the deterministic KPI compiler (`KPIFormula` tree → typed SQLGlot
AST → Postgres SQL string) and the chart-spec emitter (KPI shape → typed
chart spec for the React client). Event ingestion + DuckDB executor + funnels
+ cohorts + anomaly detection are not available in v1.
"""

from __future__ import annotations

from app.engines.analytics.chart_spec import (  # noqa: F401
    ChartKind,
    ChartSpec,
    build_chart_spec,
)
from app.engines.analytics.kpi_compiler import (  # noqa: F401
    CompiledKPI,
    KPICompilationError,
    compile_kpi,
)
