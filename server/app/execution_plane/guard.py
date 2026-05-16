"""SQLGlot-backed SQL rendering and safety checks."""

from __future__ import annotations

import sqlglot
from sqlglot import exp

from app.execution_plane.contracts import PlanCompileError

_FORBIDDEN_EXPRESSIONS = (
    exp.Alter,
    exp.Cache,
    exp.Command,
    exp.Create,
    exp.Delete,
    exp.Drop,
    exp.Insert,
    exp.Transaction,
    exp.Uncache,
    exp.Update,
    exp.Use,
)


def render_readonly_select(
    sql: str,
    *,
    allowed_tables: set[str],
    stage: str,
) -> str:
    """Parse, validate, and render a single read-only DuckDB SELECT.

    The compiler may assemble small fragments, but every executable statement
    crosses this boundary before it reaches DuckDB.
    """
    try:
        expressions = sqlglot.parse(sql, read="duckdb")
    except sqlglot.errors.SqlglotError as exc:
        raise PlanCompileError(
            "Compiled SQL could not be parsed",
            details={"stage": stage, "error": str(exc)},
        ) from exc

    if len(expressions) != 1:
        raise PlanCompileError(
            "Compiled SQL must contain exactly one statement",
            details={"stage": stage, "statement_count": len(expressions)},
        )

    expression = expressions[0]
    if expression is None:
        raise PlanCompileError(
            "Compiled SQL parser returned an empty statement",
            details={"stage": stage},
        )
    if not isinstance(expression, exp.Select):
        raise PlanCompileError(
            "Compiled SQL must be a SELECT",
            details={"stage": stage, "root": expression.key},
        )

    forbidden = next(expression.find_all(*_FORBIDDEN_EXPRESSIONS), None)
    if forbidden is not None:
        raise PlanCompileError(
            "Compiled SQL contains a forbidden expression",
            details={"stage": stage, "expression": forbidden.key},
        )

    table_names = {table.name for table in expression.find_all(exp.Table)}
    unknown_tables = sorted(table_names - allowed_tables)
    if unknown_tables:
        raise PlanCompileError(
            "Compiled SQL references tables outside the execution catalog",
            details={"stage": stage, "tables": unknown_tables},
        )

    return expression.sql(dialect="duckdb")


def count_query(sql: str, *, allowed_tables: set[str]) -> str:
    return render_readonly_select(
        f"SELECT count(*) AS row_count FROM ({sql}) AS result",
        allowed_tables=allowed_tables,
        stage="count",
    )


def preview_query(sql: str, *, allowed_tables: set[str], limit: int) -> str:
    return render_readonly_select(
        f"SELECT * FROM ({sql}) AS result LIMIT {limit}",
        allowed_tables=allowed_tables,
        stage="preview",
    )
