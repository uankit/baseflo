"""Small SQL helpers for the execution plane."""

from __future__ import annotations

import hashlib
import re
from typing import Any

from app.data_plane.naming import quote_ident
from app.execution_plane.contracts import PlanCompileError, PlanValidationError

_ALIAS_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]{0,80}$")
_SLUG_RE = re.compile(r"[^a-z0-9]+")


def slug(value: str, *, fallback: str = "col") -> str:
    raw = _SLUG_RE.sub("_", value.lower()).strip("_")
    return raw[:60] or fallback


def short_hash(value: str, *, length: int = 8) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:length]


def safe_alias(value: str) -> str:
    alias = slug(value)
    if not alias or alias[0].isdigit():
        alias = f"col_{alias}"
    alias = alias[:72]
    if not _ALIAS_RE.fullmatch(alias):
        raise PlanValidationError(f"Unsafe alias: {value}")
    return alias


def unique_alias(base: str, used: set[str], *, salt: str) -> str:
    alias = safe_alias(base)
    if alias not in used:
        used.add(alias)
        return alias
    alias = safe_alias(f"{alias}_{short_hash(salt)}")
    suffix = 2
    candidate = alias
    while candidate in used:
        candidate = safe_alias(f"{alias}_{suffix}")
        suffix += 1
    used.add(candidate)
    return candidate


def validate_operator_id(value: str) -> None:
    if not value or len(value) > 120:
        raise PlanValidationError(f"Invalid operator id: {value!r}")


def validate_measure_alias(value: str) -> str:
    alias = safe_alias(value)
    if alias != value:
        raise PlanValidationError(f"Measure alias must already be a safe identifier: {value}")
    return alias


def literal_sql(value: str | int | float | bool | None) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int | float):
        return str(value)
    return "'" + value.replace("'", "''") + "'"


def literal_sql_for_type(value: Any, *, observed_type: str) -> str:
    if value is None:
        return "NULL"
    if is_numeric_type(observed_type):
        try:
            return str(float(value))
        except (TypeError, ValueError) as exc:
            raise PlanCompileError(
                "Numeric filter value could not be coerced",
                details={"value": value, "observed_type": observed_type},
            ) from exc
    if observed_type == "boolean":
        if isinstance(value, bool):
            return "true" if value else "false"
        text = str(value).strip().lower()
        if text in {"true", "1", "yes"}:
            return "true"
        if text in {"false", "0", "no"}:
            return "false"
        raise PlanCompileError(
            "Boolean filter value could not be coerced",
            details={"value": value, "observed_type": observed_type},
        )
    if observed_type == "date":
        return f"DATE {literal_sql(str(value))}"
    if observed_type == "datetime":
        return f"TIMESTAMP {literal_sql(str(value))}"
    return literal_sql(str(value))


def q(value: str) -> str:
    return quote_ident(value)


def is_numeric_type(observed_type: str) -> bool:
    return observed_type in {"integer", "number", "money"}


def numeric_expr(alias: str, *, relation_alias: str = "src") -> str:
    return f"try_cast({relation_alias}.{q(alias)} AS DOUBLE)"


def column_expr(alias: str, *, relation_alias: str = "src") -> str:
    return f"{relation_alias}.{q(alias)}"


def typed_expr(alias: str, *, observed_type: str, relation_alias: str = "src") -> str:
    if is_numeric_type(observed_type):
        return numeric_expr(alias, relation_alias=relation_alias)
    if observed_type == "boolean":
        return f"try_cast({relation_alias}.{q(alias)} AS BOOLEAN)"
    if observed_type == "date":
        return f"try_cast({relation_alias}.{q(alias)} AS DATE)"
    if observed_type == "datetime":
        return f"try_cast({relation_alias}.{q(alias)} AS TIMESTAMP)"
    return column_expr(alias, relation_alias=relation_alias)


def predicate_sql(
    *,
    alias: str,
    observed_type: str,
    operator: str,
    value: Any,
    relation_alias: str = "src",
) -> str:
    expr = typed_expr(alias, observed_type=observed_type, relation_alias=relation_alias)
    if operator == "is_null":
        return f"{expr} IS NULL"
    if operator == "is_not_null":
        return f"{expr} IS NOT NULL"
    return f"{expr} {operator} {literal_sql_for_type(value, observed_type=observed_type)}"
