"""DuckDB-backed KPI executor.

Per docs/40-features/ANALYTICS.md §3.4. Given a `CompiledKPI` + an in-memory
data fixture, materialise the rows in DuckDB and execute the typed SQL.
Returns a typed `KPIResult` the chart spec + digest composer consume.

This is the hosted-cloud execution path. BYO-DB customers get a sibling
`postgres_executor` that runs the same `CompiledKPI.sql` against the
customer's DB. Same KPI definition, different runner — strategy pattern
straight out of docs/50-design-patterns.md §3.

Type-aware: we let DuckDB type-infer from the PhysicalType-derived DDL we
emit before insert, so `SUM(amount_minor)` actually sums BIGINT — fixes
the audit's "in-memory SQLite shimmed everything to TEXT" regression.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import duckdb

from app.engines.analytics.kpi_compiler import CompiledKPI
from app.engines.schema.ddl.identifiers import is_safe_identifier, quote_identifier
from app.engines.schema.enums import PhysicalType
from app.engines.schema.ir import ColumnIR, SchemaIR, TableIR


__all__ = [
    "KPIExecutionError",
    "KPIResult",
    "KPIResultRow",
    "execute_kpi",
]


_DUCKDB_TYPE_BY_PHYSICAL: dict[PhysicalType, str] = {
    PhysicalType.UUID: "VARCHAR",
    PhysicalType.BIGINT: "BIGINT",
    PhysicalType.INT: "INTEGER",
    PhysicalType.SMALLINT: "SMALLINT",
    PhysicalType.NUMERIC: "DECIMAL(20, 4)",
    PhysicalType.TEXT: "VARCHAR",
    PhysicalType.VARCHAR: "VARCHAR",
    PhysicalType.BOOLEAN: "BOOLEAN",
    PhysicalType.TIMESTAMPTZ: "TIMESTAMPTZ",
    PhysicalType.DATE: "DATE",
    PhysicalType.JSONB: "JSON",
    PhysicalType.BYTEA: "BLOB",
}


# ---------- Public types ----------


@dataclass(frozen=True, slots=True)
class KPIResultRow:
    """One row from a KPI result. Preserves DuckDB's type-aware values."""

    bucket: Any | None = None
    """Set when the KPI is TIME_SERIES / COHORT (bucket is the time tier)."""
    dimension: Any | None = None
    """Set when the KPI is COMPARISON / DISTRIBUTION / TOP_N."""
    value: Any | None = None
    """The aggregate the KPI computes."""
    cohort: Any | None = None
    """Set when the KPI is COHORT (cohort label, e.g., signup week)."""
    extra: dict[str, Any] | None = None
    """Any unrecognised columns; preserved for forward-compat."""


@dataclass(frozen=True, slots=True)
class KPIResult:
    name: str
    sql: str
    rows: tuple[KPIResultRow, ...]


class KPIExecutionError(RuntimeError):
    """Raised when a compiled KPI fails to execute against DuckDB.

    Carries the KPI name and the underlying DuckDB error.
    """


# ---------- Helpers ----------


def _column_type(col: ColumnIR) -> str:
    return _DUCKDB_TYPE_BY_PHYSICAL.get(col.physical_type, "VARCHAR")


def _create_table_sql(table: TableIR) -> str:
    cols: list[str] = []
    for col in table.columns:
        if not is_safe_identifier(col.name):
            raise KPIExecutionError(
                f"Refusing to materialise column with unsafe identifier: {col.name!r}"
            )
        decl = f"{quote_identifier(col.name)} {_column_type(col)}"
        if not col.nullable:
            decl += " NOT NULL"
        cols.append(decl)
    body = ",\n  ".join(cols)
    return f"CREATE TABLE {quote_identifier(table.name)} (\n  {body}\n);"


def _insert_rows(
    conn: duckdb.DuckDBPyConnection,
    table: TableIR,
    rows: Sequence[Mapping[str, Any]],
) -> None:
    if not rows:
        return
    column_names = [c.name for c in table.columns]
    placeholders = ", ".join(["?"] * len(column_names))
    quoted_cols = ", ".join(quote_identifier(c) for c in column_names)
    insert_sql = (
        f"INSERT INTO {quote_identifier(table.name)} ({quoted_cols}) "
        f"VALUES ({placeholders})"
    )
    payload = [
        tuple(row.get(col) for col in column_names)
        for row in rows
    ]
    conn.executemany(insert_sql, payload)


def _result_row_from_record(
    record: tuple[Any, ...], column_names: tuple[str, ...]
) -> KPIResultRow:
    """Map a DuckDB result row into a typed KPIResultRow.

    The KPI compiler emits these column aliases:
      - `bucket` for TIME_SERIES / COHORT
      - `dimension` for COMPARISON / DISTRIBUTION / TOP_N
      - `value` always
    Any other columns end up in `extra`.
    """
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


# ---------- Top-level entrypoint ----------


def execute_kpi(
    *,
    compiled: CompiledKPI,
    schema_ir: SchemaIR,
    rows_by_table: Mapping[str, Iterable[Mapping[str, Any]]],
) -> KPIResult:
    """Execute a compiled KPI against an in-memory DuckDB.

    `rows_by_table` maps table name → iterable of row dicts. Tables present
    in the SchemaIR but absent from `rows_by_table` are materialised empty.
    DuckDB's type-aware columns mean `SUM`/`AVG` over BIGINT money columns
    actually sum BIGINTs (fixing the audit-flagged "all-text SQLite" regression).
    """
    conn = duckdb.connect(database=":memory:")
    try:
        for table in schema_ir.tables:
            conn.execute(_create_table_sql(table))
            rows = list(rows_by_table.get(table.name, []))
            _insert_rows(conn, table, rows)

        try:
            cursor = conn.execute(compiled.sql)
        except duckdb.Error as exc:
            raise KPIExecutionError(
                f"KPI {compiled.name!r}: DuckDB execution failed: {exc}"
            ) from exc

        column_names: tuple[str, ...] = tuple(d[0] for d in (cursor.description or ()))
        records = cursor.fetchall()
    finally:
        conn.close()

    result_rows = tuple(_result_row_from_record(r, column_names) for r in records)
    return KPIResult(name=compiled.name, sql=compiled.sql, rows=result_rows)
