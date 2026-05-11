"""Cross-cutting structural validators — `BF-SCHEMA-NNN`.

Per docs/40-features/IR-CORE.md §3.4. These are the deterministic checks the
compiler runs after agent composition. They verify *structure*, never *meaning*.

Each check is a typed predicate; `validate(ir)` runs them all and returns a
typed `ValidationReport`. The agent runtime + saga use the report to decide
between repair routing and ship.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from app.engines.schema.enums import (
    PII_SEMANTIC_TYPES,
    PhysicalType,
    SemanticType,
)
from app.engines.schema.ir import Assumption, ColumnIR, RelationshipIR, SchemaIR, TableIR

if TYPE_CHECKING:
    from collections.abc import Callable


@dataclass(frozen=True, slots=True)
class ValidationFinding:
    error_code: str
    message: str
    target: str  # natural identifier for the offending element


@dataclass(frozen=True, slots=True)
class ValidationReport:
    findings: tuple[ValidationFinding, ...]

    @property
    def passed(self) -> bool:
        return not self.findings

    def summary(self) -> str:
        if self.passed:
            return "ok"
        return "; ".join(f"{f.error_code} {f.target}: {f.message}" for f in self.findings)


# ---------- Individual checks ----------


def _check_non_empty(ir: SchemaIR) -> list[ValidationFinding]:
    if not ir.tables:
        return [ValidationFinding("BF-SCHEMA-010", "IR has no tables.", "schema")]
    return []


def _check_money_columns(ir: SchemaIR) -> list[ValidationFinding]:
    """Money columns must be BIGINT minor-unit. Currency context is reported
    in one of three shapes (see `ColumnIR` docstring); the validator enforces
    that the chosen shape is internally consistent, but does NOT require that
    a currency be known — currency-unknown is a legitimate observation and
    becomes a workspace assumption surfaced to the user, not a build error.
    """
    findings: list[ValidationFinding] = []
    for table in ir.tables:
        sibling_text_columns = {
            c.name for c in table.columns
            if c.physical_type == PhysicalType.TEXT
        }
        for col in table.columns:
            if col.semantic_type != SemanticType.MONEY:
                continue
            if col.physical_type != PhysicalType.BIGINT:
                findings.append(
                    ValidationFinding(
                        error_code="BF-SCHEMA-002",
                        message="MONEY columns must be BIGINT minor-unit.",
                        target=f"{table.name}.{col.name}",
                    )
                )
            if not col.is_minor_unit:
                findings.append(
                    ValidationFinding(
                        error_code="BF-SCHEMA-002",
                        message="MONEY column missing is_minor_unit=True.",
                        target=f"{table.name}.{col.name}",
                    )
                )
            if col.currency and col.currency_column:
                findings.append(
                    ValidationFinding(
                        error_code="BF-SCHEMA-002",
                        message=(
                            "MONEY column has both `currency` and `currency_column` "
                            "set; pick exactly one."
                        ),
                        target=f"{table.name}.{col.name}",
                    )
                )
            if col.currency_column and col.currency_column not in sibling_text_columns:
                findings.append(
                    ValidationFinding(
                        error_code="BF-SCHEMA-002",
                        message=(
                            f"MONEY column references currency_column "
                            f"{col.currency_column!r}, which is not a TEXT column "
                            f"on the same table."
                        ),
                        target=f"{table.name}.{col.name}",
                    )
                )
    return findings


def _check_status_columns(ir: SchemaIR) -> list[ValidationFinding]:
    findings: list[ValidationFinding] = []
    for table in ir.tables:
        for col in table.columns:
            if col.semantic_type == SemanticType.STATUS and not col.enum_values:
                findings.append(
                    ValidationFinding(
                        error_code="BF-SCHEMA-003",
                        message="STATUS column missing enum_values.",
                        target=f"{table.name}.{col.name}",
                    )
                )
    return findings


def _check_temporal_columns(ir: SchemaIR) -> list[ValidationFinding]:
    findings: list[ValidationFinding] = []
    temporal_physical = {PhysicalType.DATE, PhysicalType.TIMESTAMPTZ}
    for table in ir.tables:
        for col in table.columns:
            if (
                col.semantic_type == SemanticType.TEMPORAL
                and col.physical_type not in temporal_physical
            ):
                findings.append(
                    ValidationFinding(
                        error_code="BF-SCHEMA-011",
                        message=(
                            "TEMPORAL columns must be DATE or TIMESTAMPTZ so "
                            "time windows can execute deterministically."
                        ),
                        target=f"{table.name}.{col.name}",
                    )
                )
    return findings


def _check_relationship_endpoints_exist(ir: SchemaIR) -> list[ValidationFinding]:
    table_names = {t.name for t in ir.tables}
    findings: list[ValidationFinding] = []
    for rel in ir.relationships:
        if rel.from_table not in table_names:
            findings.append(
                ValidationFinding(
                    error_code="BF-SCHEMA-004",
                    message=f"Relationship from_table {rel.from_table!r} not in schema.",
                    target=f"relationship:{rel.name}",
                )
            )
        if rel.to_table not in table_names:
            findings.append(
                ValidationFinding(
                    error_code="BF-SCHEMA-004",
                    message=f"Relationship to_table {rel.to_table!r} not in schema.",
                    target=f"relationship:{rel.name}",
                )
            )
    return findings


def _check_relationship_columns_exist(ir: SchemaIR) -> list[ValidationFinding]:
    findings: list[ValidationFinding] = []
    by_name = {t.name: t for t in ir.tables}
    for rel in ir.relationships:
        findings += _verify_columns_present(rel, "from", by_name.get(rel.from_table))
        findings += _verify_columns_present(rel, "to", by_name.get(rel.to_table))
    return findings


def _verify_columns_present(
    rel: RelationshipIR, side: str, table: TableIR | None
) -> list[ValidationFinding]:
    if table is None:
        return []  # endpoint check already covers missing tables
    needed = rel.from_columns if side == "from" else rel.to_columns
    have = {c.name for c in table.columns}
    missing = [c for c in needed if c not in have]
    if not missing:
        return []
    return [
        ValidationFinding(
            error_code="BF-SCHEMA-005",
            message=(
                f"Relationship {rel.name!r} {side}-columns "
                f"{missing!r} missing from table {table.name!r}."
            ),
            target=f"relationship:{rel.name}",
        )
    ]


def _check_primary_keys(ir: SchemaIR) -> list[ValidationFinding]:
    findings: list[ValidationFinding] = []
    for table in ir.tables:
        if not table.primary_key:
            findings.append(
                ValidationFinding(
                    error_code="BF-SCHEMA-006",
                    message=f"Table {table.name!r} has empty primary_key.",
                    target=f"table:{table.name}",
                )
            )
            continue
        have = {c.name for c in table.columns}
        missing = [c for c in table.primary_key if c not in have]
        if missing:
            findings.append(
                ValidationFinding(
                    error_code="BF-SCHEMA-006",
                    message=(
                        f"Table {table.name!r} primary_key references "
                        f"missing columns {missing!r}."
                    ),
                    target=f"table:{table.name}",
                )
            )
    return findings


def _check_duplicate_identifiers(ir: SchemaIR) -> list[ValidationFinding]:
    findings: list[ValidationFinding] = []
    seen_tables: set[str] = set()
    for table in ir.tables:
        if table.name in seen_tables:
            findings.append(
                ValidationFinding(
                    error_code="BF-SCHEMA-007",
                    message=f"Duplicate table name {table.name!r}.",
                    target=f"table:{table.name}",
                )
            )
        seen_tables.add(table.name)
        seen_cols: set[str] = set()
        for col in table.columns:
            if col.name in seen_cols:
                findings.append(
                    ValidationFinding(
                        error_code="BF-SCHEMA-007",
                        message=f"Duplicate column {col.name!r} in {table.name!r}.",
                        target=f"{table.name}.{col.name}",
                    )
                )
            seen_cols.add(col.name)
    return findings


def _check_reconciliation_policy(ir: SchemaIR) -> list[ValidationFinding]:
    findings: list[ValidationFinding] = []
    for table in ir.tables:
        if table.is_reconciled and table.reconciliation_policy is None:
            findings.append(
                ValidationFinding(
                    error_code="BF-SCHEMA-008",
                    message=(
                        f"Reconciled table {table.name!r} missing reconciliation_policy."
                    ),
                    target=f"table:{table.name}",
                )
            )
    return findings


def _check_pii_masking(ir: SchemaIR) -> list[ValidationFinding]:
    findings: list[ValidationFinding] = []
    for table in ir.tables:
        for col in table.columns:
            if col.semantic_type in PII_SEMANTIC_TYPES and not col.pii_masked_by_default:
                findings.append(
                    ValidationFinding(
                        error_code="BF-SCHEMA-009",
                        message=(
                            f"PII column {table.name}.{col.name} must have "
                            "pii_masked_by_default=True."
                        ),
                        target=f"{table.name}.{col.name}",
                    )
                )
    return findings


# ---------- Composition ----------


_CHECKS: tuple[Callable[[SchemaIR], list[ValidationFinding]], ...] = (
    _check_non_empty,
    _check_money_columns,
    _check_status_columns,
    _check_temporal_columns,
    _check_relationship_endpoints_exist,
    _check_relationship_columns_exist,
    _check_primary_keys,
    _check_duplicate_identifiers,
    _check_reconciliation_policy,
    _check_pii_masking,
)


def normalize_ir(ir: SchemaIR) -> SchemaIR:
    """Auto-fix common IR issues so agentic output passes deterministic validation.

    MONEY columns are forced to BIGINT minor-unit (implementation detail agents
    shouldn't need to know). Reconciled tables missing a policy are downgraded
    to non-reconciled because we can't synthesize join keys without the entity
    reconciliation plan.
    """
    new_tables: list[TableIR] = []
    new_assumptions = list(ir.assumptions)
    assumption_keys = {(a.target, a.text) for a in new_assumptions}
    for table in ir.tables:
        table_changed = False
        by_name = {col.name: col for col in table.columns}
        money_updates: dict[str, dict[str, Any]] = {}
        text_currency_columns: set[str] = set()

        for col in table.columns:
            if col.semantic_type == SemanticType.MONEY:
                updates: dict[str, Any] = {}
                if col.physical_type != PhysicalType.BIGINT:
                    updates["physical_type"] = PhysicalType.BIGINT
                if not col.is_minor_unit:
                    updates["is_minor_unit"] = True
                if col.currency == "":
                    updates["currency"] = None
                currency = updates.get("currency", col.currency)
                if currency and col.currency_column:
                    updates["currency_column"] = None
                elif col.currency_column:
                    currency_col = by_name.get(col.currency_column)
                    if currency_col is None:
                        updates["currency_column"] = None
                        text = (
                            f"Currency for {table.name}.{col.name} was not present "
                            "as a source column; it is unknown and can be supplied "
                            "at query or display time."
                        )
                        key = (f"{table.name}.{col.name}", text)
                        if key not in assumption_keys:
                            new_assumptions.append(
                                Assumption(
                                    target=key[0],
                                    text=key[1],
                                    source_agent="SchemaAgent",
                                )
                            )
                            assumption_keys.add(key)
                    elif currency_col.physical_type != PhysicalType.TEXT:
                        text_currency_columns.add(col.currency_column)
                if updates:
                    money_updates[col.name] = updates

        new_cols: list[ColumnIR] = []
        for col in table.columns:
            updates = dict(money_updates.get(col.name, {}))
            if col.name in text_currency_columns:
                updates.update(
                    {
                        "semantic_type": SemanticType.CATEGORY,
                        "physical_type": PhysicalType.TEXT,
                        "currency": None,
                        "currency_column": None,
                        "is_minor_unit": False,
                    }
                )
            if updates:
                new_cols.append(col.model_copy(update=updates))
            else:
                new_cols.append(col)
        if new_cols != table.columns:
            table_changed = True

        table_updates: dict[str, Any] = {}
        if table.is_reconciled and table.reconciliation_policy is None:
            # Can't synthesize a valid ReconciliationPolicy without join keys,
            # so downgrade to non-reconciled to keep the build moving.
            table_updates["is_reconciled"] = False
            table_changed = True

        if table_changed:
            new_table = table.model_copy(update={"columns": new_cols, **table_updates})
            new_tables.append(new_table)
        else:
            new_tables.append(table)

    return ir.model_copy(update={"tables": new_tables, "assumptions": new_assumptions})


def validate(ir: SchemaIR) -> ValidationReport:
    """Run every cross-cutting check. Order is deterministic."""
    findings: list[ValidationFinding] = []
    for check in _CHECKS:
        findings.extend(check(ir))
    return ValidationReport(findings=tuple(findings))
