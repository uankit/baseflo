"""Shared migration helpers.

Imported by individual revision files to keep boilerplate DRY without forcing
introspection through SQLAlchemy metadata (which would couple migrations to
the current ORM state — Alembic best-practice forbids that).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


def install_updated_at_trigger(table: str) -> None:
    """Attach the shared `baseflo_set_updated_at` trigger to a table."""
    op.execute(
        f"""
        CREATE TRIGGER set_updated_at BEFORE UPDATE ON {table}
        FOR EACH ROW EXECUTE FUNCTION baseflo_set_updated_at();
        """
    )


def drop_updated_at_trigger(table: str) -> None:
    op.execute(f"DROP TRIGGER IF EXISTS set_updated_at ON {table}")


def uuid_pk() -> sa.Column:
    return sa.Column(
        "id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True
    )


def fk_uuid(
    name: str,
    *,
    target: str,
    nullable: bool = False,
    ondelete: str = "CASCADE",
    constraint_name: str | None = None,
) -> sa.Column:
    fk_name = constraint_name or _fk_name(name, target)
    return sa.Column(
        name,
        sa.dialects.postgresql.UUID(as_uuid=True),
        sa.ForeignKey(f"{target}.id", ondelete=ondelete, name=fk_name),
        nullable=nullable,
    )


def _fk_name(column: str, target: str) -> str:
    table_guess = column.replace("_id", "")
    # Use the calling table prefix if obvious; otherwise the target-table prefix.
    return f"fk__{table_guess}__{column}__{target}"


def timestamps_columns() -> list[sa.Column]:
    return [
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    ]


def soft_delete_column() -> sa.Column:
    return sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True)
