"""entity_id_map — (source, source_id) ↔ canonical_id mapping per project.

Per docs/01-architecture.md §4. The reconciler / backfill / upserter all
need a stable canonical id for every (entity_kind, source_id) pair so that
re-fetched rows update the same canonical row. This table is the registry.

Reverse lookup (canonical_id → list of source_ids) is the basis of the
cross-source unification UI ("this customer is Shopify cust 1 + Excel
contact 42").

Revision ID: 0016_entity_id_map
Revises: 0015_tenant_data_applications
Create Date: 2026-05-07
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0016_entity_id_map"
down_revision: str | None = "0015_tenant_data_applications"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "entity_id_map",
        sa.Column(
            "id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True,
        ),
        sa.Column(
            "organization_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "organizations.id", ondelete="CASCADE",
                name="fk__entity_id_map__organization_id__organizations",
            ),
            nullable=False,
        ),
        sa.Column(
            "project_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "projects.id", ondelete="CASCADE",
                name="fk__entity_id_map__project_id__projects",
            ),
            nullable=False,
        ),
        sa.Column("entity_kind", sa.String(64), nullable=False),
        sa.Column("source", sa.String(60), nullable=False),
        sa.Column("source_id", sa.String(255), nullable=False),
        sa.Column(
            "canonical_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "project_id", "entity_kind", "source", "source_id",
            name="uq__entity_id_map__project_id__entity_kind__source__source_id",
        ),
    )
    # Reverse lookup: given a canonical_id, find all source mappings.
    op.create_index(
        "ix__entity_id_map__project_kind_canonical",
        "entity_id_map",
        ["project_id", "entity_kind", "canonical_id"],
    )

    # RLS — direct organization_id scope.
    op.execute("ALTER TABLE entity_id_map ENABLE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON entity_id_map
        USING (organization_id = current_setting('app.organization_id', true)::uuid)
        WITH CHECK (organization_id = current_setting('app.organization_id', true)::uuid);
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON entity_id_map")
    op.execute("ALTER TABLE entity_id_map DISABLE ROW LEVEL SECURITY")
    op.drop_index(
        "ix__entity_id_map__project_kind_canonical", table_name="entity_id_map",
    )
    op.drop_table("entity_id_map")
