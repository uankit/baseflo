"""entity identity index for row-level resolution.

Revision ID: 0021_entity_identity_index
Revises: 0020_workspace_build_graph
Create Date: 2026-05-10
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0021_entity_identity_index"
down_revision: str | None = "0020_workspace_build_graph"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "entity_identity_index",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "organizations.id",
                ondelete="CASCADE",
                name="fk__entity_identity_index__organization_id__organizations",
            ),
            nullable=False,
        ),
        sa.Column(
            "project_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "projects.id",
                ondelete="CASCADE",
                name="fk__entity_identity_index__project_id__projects",
            ),
            nullable=False,
        ),
        sa.Column("entity_kind", sa.String(64), nullable=False),
        sa.Column("identity_key", sa.String(180), nullable=False),
        sa.Column("identity_hash", sa.String(64), nullable=False),
        sa.Column("canonical_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("evidence", sa.dialects.postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "project_id",
            "entity_kind",
            "identity_key",
            "identity_hash",
            name="uq__entity_identity_index__project_kind_key_hash",
        ),
    )
    op.create_index(
        "ix__entity_identity_index__project_kind_canonical",
        "entity_identity_index",
        ["project_id", "entity_kind", "canonical_id"],
    )
    op.execute("ALTER TABLE entity_identity_index ENABLE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON entity_identity_index
        USING (organization_id = current_setting('app.organization_id', true)::uuid)
        WITH CHECK (organization_id = current_setting('app.organization_id', true)::uuid);
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON entity_identity_index")
    op.execute("ALTER TABLE entity_identity_index DISABLE ROW LEVEL SECURITY")
    op.drop_index(
        "ix__entity_identity_index__project_kind_canonical",
        table_name="entity_identity_index",
    )
    op.drop_table("entity_identity_index")
