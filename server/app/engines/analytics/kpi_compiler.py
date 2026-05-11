"""KPI compiler — `KPIDefinition` → typed Postgres SQL via SQLGlot.

Per docs/40-features/ANALYTICS.md §3.4. Pure function: same KPI in →
same SQL out. SQLGlot's expression API builds the AST; we render via
`sql(dialect='postgres')` so the resulting string is always syntactically
correct (or we raise a typed error).

The compiler validates:
  - Every column reference resolves against the supplied schema summary.
  - The grain table exists.
  - RATIO formulas have both numerator and denominator.
  - SUM/AVG/MIN/MAX/COUNT_DISTINCT have a column reference.
  - Time-series + cohort KPIs have a time_dimension.

Compilation surface intentionally narrower than the agent's prompt allows;
shapes the agent might produce that the compiler can't yet emit will surface
through `KPIPlanner._validate_output` first (per agent), then through
`CoherenceGate` deterministic checks.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

import sqlglot
from sqlglot import exp
from sqlglot.errors import ParseError

from app.agents.specialists.kpi_planner.types import (
    ColumnRef,
    FilterOp,
    KPIDefinition,
    KPIFilter,
    KPIFormula,
    KPIKind,
    KPIOp,
)
from app.engines.schema.ddl.identifiers import (
    is_safe_identifier,
    quote_identifier,
)


__all__ = [
    "CompiledKPI",
    "KPICompilationError",
    "compile_kpi",
]


@dataclass(frozen=True, slots=True)
class CompiledKPI:
    """Compiled KPI: typed SQL string + provenance fields for caching/debug."""

    name: str
    sql: str
    grain_table: str
    time_dimension: str | None
    breakdown_dimension: str | None


class KPICompilationError(ValueError):
    """Raised when a KPI cannot be compiled. Carries the KPI name + reason."""


# ---------- Filter compilation ----------


_BINARY_OP_BY_FILTER: dict[FilterOp, type[exp.Expression]] = {
    FilterOp.EQ: exp.EQ,
    FilterOp.NE: exp.NEQ,
    FilterOp.GTE: exp.GTE,
    FilterOp.LTE: exp.LTE,
}


def _column_ref_to_expr(ref: ColumnRef) -> exp.Column:
    """Build a SQLGlot Column expression with safely-quoted identifiers."""
    if not is_safe_identifier(ref.table) or not is_safe_identifier(ref.column):
        # Force quoting via SQLGlot's parser (it handles escaping correctly).
        return exp.column(
            quote_identifier(ref.column).strip('"'),
            table=quote_identifier(ref.table).strip('"'),
            quoted=True,
        )
    return exp.column(ref.column, table=ref.table)


def _value_to_literal(value: object) -> exp.Expression:
    """Convert a Python literal to a SQLGlot Literal expression."""
    if value is None:
        return exp.null()
    if isinstance(value, bool):
        return exp.true() if value else exp.false()
    if isinstance(value, (int, float)):
        return exp.Literal.number(value)
    if isinstance(value, list):
        return exp.Tuple(expressions=[_value_to_literal(v) for v in value])
    return exp.Literal.string(str(value))


def _filter_to_expr(filt: KPIFilter) -> exp.Expression:
    col = _column_ref_to_expr(filt.column)

    if filt.op in _BINARY_OP_BY_FILTER:
        op_cls = _BINARY_OP_BY_FILTER[filt.op]
        return op_cls(this=col, expression=_value_to_literal(filt.value))

    if filt.op == FilterOp.IN:
        if not isinstance(filt.value, list):
            raise KPICompilationError(
                f"Filter {filt.column.column!r} op=IN requires a list value."
            )
        return exp.In(
            this=col,
            expressions=[_value_to_literal(v) for v in filt.value],
        )

    if filt.op == FilterOp.NOT_IN:
        if not isinstance(filt.value, list):
            raise KPICompilationError(
                f"Filter {filt.column.column!r} op=NOT_IN requires a list value."
            )
        return exp.Not(
            this=exp.In(
                this=col,
                expressions=[_value_to_literal(v) for v in filt.value],
            )
        )

    if filt.op == FilterOp.BETWEEN:
        if not isinstance(filt.value, list) or len(filt.value) != 2:
            raise KPICompilationError(
                f"Filter {filt.column.column!r} op=BETWEEN requires [low, high]."
            )
        return exp.Between(
            this=col,
            low=_value_to_literal(filt.value[0]),
            high=_value_to_literal(filt.value[1]),
        )

    if filt.op == FilterOp.IS_NULL:
        return exp.Is(this=col, expression=exp.null())

    if filt.op == FilterOp.IS_NOT_NULL:
        return exp.Not(this=exp.Is(this=col, expression=exp.null()))

    raise KPICompilationError(f"Unsupported filter op: {filt.op!r}")


def _combine_filters(filters: list[KPIFilter]) -> exp.Expression | None:
    if not filters:
        return None
    parts = [_filter_to_expr(f) for f in filters]
    combined = parts[0]
    for part in parts[1:]:
        combined = exp.And(this=combined, expression=part)
    return combined


# ---------- Aggregate compilation ----------


def _formula_to_aggregate_expr(
    formula: KPIFormula, kpi_name: str
) -> exp.Expression:
    """Compile a KPIFormula tree to a SQLGlot scalar aggregate expression."""
    if formula.op == KPIOp.COUNT:
        if formula.column is None:
            return exp.Count(this=exp.Star())
        return exp.Count(this=_column_ref_to_expr(formula.column))

    if formula.op == KPIOp.COUNT_DISTINCT:
        if formula.column is None:
            raise KPICompilationError(f"{kpi_name!r}: COUNT_DISTINCT requires a column.")
        return exp.Count(
            this=exp.Distinct(expressions=[_column_ref_to_expr(formula.column)])
        )

    if formula.op in {KPIOp.SUM, KPIOp.AVG, KPIOp.MIN, KPIOp.MAX}:
        if formula.column is None:
            # User-facing SQL keywords are conventionally uppercase; the lower-cased
            # enum value would be confusing in error messages.
            raise KPICompilationError(
                f"{kpi_name!r}: {formula.op.value.upper()} requires a column."
            )
        agg_cls = {
            KPIOp.SUM: exp.Sum,
            KPIOp.AVG: exp.Avg,
            KPIOp.MIN: exp.Min,
            KPIOp.MAX: exp.Max,
        }[formula.op]
        # sqlglot's Sum/Avg/Min/Max derive from AggFunc → Func → Expression at
        # runtime; mypy's bundled stubs don't carry the chain through the dict
        # union, so we cast at the boundary.
        return cast(
            exp.Expression, agg_cls(this=_column_ref_to_expr(formula.column))
        )

    if formula.op == KPIOp.RATIO:
        if formula.numerator is None or formula.denominator is None:
            raise KPICompilationError(
                f"{kpi_name!r}: RATIO requires numerator + denominator."
            )
        num = _formula_to_aggregate_expr(formula.numerator, f"{kpi_name}.num")
        den = _formula_to_aggregate_expr(formula.denominator, f"{kpi_name}.den")
        # NULLIF guards division by zero.
        return exp.Div(
            this=num,
            expression=exp.func("NULLIF", den, exp.Literal.number(0)),
        )

    raise KPICompilationError(f"{kpi_name!r}: unknown KPIOp {formula.op!r}")


# ---------- Time bucket compilation ----------


_TIME_BUCKET_BY_KIND: dict[KPIKind, str] = {
    KPIKind.TIME_SERIES: "week",
    KPIKind.COHORT: "week",
}


def _time_bucket_expr(
    time_dimension: ColumnRef, kpi_kind: KPIKind
) -> exp.Expression:
    """`date_trunc('week', table.column)` for time-series + cohorts."""
    bucket = _TIME_BUCKET_BY_KIND.get(kpi_kind, "week")
    # `exp.func(...)` returns a sqlglot Func (Expression subclass); mypy's
    # bundled stubs narrow it to Func and Func isn't seen as Expression.
    return cast(
        exp.Expression,
        exp.func(
            "DATE_TRUNC",
            exp.Literal.string(bucket),
            _column_ref_to_expr(time_dimension),
        ),
    )


# ---------- Schema validation ----------


def _resolve_refs(formula: KPIFormula) -> list[ColumnRef]:
    refs: list[ColumnRef] = []
    if formula.column is not None:
        refs.append(formula.column)
    if formula.numerator is not None:
        refs.extend(_resolve_refs(formula.numerator))
    if formula.denominator is not None:
        refs.extend(_resolve_refs(formula.denominator))
    return refs


def _validate_against_schema(
    kpi: KPIDefinition, schema_summary: dict[str, list[str]]
) -> None:
    """Verify every referenced (table, column) exists in the supplied summary."""
    if kpi.grain.table not in schema_summary:
        raise KPICompilationError(
            f"{kpi.name!r}: grain.table {kpi.grain.table!r} not in schema."
        )

    refs = _resolve_refs(kpi.formula)
    if kpi.time_dimension is not None:
        refs.append(kpi.time_dimension)
    if kpi.breakdown_dimension is not None:
        refs.append(kpi.breakdown_dimension)
    for f in kpi.filters:
        refs.append(f.column)

    for ref in refs:
        cols = schema_summary.get(ref.table)
        if cols is None:
            raise KPICompilationError(
                f"{kpi.name!r}: references unknown table {ref.table!r}."
            )
        if ref.column not in cols:
            raise KPICompilationError(
                f"{kpi.name!r}: references unknown column {ref.table}.{ref.column}."
            )

    if kpi.kind in {KPIKind.TIME_SERIES, KPIKind.COHORT} and kpi.time_dimension is None:
        raise KPICompilationError(
            f"{kpi.name!r}: kind={kpi.kind.value} requires time_dimension."
        )


# ---------- Top-level compile ----------


def compile_kpi(
    kpi: KPIDefinition,
    *,
    schema_summary: dict[str, list[str]],
    dialect: str = "postgres",
) -> CompiledKPI:
    """Compile a KPI to a typed Postgres SQL string.

    Raises `KPICompilationError` (a `ValueError` subclass) on invalid shape.
    """
    _validate_against_schema(kpi, schema_summary)

    grain_table = kpi.grain.table
    aggregate = _formula_to_aggregate_expr(kpi.formula, kpi.name)
    aggregate_alias = cast(
        exp.Expression, exp.alias_(aggregate, "value", quoted=False)
    )

    # Build the SELECT projection: bucket (if any), breakdown (if any), value.
    projections: list[exp.Expression] = []
    group_by: list[exp.Expression] = []
    order_by: list[exp.Expression] = []

    if kpi.time_dimension is not None and kpi.kind in {
        KPIKind.TIME_SERIES, KPIKind.COHORT,
    }:
        bucket_expr = _time_bucket_expr(kpi.time_dimension, kpi.kind)
        bucket_alias = cast(
            exp.Expression, exp.alias_(bucket_expr, "bucket", quoted=False)
        )
        projections.append(bucket_alias)
        group_by.append(bucket_expr)
        order_by.append(bucket_expr)

    if kpi.breakdown_dimension is not None and kpi.kind in {
        KPIKind.COMPARISON, KPIKind.TOP_N, KPIKind.DISTRIBUTION,
    }:
        breakdown = _column_ref_to_expr(kpi.breakdown_dimension)
        breakdown_alias = cast(
            exp.Expression, exp.alias_(breakdown, "dimension", quoted=False)
        )
        projections.append(breakdown_alias)
        group_by.append(breakdown)

    projections.append(aggregate_alias)

    # Build SELECT … FROM <grain_table> WHERE … GROUP BY … ORDER BY … LIMIT
    select_stmt = (
        exp.Select(expressions=projections)
        .from_(quote_identifier(grain_table))
    )

    where_expr = _combine_filters(kpi.filters)
    if where_expr is not None:
        select_stmt = select_stmt.where(where_expr)

    if group_by:
        select_stmt = select_stmt.group_by(*group_by)

    if order_by:
        select_stmt = select_stmt.order_by(*order_by)

    if kpi.kind == KPIKind.TOP_N:
        # TOP_N: order by the aggregate descending; agent doesn't supply N
        # in the v1 schema, so we cap at 10 deterministically.
        select_stmt = select_stmt.order_by(exp.Ordered(this=aggregate, desc=True))
        select_stmt = select_stmt.limit(10)

    sql = select_stmt.sql(dialect=dialect)

    # Round-trip parse confirms the AST renders to syntactically valid SQL.
    try:
        sqlglot.parse_one(sql, read=dialect)
    except ParseError as exc:
        raise KPICompilationError(
            f"{kpi.name!r}: emitted SQL failed to re-parse: {exc}"
        ) from exc

    return CompiledKPI(
        name=kpi.name,
        sql=sql,
        grain_table=grain_table,
        time_dimension=(
            f"{kpi.time_dimension.table}.{kpi.time_dimension.column}"
            if kpi.time_dimension is not None
            else None
        ),
        breakdown_dimension=(
            f"{kpi.breakdown_dimension.table}.{kpi.breakdown_dimension.column}"
            if kpi.breakdown_dimension is not None
            else None
        ),
    )
