"""Schema IR → Postgres DDL emitter.

Per docs/40-features/IR-DDL.md.

Pure function: same `SchemaIR` always produces the same `EmissionResult`.
The result's `sql` is parsed back through SQLGlot for syntactic validation;
the `ast_hash` is a SHA-256 over the canonical (normalized + parsed) SQL.

Constraints from `ConstraintProposer` are NOT consumed here in M1 — that
flow is not available in v1. M1 emits structural
DDL (tables, columns with NOT NULL + defaults, primary keys, FKs, indexes,
audit timestamp triggers, and STATUS CHECK constraints derived from
`ColumnIR.enum_values`).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

import sqlglot
from sqlglot.errors import ParseError

from app.core.errors import BasefloError
from app.engines.schema.compatibility import normalize_ir, validate as ir_validate
from app.engines.schema.ddl.identifiers import (
    is_safe_identifier,
    quote_identifier,
    quote_string_literal,
)
from app.engines.schema.enums import (
    Cardinality,
    OnDelete,
    PhysicalType,
    SemanticType,
)
from app.engines.schema.ir import ColumnIR, IndexIR, RelationshipIR, SchemaIR, TableIR


# ---------- Public types ----------


@dataclass(frozen=True, slots=True)
class EmissionWarning:
    code: str
    message: str
    target: str


@dataclass(frozen=True, slots=True)
class EmissionResult:
    sql: str
    ast_hash: str
    table_count: int
    column_count: int
    relationship_count: int
    index_count: int
    constraint_count: int
    warnings: tuple[EmissionWarning, ...]


# ---------- Type mapping ----------


_PG_TYPE_BY_PHYSICAL: dict[PhysicalType, str] = {
    PhysicalType.UUID: "uuid",
    PhysicalType.BIGINT: "bigint",
    PhysicalType.INT: "integer",
    PhysicalType.SMALLINT: "smallint",
    PhysicalType.NUMERIC: "numeric(20, 4)",
    PhysicalType.TEXT: "text",
    PhysicalType.VARCHAR: "varchar(255)",
    PhysicalType.BOOLEAN: "boolean",
    PhysicalType.TIMESTAMPTZ: "timestamptz",
    PhysicalType.DATE: "date",
    PhysicalType.JSONB: "jsonb",
    PhysicalType.BYTEA: "bytea",
}


def _render_physical_type(col: ColumnIR) -> str:
    base = _PG_TYPE_BY_PHYSICAL.get(col.physical_type)
    if base is None:  # pragma: no cover — guarded by IR enum
        raise BasefloError(
            error_code="BF-SCHEMA-EMIT-002",
            message=f"Unsupported physical_type {col.physical_type!r} for Postgres dialect.",
            status_code=500,
        )
    return base


def _render_default(value: str | int | float | bool | None) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (int, float)):
        return repr(value)
    return quote_string_literal(str(value))


# ---------- Column emission ----------


def _emit_column(col: ColumnIR, warnings: list[EmissionWarning]) -> str:
    if not is_safe_identifier(col.name):
        warnings.append(
            EmissionWarning(
                code="BF-SCHEMA-EMIT-003",
                message=f"Column name {col.name!r} required quoting.",
                target=col.name,
            )
        )

    parts = [quote_identifier(col.name), _render_physical_type(col)]
    if not col.nullable:
        parts.append("NOT NULL")
    if col.default is not None:
        parts.append(f"DEFAULT {_render_default(col.default)}")
    return " ".join(parts)


# ---------- Constraint emission (status enums) ----------


def _emit_status_check(table_name: str, col: ColumnIR) -> str | None:
    if col.semantic_type != SemanticType.STATUS:
        return None
    if not col.enum_values:
        return None
    values_clause = ", ".join(quote_string_literal(v) for v in col.enum_values)
    cname = f"ck__{table_name}__{col.name}_enum"
    return (
        f"CONSTRAINT {quote_identifier(cname)} "
        f"CHECK ({quote_identifier(col.name)} IN ({values_clause}))"
    )


# ---------- Table emission ----------


def _emit_table(table: TableIR, warnings: list[EmissionWarning]) -> tuple[str, int]:
    """Return `(create_table_sql, constraint_count)`."""
    if not is_safe_identifier(table.name):
        warnings.append(
            EmissionWarning(
                code="BF-SCHEMA-EMIT-003",
                message=f"Table name {table.name!r} required quoting.",
                target=table.name,
            )
        )

    column_lines = [_emit_column(c, warnings) for c in table.columns]

    pk_columns_quoted = ", ".join(quote_identifier(c) for c in table.primary_key)
    pk_constraint = (
        f"CONSTRAINT {quote_identifier(f'pk__{table.name}')} "
        f"PRIMARY KEY ({pk_columns_quoted})"
    )

    constraint_lines: list[str] = [pk_constraint]
    for col in table.columns:
        check = _emit_status_check(table.name, col)
        if check is not None:
            constraint_lines.append(check)

    body = ",\n  ".join(column_lines + constraint_lines)
    sql = (
        f"CREATE TABLE {quote_identifier(table.name)} (\n  {body}\n);"
    )
    return sql, len(constraint_lines)


# ---------- Relationship (FK) emission ----------


_ON_DELETE_SQL: dict[OnDelete, str] = {
    OnDelete.RESTRICT: "RESTRICT",
    OnDelete.CASCADE: "CASCADE",
    OnDelete.SET_NULL: "SET NULL",
}


def _emit_relationship(rel: RelationshipIR) -> str:
    """Emit ALTER TABLE … ADD CONSTRAINT FOREIGN KEY …

    The FK lives on the many-side per cardinality direction:
      *..1 (MANY_TO_ONE) — FK on `from_table`, references `to_table`.
      1..* (ONE_TO_MANY) — FK on `to_table`, references `from_table`.
      1..1 (ONE_TO_ONE)  — FK on `from_table` (with UNIQUE on the FK column).
      *..* (MANY_TO_MANY) — caller is expected to model a join table; this
                            relationship represents one of its FKs and is
                            emitted on whichever side `from_table` is.
    """
    if rel.cardinality == Cardinality.ONE_TO_MANY:
        owner_table = rel.to_table
        owner_columns = rel.to_columns
        ref_table = rel.from_table
        ref_columns = rel.from_columns
    else:
        owner_table = rel.from_table
        owner_columns = rel.from_columns
        ref_table = rel.to_table
        ref_columns = rel.to_columns

    constraint_name = f"fk__{owner_table}__{rel.name}"
    cols = ", ".join(quote_identifier(c) for c in owner_columns)
    refs = ", ".join(quote_identifier(c) for c in ref_columns)
    return (
        f"ALTER TABLE {quote_identifier(owner_table)} "
        f"ADD CONSTRAINT {quote_identifier(constraint_name)} "
        f"FOREIGN KEY ({cols}) REFERENCES {quote_identifier(ref_table)} ({refs}) "
        f"ON DELETE {_ON_DELETE_SQL[rel.on_delete]};"
    )


def _fk_owner_side(rel: RelationshipIR) -> tuple[str, list[str]]:
    if rel.cardinality == Cardinality.ONE_TO_MANY:
        return rel.to_table, rel.to_columns
    return rel.from_table, rel.from_columns


# ---------- Index emission ----------


def _emit_explicit_index(idx: IndexIR) -> str:
    cols = ", ".join(quote_identifier(c) for c in idx.columns)
    head = "CREATE UNIQUE INDEX" if idx.unique else "CREATE INDEX"
    base = f"{head} {quote_identifier(idx.name)} ON {quote_identifier(idx.table)} ({cols})"
    if idx.partial_predicate:
        base += f" WHERE {idx.partial_predicate}"
    return base + ";"


def _emit_fk_index(rel: RelationshipIR) -> str:
    """FK columns must be indexed (Postgres doesn't auto-index FKs)."""
    owner_table, owner_columns = _fk_owner_side(rel)
    cols = ", ".join(quote_identifier(c) for c in owner_columns)
    name = f"ix__{owner_table}__{rel.name}"
    return f"CREATE INDEX {quote_identifier(name)} ON {quote_identifier(owner_table)} ({cols});"


# ---------- Audit timestamps ----------


def _has_temporal_audit_columns(table: TableIR) -> bool:
    names = {c.name for c in table.columns}
    return "created_at" in names and "updated_at" in names


def _emit_audit_trigger(table: TableIR) -> str | None:
    """Attach the shared `baseflo_set_updated_at` trigger when the table has
    a `created_at` + `updated_at` pair.

    The trigger function itself is created globally by the existing migration
    `20260507_0001_init_organizations_users_memberships.py`. The DDL emitter
    references it; if it doesn't exist in the target DB the engine fails
    fast at execution time.
    """
    if not _has_temporal_audit_columns(table):
        return None
    name = f"trg__{table.name}__set_updated_at"
    return (
        f"CREATE TRIGGER {quote_identifier(name)} "
        f"BEFORE UPDATE ON {quote_identifier(table.name)} "
        f"FOR EACH ROW EXECUTE FUNCTION baseflo_set_updated_at();"
    )


# ---------- Top-level entrypoint ----------


def compile_ir(ir: SchemaIR) -> EmissionResult:
    """Compile a `SchemaIR` to Postgres DDL.

    Raises `BF-SCHEMA-EMIT-001` if the IR fails compatibility validation.
    """
    ir = normalize_ir(ir)
    report = ir_validate(ir)
    if not report.passed:
        raise BasefloError(
            error_code="BF-SCHEMA-EMIT-001",
            message=f"Refusing to compile invalid IR: {report.summary()}",
            status_code=500,
            details={
                "findings": [
                    {"code": f.error_code, "target": f.target, "message": f.message}
                    for f in report.findings
                ]
            },
        )

    warnings: list[EmissionWarning] = []
    statements: list[str] = []

    # 1) Tables
    constraint_count = 0
    column_count = 0
    for table in ir.tables:
        sql, count = _emit_table(table, warnings)
        statements.append(sql)
        constraint_count += count
        column_count += len(table.columns)
        trigger = _emit_audit_trigger(table)
        if trigger is not None:
            statements.append(trigger)

    # 2) Relationships (FKs)
    for rel in ir.relationships:
        statements.append(_emit_relationship(rel))
        statements.append(_emit_fk_index(rel))

    # 3) Explicit indexes
    for idx in ir.indexes:
        statements.append(_emit_explicit_index(idx))

    sql = "\n".join(statements)

    # 4) Round-trip parse via SQLGlot — confirms our emission is well-formed.
    try:
        parsed = sqlglot.parse(sql, read="postgres")
    except ParseError as exc:
        raise BasefloError(
            error_code="BF-SCHEMA-EMIT-002",
            message=f"Emitted DDL failed SQLGlot parse: {exc}",
            status_code=500,
            details={"sql": sql},
            cause=exc,
        ) from exc

    # 5) Stable hash over the canonicalised SQLGlot AST.
    ast_canonical = "\n".join(
        statement.sql(dialect="postgres", normalize=True)
        for statement in parsed
        if statement is not None
    )
    ast_hash = hashlib.sha256(ast_canonical.encode("utf-8")).hexdigest()

    return EmissionResult(
        sql=sql,
        ast_hash=ast_hash,
        table_count=len(ir.tables),
        column_count=column_count,
        relationship_count=len(ir.relationships),
        index_count=len(ir.indexes) + len(ir.relationships),
        constraint_count=constraint_count,
        warnings=tuple(warnings),
    )
