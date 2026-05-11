"""Workspace analytics summary builder.

Alpha goal: turn persisted `KPIDefinition`s + canonical rows into the contract
the web app already renders. This is deterministic execution, not an agent
surface. Agents choose the KPIs; this service compiles and runs them.
"""

from __future__ import annotations

from collections import Counter
from datetime import UTC, date, datetime, timedelta
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field

from app.agents.specialists.kpi_planner.types import (
    KPIDefinition,
    KPIKind,
)
from app.core.errors import BasefloError
from app.engines.analytics.duckdb_executor import (
    KPIExecutionError,
    KPIResult,
    execute_kpi as execute_kpi_duckdb,
)
from app.engines.analytics.kpi_compiler import KPICompilationError, compile_kpi
from app.engines.analytics.postgres_executor import PostgresKPIExecutor
from app.engines.schema.enums import PII_SEMANTIC_TYPES, SemanticType
from app.observability.logging import get_logger

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession

    from app.engines.schema.ir import ColumnIR, SchemaIR, TableIR


logger = get_logger("services.analytics.summary")


class FunnelStepDTO(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    id: str
    label: str
    count: int = Field(ge=0)
    conversion_rate: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        serialization_alias="conversionRate",
    )


class FunnelDTO(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    id: str
    name: str
    steps: list[FunnelStepDTO] = Field(default_factory=list)


class CohortRowDTO(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    cohort_label: str = Field(serialization_alias="cohortLabel")
    size: int = Field(ge=0)
    retention: list[float] = Field(default_factory=list)


class CohortGridDTO(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    id: str
    name: str
    bucket_labels: list[str] = Field(
        default_factory=list,
        serialization_alias="bucketLabels",
    )
    rows: list[CohortRowDTO] = Field(default_factory=list)


class TopNRowDTO(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    label: str
    value: float
    unit: str | None = None


class TopNListDTO(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    id: str
    name: str
    rows: list[TopNRowDTO] = Field(default_factory=list)


class GeoBucketDTO(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    region: str
    count: int = Field(ge=0)


class LapsingRowDTO(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    entity_id: str = Field(serialization_alias="entityId")
    label: str
    last_active_at: str = Field(serialization_alias="lastActiveAt")
    reason: str


class AnalyticsSummaryDTO(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    version_id: str = Field(serialization_alias="versionId")
    funnels: list[FunnelDTO] = Field(default_factory=list)
    cohorts: list[CohortGridDTO] = Field(default_factory=list)
    top_n: list[TopNListDTO] = Field(
        default_factory=list,
        serialization_alias="topN",
    )
    geo: list[GeoBucketDTO] = Field(default_factory=list)
    lapsing: list[LapsingRowDTO] = Field(default_factory=list)


class AnalyticsSummaryBuilder:
    """Builds the alpha analytics response from canonical rows."""

    async def build(
        self,
        *,
        version_id: UUID,
        ir: SchemaIR,
        kpis: list[KPIDefinition],
        rows_by_table: dict[str, list[dict[str, Any]]],
        session: AsyncSession | None = None,
        schema_name: str | None = None,
    ) -> AnalyticsSummaryDTO:
        schema_summary = {
            table.name: [column.name for column in table.columns]
            for table in ir.tables
        }
        results = await self._execute_kpis(
            ir=ir,
            kpis=kpis,
            rows_by_table=rows_by_table,
            schema_summary=schema_summary,
            session=session,
            schema_name=schema_name,
        )
        top_n = self._top_n_from_results(kpis=kpis, results=results)
        if not top_n:
            top_n = self._fallback_top_n(ir=ir, rows_by_table=rows_by_table)

        return AnalyticsSummaryDTO(
            version_id=str(version_id),
            funnels=self._funnels_from_results(kpis=kpis, results=results),
            cohorts=[],
            top_n=top_n,
            geo=self._geo_from_rows(ir=ir, rows_by_table=rows_by_table),
            lapsing=self._lapsing_from_rows(ir=ir, rows_by_table=rows_by_table),
        )

    async def _execute_kpis(
        self,
        *,
        ir: SchemaIR,
        kpis: list[KPIDefinition],
        rows_by_table: dict[str, list[dict[str, Any]]],
        schema_summary: dict[str, list[str]],
        session: AsyncSession | None = None,
        schema_name: str | None = None,
    ) -> dict[str, KPIResult]:
        out: dict[str, KPIResult] = {}
        for kpi in kpis:
            try:
                compiled = compile_kpi(kpi, schema_summary=schema_summary)
                if session is not None and schema_name is not None:
                    out[kpi.name] = await PostgresKPIExecutor.execute_kpi(
                        compiled=compiled,
                        session=session,
                        schema_name=schema_name,
                    )
                else:
                    out[kpi.name] = execute_kpi_duckdb(
                        compiled=compiled,
                        schema_ir=ir,
                        rows_by_table=rows_by_table,
                    )
            except (KPICompilationError, KPIExecutionError, BasefloError, ValueError) as exc:
                logger.warning(
                    "analytics_kpi_skipped",
                    kpi_name=kpi.name,
                    error=str(exc),
                )
        return out

    def _top_n_from_results(
        self,
        *,
        kpis: list[KPIDefinition],
        results: dict[str, KPIResult],
    ) -> list[TopNListDTO]:
        out: list[TopNListDTO] = []
        by_name = {kpi.name: kpi for kpi in kpis}
        for name, result in results.items():
            kpi = by_name.get(name)
            if kpi is None:
                continue
            if kpi.kind not in {
                KPIKind.TOP_N,
                KPIKind.COMPARISON,
                KPIKind.DISTRIBUTION,
                KPIKind.COUNTER,
            }:
                continue
            rows: list[TopNRowDTO] = []
            for idx, row in enumerate(result.rows):
                label = (
                    str(row.dimension)
                    if row.dimension is not None
                    else kpi.name if kpi.kind == KPIKind.COUNTER
                    else f"Row {idx + 1}"
                )
                rows.append(
                    TopNRowDTO(
                        label=label,
                        value=_numeric(row.value),
                        unit=_unit_for_kpi(kpi),
                    )
                )
            if rows:
                out.append(
                    TopNListDTO(
                        id=_slug(name),
                        name=name,
                        rows=rows[:10],
                    )
                )
        return out[:6]

    def _funnels_from_results(
        self,
        *,
        kpis: list[KPIDefinition],
        results: dict[str, KPIResult],
    ) -> list[FunnelDTO]:
        out: list[FunnelDTO] = []
        by_name = {kpi.name: kpi for kpi in kpis}
        for name, result in results.items():
            kpi = by_name.get(name)
            if kpi is None or kpi.kind != KPIKind.FUNNEL:
                continue
            steps: list[FunnelStepDTO] = []
            first_count: int | None = None
            for idx, row in enumerate(result.rows):
                count = int(_numeric(row.value))
                if first_count is None:
                    first_count = max(1, count)
                steps.append(
                    FunnelStepDTO(
                        id=f"{_slug(name)}_{idx}",
                        label=str(row.dimension or f"Step {idx + 1}"),
                        count=count,
                        conversion_rate=count / first_count if first_count else None,
                    )
                )
            if steps:
                out.append(FunnelDTO(id=_slug(name), name=name, steps=steps))
        return out

    def _geo_from_rows(
        self,
        *,
        ir: SchemaIR,
        rows_by_table: dict[str, list[dict[str, Any]]],
    ) -> list[GeoBucketDTO]:
        counter: Counter[str] = Counter()
        for table in ir.tables:
            geo_columns = [
                column for column in table.columns
                if _is_geo_column(column)
            ]
            for column in geo_columns:
                for row in rows_by_table.get(table.name, []):
                    value = row.get(column.name)
                    if value in (None, ""):
                        continue
                    counter[_region_label(value)] += 1
        return [
            GeoBucketDTO(region=region, count=count)
            for region, count in counter.most_common(10)
        ]

    def _lapsing_from_rows(
        self,
        *,
        ir: SchemaIR,
        rows_by_table: dict[str, list[dict[str, Any]]],
    ) -> list[LapsingRowDTO]:
        cutoff = datetime.now(UTC) - timedelta(days=30)
        out: list[LapsingRowDTO] = []
        for table in ir.tables:
            temporal = _best_temporal_column(table)
            if temporal is None:
                continue
            label_col = _best_label_column(table)
            id_col = table.primary_key[0]
            for row in rows_by_table.get(table.name, []):
                last_active = _parse_datetime(row.get(temporal.name))
                if last_active is None or last_active >= cutoff:
                    continue
                entity_id = str(row.get(id_col) or "")
                label = str(row.get(label_col.name) or entity_id or table.label)
                out.append(
                    LapsingRowDTO(
                        entity_id=entity_id,
                        label=label,
                        last_active_at=last_active.isoformat(),
                        reason=f"No activity since {last_active.date().isoformat()}",
                    )
                )
        out.sort(key=lambda item: item.last_active_at)
        return out[:20]

    def _fallback_top_n(
        self,
        *,
        ir: SchemaIR,
        rows_by_table: dict[str, list[dict[str, Any]]],
    ) -> list[TopNListDTO]:
        lists: list[TopNListDTO] = []
        for table in ir.tables:
            category = next(
                (
                    column for column in table.columns
                    if column.semantic_type in {
                        SemanticType.STATUS,
                        SemanticType.CATEGORY,
                        SemanticType.PII_ADDRESS,
                    }
                ),
                None,
            )
            if category is None:
                continue
            counts: Counter[str] = Counter(
                str(row.get(category.name))
                for row in rows_by_table.get(table.name, [])
                if row.get(category.name) not in (None, "")
            )
            if not counts:
                continue
            lists.append(
                TopNListDTO(
                    id=f"{table.name}_{category.name}",
                    name=f"{table.label} by {category.label}",
                    rows=[
                        TopNRowDTO(label=label, value=float(count), unit="rows")
                        for label, count in counts.most_common(10)
                    ],
                )
            )
        return lists[:6]


def _best_temporal_column(table: TableIR) -> ColumnIR | None:
    temporal = [
        column for column in table.columns
        if column.semantic_type == SemanticType.TEMPORAL
    ]
    if not temporal:
        return None
    preferred_names = ("last_active_at", "last_seen_at", "updated_at")
    by_name = {column.name: column for column in temporal}
    for name in preferred_names:
        if name in by_name:
            return by_name[name]
    for column in temporal:
        if any(token in column.name for token in ("active", "seen", "purchase", "order")):
            return column
    return None


def _is_geo_column(column: ColumnIR) -> bool:
    if column.semantic_type == SemanticType.PII_ADDRESS:
        return True
    if column.semantic_type != SemanticType.CATEGORY:
        return False
    return column.name in {"region", "country", "state", "city", "province"}


def _best_label_column(table: TableIR) -> ColumnIR:
    for semantic in (
        SemanticType.PII_NAME,
        SemanticType.PII_EMAIL,
        SemanticType.CATEGORY,
        SemanticType.STATUS,
    ):
        for column in table.columns:
            if column.semantic_type == semantic:
                return column
    for column in table.columns:
        if column.semantic_type not in PII_SEMANTIC_TYPES:
            return column
    return table.columns[0]


def _unit_for_kpi(kpi: KPIDefinition) -> str | None:
    if kpi.formula.column is None:
        return "rows"
    if "minor" in kpi.formula.column.column:
        return "minor"
    return None


def _numeric(value: Any) -> float:
    if value is None:
        return 0.0
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    if isinstance(value, int | float):
        return float(value)
    try:
        return float(str(value))
    except ValueError:
        return 0.0


def _parse_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day, tzinfo=UTC)
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _region_label(value: Any) -> str:
    text = str(value).strip()
    if not text:
        return "Unknown"
    parts = [part.strip() for part in text.split(",") if part.strip()]
    return parts[-1] if parts else text


def _slug(value: str) -> str:
    lowered = value.lower()
    out = "".join(ch if ch.isalnum() else "_" for ch in lowered)
    return "_".join(part for part in out.split("_") if part)[:80] or "metric"
