"""Deterministic ChangePlan → child SchemaIR applier.

Per docs/40-features/AGENT-CHG.md §3.4. Walks a typed `ChangePlan` against
a parent `SchemaIR` and returns a new child IR with the mutations applied.
Pure function: same plan + same parent → same child IR.

This is the seam between agent (decides what to change) and compiler
(emits typed IR). The CoherenceGate validates the result downstream.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.agents.specialists.change_planner.types import (
    ChangePlan,
    IRMutation,
    MutationKind,
)
from app.core.errors import BasefloError
from app.engines.schema.enums import (
    Cardinality,
    OnDelete,
    PhysicalType,
    SemanticType,
)
from app.engines.schema.ir import (
    ColumnIR,
    RelationshipIR,
    SchemaIR,
    TableIR,
)


__all__ = ["apply_change_plan"]


def apply_change_plan(*, parent: SchemaIR, plan: ChangePlan, applied_by: str) -> SchemaIR:
    """Apply each mutation in `plan` to `parent`, returning the child IR.

    `applied_by` becomes the child's `composed_by` field for traceability.
    Raises `BasefloError(BF-SCHEMA-NNN)` on malformed mutations — the
    ChangePlanner's validator should have caught these, but the applier is
    the last gate before the typed IR persists.
    """
    tables: list[TableIR] = list(parent.tables)
    relationships: list[RelationshipIR] = list(parent.relationships)
    indexes = list(parent.indexes)
    assumptions = list(parent.assumptions)

    for index, mutation in enumerate(plan.mutations):
        try:
            tables, relationships = _apply_mutation(
                mutation, tables=tables, relationships=relationships,
            )
        except BasefloError:
            raise
        except Exception as exc:  # noqa: BLE001 — wrap with mutation context
            raise BasefloError(
                error_code="BF-SCHEMA-001",
                message=(
                    f"Mutation #{index} ({mutation.kind.value} on {mutation.target!r}) "
                    f"failed to apply: {exc!r}"
                ),
                status_code=500,
                cause=exc,
            ) from exc

    return SchemaIR(
        schema_version=parent.schema_version + 1,
        tables=tables,
        relationships=relationships,
        indexes=indexes,
        assumptions=assumptions,
        parent_version_id=parent.parent_version_id,
        composed_at=datetime.now(UTC),
        composed_by=applied_by,
    )


# ---------- per-kind mutation handlers ----------


def _apply_mutation(
    mutation: IRMutation,
    *,
    tables: list[TableIR],
    relationships: list[RelationshipIR],
) -> tuple[list[TableIR], list[RelationshipIR]]:
    if mutation.kind == MutationKind.ADD_TABLE:
        return _add_table(mutation, tables=tables, relationships=relationships)
    if mutation.kind == MutationKind.REMOVE_TABLE:
        return _remove_table(mutation, tables=tables, relationships=relationships)
    if mutation.kind == MutationKind.ADD_COLUMN:
        return _add_column(mutation, tables=tables, relationships=relationships)
    if mutation.kind == MutationKind.REMOVE_COLUMN:
        return _remove_column(mutation, tables=tables, relationships=relationships)
    if mutation.kind == MutationKind.RENAME_COLUMN:
        return _rename_column(mutation, tables=tables, relationships=relationships)
    if mutation.kind == MutationKind.ADD_RELATIONSHIP:
        return _add_relationship(mutation, tables=tables, relationships=relationships)
    if mutation.kind == MutationKind.REMOVE_RELATIONSHIP:
        return _remove_relationship(
            mutation, tables=tables, relationships=relationships
        )
    raise BasefloError(
        error_code="BF-SCHEMA-001",
        message=f"Unsupported mutation kind: {mutation.kind!r}.",
        status_code=500,
    )


def _add_table(
    m: IRMutation,
    *,
    tables: list[TableIR],
    relationships: list[RelationshipIR],
) -> tuple[list[TableIR], list[RelationshipIR]]:
    if any(t.name == m.target for t in tables):
        raise BasefloError(
            error_code="BF-SCHEMA-001",
            message=f"ADD_TABLE: table {m.target!r} already exists.",
            status_code=400,
        )
    columns_payload = m.payload.get("columns") or []
    if not isinstance(columns_payload, list) or not columns_payload:
        raise BasefloError(
            error_code="BF-SCHEMA-001",
            message=f"ADD_TABLE {m.target!r}: payload['columns'] must be a non-empty list.",
            status_code=400,
        )
    primary_key = m.payload.get("primary_key") or []
    if not isinstance(primary_key, list) or not primary_key:
        raise BasefloError(
            error_code="BF-SCHEMA-001",
            message=f"ADD_TABLE {m.target!r}: payload['primary_key'] required.",
            status_code=400,
        )

    columns = [_column_from_payload(c) for c in columns_payload]
    label = str(m.payload.get("label") or m.target.replace("_", " ").title())
    purpose = str(m.payload.get("purpose") or f"Holds {m.target}.")
    grain = str(m.payload.get("grain") or f"one row per {m.target.rstrip('s') or m.target}")
    new_table = TableIR(
        name=m.target,
        label=label,
        purpose=purpose,
        grain=grain,
        primary_key=[str(k) for k in primary_key],
        columns=columns,
    )
    return [*tables, new_table], relationships


def _remove_table(
    m: IRMutation,
    *,
    tables: list[TableIR],
    relationships: list[RelationshipIR],
) -> tuple[list[TableIR], list[RelationshipIR]]:
    if not any(t.name == m.target for t in tables):
        raise BasefloError(
            error_code="BF-SCHEMA-001",
            message=f"REMOVE_TABLE: table {m.target!r} not found.",
            status_code=400,
        )
    new_tables = [t for t in tables if t.name != m.target]
    new_rels = [
        r for r in relationships
        if r.from_table != m.target and r.to_table != m.target
    ]
    return new_tables, new_rels


def _add_column(
    m: IRMutation,
    *,
    tables: list[TableIR],
    relationships: list[RelationshipIR],
) -> tuple[list[TableIR], list[RelationshipIR]]:
    table_name, column_name = _split_dotted(m.target, op="ADD_COLUMN")
    new_col = ColumnIR(
        name=column_name,
        label=str(m.payload.get("label") or column_name.replace("_", " ").title()),
        semantic_type=SemanticType(m.payload["semantic_type"]),
        physical_type=PhysicalType(m.payload["physical_type"]),
        nullable=bool(m.payload["nullable"]),
        enum_values=m.payload.get("enum_values"),
        currency=m.payload.get("currency"),
        is_minor_unit=bool(m.payload.get("is_minor_unit", False)),
        pii_masked_by_default=bool(m.payload.get("pii_masked_by_default", False)),
    )

    new_tables: list[TableIR] = []
    found = False
    for table in tables:
        if table.name == table_name:
            found = True
            if any(c.name == column_name for c in table.columns):
                raise BasefloError(
                    error_code="BF-SCHEMA-001",
                    message=f"ADD_COLUMN: {table_name}.{column_name} already exists.",
                    status_code=400,
                )
            new_tables.append(
                table.model_copy(update={"columns": [*table.columns, new_col]})
            )
        else:
            new_tables.append(table)
    if not found:
        raise BasefloError(
            error_code="BF-SCHEMA-001",
            message=f"ADD_COLUMN: table {table_name!r} not found.",
            status_code=400,
        )
    return new_tables, relationships


def _remove_column(
    m: IRMutation,
    *,
    tables: list[TableIR],
    relationships: list[RelationshipIR],
) -> tuple[list[TableIR], list[RelationshipIR]]:
    table_name, column_name = _split_dotted(m.target, op="REMOVE_COLUMN")
    new_tables: list[TableIR] = []
    found_table = False
    found_col = False
    for table in tables:
        if table.name == table_name:
            found_table = True
            if column_name in table.primary_key:
                raise BasefloError(
                    error_code="BF-SCHEMA-001",
                    message=(
                        f"REMOVE_COLUMN: {table_name}.{column_name} is part of the "
                        f"primary key; remove the table or change the PK first."
                    ),
                    status_code=400,
                )
            new_cols = [c for c in table.columns if c.name != column_name]
            if len(new_cols) == len(table.columns):
                continue  # not found in this table; raise after loop
            found_col = True
            new_tables.append(table.model_copy(update={"columns": new_cols}))
        else:
            new_tables.append(table)
    if not found_table:
        raise BasefloError(
            error_code="BF-SCHEMA-001",
            message=f"REMOVE_COLUMN: table {table_name!r} not found.",
            status_code=400,
        )
    if not found_col:
        raise BasefloError(
            error_code="BF-SCHEMA-001",
            message=f"REMOVE_COLUMN: {table_name}.{column_name} not found.",
            status_code=400,
        )
    return new_tables, relationships


def _rename_column(
    m: IRMutation,
    *,
    tables: list[TableIR],
    relationships: list[RelationshipIR],
) -> tuple[list[TableIR], list[RelationshipIR]]:
    table_name, old_name = _split_dotted(m.target, op="RENAME_COLUMN")
    new_name = str(m.payload["new_name"])

    new_tables: list[TableIR] = []
    found_col = False
    for table in tables:
        if table.name == table_name:
            cols = []
            for col in table.columns:
                if col.name == old_name:
                    found_col = True
                    cols.append(col.model_copy(update={"name": new_name}))
                else:
                    cols.append(col)
            new_pk = [
                new_name if k == old_name else k for k in table.primary_key
            ]
            new_tables.append(
                table.model_copy(update={"columns": cols, "primary_key": new_pk})
            )
        else:
            new_tables.append(table)
    if not found_col:
        raise BasefloError(
            error_code="BF-SCHEMA-001",
            message=f"RENAME_COLUMN: {table_name}.{old_name} not found.",
            status_code=400,
        )

    # Update relationship column lists if they referenced the renamed column.
    new_rels: list[RelationshipIR] = []
    for rel in relationships:
        update: dict[str, list[str]] = {}
        if rel.from_table == table_name:
            update["from_columns"] = [
                new_name if c == old_name else c for c in rel.from_columns
            ]
        if rel.to_table == table_name:
            update["to_columns"] = [
                new_name if c == old_name else c for c in rel.to_columns
            ]
        new_rels.append(rel.model_copy(update=update) if update else rel)

    return new_tables, new_rels


def _add_relationship(
    m: IRMutation,
    *,
    tables: list[TableIR],
    relationships: list[RelationshipIR],
) -> tuple[list[TableIR], list[RelationshipIR]]:
    if "↔" not in m.target and "<->" not in m.target:
        raise BasefloError(
            error_code="BF-SCHEMA-001",
            message=(
                "ADD_RELATIONSHIP target must be 'from_table↔to_table' "
                f"(or 'from<->to'); got {m.target!r}."
            ),
            status_code=400,
        )
    sep = "↔" if "↔" in m.target else "<->"
    from_table, to_table = m.target.split(sep, 1)
    table_names = {t.name for t in tables}
    if from_table not in table_names or to_table not in table_names:
        raise BasefloError(
            error_code="BF-SCHEMA-001",
            message=(
                f"ADD_RELATIONSHIP {m.target!r}: one of "
                f"{from_table!r} / {to_table!r} not in IR."
            ),
            status_code=400,
        )

    cardinality = Cardinality(m.payload["cardinality"])
    new_rel = RelationshipIR(
        name=str(m.payload.get("name") or f"{from_table}_{to_table}"),
        from_table=from_table,
        from_columns=[str(c) for c in m.payload["from_columns"]],
        to_table=to_table,
        to_columns=[str(c) for c in m.payload["to_columns"]],
        cardinality=cardinality,
        on_delete=OnDelete(m.payload.get("on_delete", "RESTRICT")),
        optional_from=bool(m.payload.get("optional_from", False)),
        optional_to=bool(m.payload.get("optional_to", False)),
    )
    return tables, [*relationships, new_rel]


def _remove_relationship(
    m: IRMutation,
    *,
    tables: list[TableIR],
    relationships: list[RelationshipIR],
) -> tuple[list[TableIR], list[RelationshipIR]]:
    new_rels = [r for r in relationships if r.name != m.target]
    if len(new_rels) == len(relationships):
        raise BasefloError(
            error_code="BF-SCHEMA-001",
            message=f"REMOVE_RELATIONSHIP: {m.target!r} not found.",
            status_code=400,
        )
    return tables, new_rels


# ---------- helpers ----------


def _split_dotted(target: str, *, op: str) -> tuple[str, str]:
    if "." not in target:
        raise BasefloError(
            error_code="BF-SCHEMA-001",
            message=f"{op} target must be 'table.column'; got {target!r}.",
            status_code=400,
        )
    table_name, _, column_name = target.partition(".")
    return table_name, column_name


def _column_from_payload(payload: Any) -> ColumnIR:
    if not isinstance(payload, dict):
        raise BasefloError(
            error_code="BF-SCHEMA-001",
            message="ADD_TABLE: each entry in payload['columns'] must be a dict.",
            status_code=400,
        )
    return ColumnIR(
        name=str(payload["name"]),
        label=str(payload.get("label") or str(payload["name"]).replace("_", " ").title()),
        semantic_type=SemanticType(payload["semantic_type"]),
        physical_type=PhysicalType(payload["physical_type"]),
        nullable=bool(payload.get("nullable", True)),
        enum_values=payload.get("enum_values"),
        currency=payload.get("currency"),
        is_minor_unit=bool(payload.get("is_minor_unit", False)),
        pii_masked_by_default=bool(payload.get("pii_masked_by_default", False)),
    )
