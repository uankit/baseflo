"""workspace build graph persistence.

Revision ID: 0020_workspace_build_graph
Revises: 0019_membership_lookup_contract
Create Date: 2026-05-10
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0020_workspace_build_graph"
down_revision: str | None = "0019_membership_lookup_contract"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "workspace_builds",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "organizations.id",
                ondelete="CASCADE",
                name="fk__workspace_builds__organization_id__organizations",
            ),
            nullable=False,
        ),
        sa.Column(
            "project_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "projects.id",
                ondelete="CASCADE",
                name="fk__workspace_builds__project_id__projects",
            ),
            nullable=False,
        ),
        sa.Column(
            "job_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "generation_jobs.id",
                ondelete="CASCADE",
                name="fk__workspace_builds__job_id__generation_jobs",
            ),
            nullable=False,
        ),
        sa.Column("conversation_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("graph_name", sa.String(120), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("current_node", sa.String(120), nullable=True),
        sa.Column("repair_cycle", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("project_version_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("final_result", sa.dialects.postgresql.JSONB(), nullable=True),
        sa.Column("error", sa.dialects.postgresql.JSONB(), nullable=True),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.CheckConstraint(
            "status IN ('running', 'succeeded', 'failed')",
            name="ck__workspace_builds__status_enum",
        ),
        sa.UniqueConstraint("job_id", name="uq__workspace_builds__job_id"),
    )
    op.create_index(
        "ix__workspace_builds__organization_id_project_id",
        "workspace_builds",
        ["organization_id", "project_id"],
    )

    op.create_table(
        "workspace_build_snapshots",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "build_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "workspace_builds.id",
                ondelete="CASCADE",
                name="fk__workspace_build_snapshots__build_id__workspace_builds",
            ),
            nullable=False,
        ),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("snapshot_id", sa.String(255), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("node_name", sa.String(120), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("payload", sa.dialects.postgresql.JSONB(), nullable=False),
        sa.Column("error", sa.dialects.postgresql.JSONB(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("traceparent", sa.Text(), nullable=True),
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
        sa.CheckConstraint(
            "kind IN ('node', 'end')",
            name="ck__workspace_build_snapshots__kind_enum",
        ),
        sa.CheckConstraint(
            "status IN ('created', 'pending', 'running', 'success', 'error')",
            name="ck__workspace_build_snapshots__status_enum",
        ),
        sa.UniqueConstraint(
            "build_id",
            "snapshot_id",
            name="uq__workspace_build_snapshots__build_id__snapshot_id",
        ),
        sa.UniqueConstraint(
            "build_id",
            "ordinal",
            name="uq__workspace_build_snapshots__build_id__ordinal",
        ),
    )
    op.create_index(
        "ix__workspace_build_snapshots__build_id_status_ordinal",
        "workspace_build_snapshots",
        ["build_id", "status", "ordinal"],
    )

    for table_name in ("workspace_builds", "workspace_build_snapshots"):
        op.execute(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON workspace_builds
        USING (organization_id = current_setting('app.organization_id', true)::uuid)
        WITH CHECK (organization_id = current_setting('app.organization_id', true)::uuid);
        """
    )
    op.execute(
        """
        CREATE POLICY tenant_isolation ON workspace_build_snapshots
        USING (
            EXISTS (
                SELECT 1 FROM workspace_builds
                WHERE workspace_builds.id = workspace_build_snapshots.build_id
                AND workspace_builds.organization_id =
                    current_setting('app.organization_id', true)::uuid
            )
        )
        WITH CHECK (
            EXISTS (
                SELECT 1 FROM workspace_builds
                WHERE workspace_builds.id = workspace_build_snapshots.build_id
                AND workspace_builds.organization_id =
                    current_setting('app.organization_id', true)::uuid
            )
        );
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON workspace_build_snapshots")
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON workspace_builds")
    op.execute("ALTER TABLE workspace_build_snapshots DISABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE workspace_builds DISABLE ROW LEVEL SECURITY")
    op.drop_index(
        "ix__workspace_build_snapshots__build_id_status_ordinal",
        table_name="workspace_build_snapshots",
    )
    op.drop_table("workspace_build_snapshots")
    op.drop_index(
        "ix__workspace_builds__organization_id_project_id",
        table_name="workspace_builds",
    )
    op.drop_table("workspace_builds")
