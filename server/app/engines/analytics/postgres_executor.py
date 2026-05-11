"""Postgres-backed KPI executor for hosted mode.

Given a ``CompiledKPI`` and a tenant-scoped async session, set the
``search_path`` to the tenant schema and run the compiled SQL directly
against Postgres. No in-memory materialisation — the query planner sees
the real tables and indexes.

This is the hosted-cloud execution path. BYO-DB (not in v1) will use the
sibling ``duckdb_executor`` when the customer's data lives outside our
Postgres fleet.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import BasefloError
from app.engines.analytics.kpi_compiler import CompiledKPI
from app.engines.schema.ddl.identifiers import is_safe_identifier

__all__ = [
    "KPIResult",
    "KPIResultRow",
    "PostgresKPIExecutor",
]


@dataclass(frozen=True, slots=True)
class KPIResultRow:
    bucket: Any | None = None
    dimension: Any | None = None
    value: Any | None = None
    cohort: Any | None = None
    extra: dict[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class KPIResult:
    name: str
    sql: str
    rows: tuple[KPIResultRow, ...]


class PostgresKPIExecutor:
    """Execute compiled KPIs directly against a tenant Postgres schema."""

    @staticmethod
    async def execute_kpi(
        *,
        compiled: CompiledKPI,
        session: AsyncSession,
        schema_name: str,
    ) -> KPIResult:
        """Run ``compiled.sql`` against the tenant schema and return typed rows."""
        if not is_safe_identifier(schema_name):
            raise BasefloError(
                error_code="BF-ANALYTICS-002",
                message=f"Unsafe schema name for KPI execution: {schema_name!r}.",
                status_code=500,
            )

        current_path = (
            await session.execute(
                text("SELECT current_setting('search_path', true)")
            )
        ).scalar_one()

        await session.execute(
            text("SELECT set_config('search_path', :path, true)"),
            {"path": f"{schema_name}, public"},
        )
        try:
            result = await session.execute(text(compiled.sql))
        except Exception as exc:
            raise BasefloError(
                error_code="BF-ANALYTICS-001",
                message=f"KPI {compiled.name!r}: Postgres execution failed: {exc}",
                status_code=500,
            ) from exc
        finally:
            await session.execute(
                text("SELECT set_config('search_path', :path, true)"),
                {"path": current_path},
            )

        column_names: tuple[str, ...] = tuple(result.keys())
        records = result.all()
        result_rows = tuple(
            _result_row_from_record(r, column_names) for r in records
        )
        return KPIResult(name=compiled.name, sql=compiled.sql, rows=result_rows)


def _result_row_from_record(
    record: tuple[Any, ...], column_names: tuple[str, ...]
) -> KPIResultRow:
    bucket: Any | None = None
    dimension: Any | None = None
    value: Any | None = None
    cohort: Any | None = None
    extra: dict[str, Any] = {}
    for idx, name in enumerate(column_names):
        cell = record[idx]
        if name == "bucket":
            bucket = cell
        elif name == "dimension":
            dimension = cell
        elif name == "value":
            value = cell
        elif name == "cohort":
            cohort = cell
        else:
            extra[name] = cell
    return KPIResultRow(
        bucket=bucket,
        dimension=dimension,
        value=value,
        cohort=cohort,
        extra=extra or None,
    )
