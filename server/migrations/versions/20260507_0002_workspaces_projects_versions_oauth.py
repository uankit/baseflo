"""workspaces, projects, project_versions, oauth_identities

Revision ID: 0002_workspaces_projects_versions
Revises: 0001_init
Create Date: 2026-05-07
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_workspaces_projects_versions"
down_revision: str | None = "0001_init"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ---------- oauth_identities ----------
    op.create_table(
        "oauth_identities",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE", name="fk__oauth_identities__user_id__users"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("subject", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("provider", "subject", name="uq__oauth_identities__provider__subject"),
        sa.CheckConstraint(
            "provider IN ('google', 'github', 'microsoft')",
            name="ck__oauth_identities__provider_enum",
        ),
    )
    op.execute(
        "CREATE TRIGGER set_updated_at BEFORE UPDATE ON oauth_identities "
        "FOR EACH ROW EXECUTE FUNCTION baseflo_set_updated_at();"
    )

    # ---------- workspaces ----------
    op.create_table(
        "workspaces",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "organizations.id", ondelete="CASCADE",
                name="fk__workspaces__organization_id__organizations",
            ),
            nullable=False,
        ),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("slug", sa.String(80), nullable=False),
        sa.Column(
            "created_by",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "users.id", ondelete="RESTRICT", name="fk__workspaces__created_by__users"
            ),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint(
            "organization_id", "slug",
            name="uq__workspaces__organization_id__slug",
        ),
    )
    op.execute(
        "CREATE TRIGGER set_updated_at BEFORE UPDATE ON workspaces "
        "FOR EACH ROW EXECUTE FUNCTION baseflo_set_updated_at();"
    )

    # ---------- projects ----------
    op.create_table(
        "projects",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "organizations.id", ondelete="CASCADE",
                name="fk__projects__organization_id__organizations",
            ),
            nullable=False,
        ),
        sa.Column(
            "workspace_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "workspaces.id", ondelete="CASCADE",
                name="fk__projects__workspace_id__workspaces",
            ),
            nullable=False,
        ),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("slug", sa.String(80), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("current_version_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("deployment_mode", sa.String(20), nullable=False, server_default="hosted"),
        sa.Column("tenant_data_dsn_encrypted", sa.LargeBinary, nullable=True),
        sa.Column("tenant_data_schema_name", sa.String(120), nullable=True),
        sa.Column(
            "created_by",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT", name="fk__projects__created_by__users"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint(
            "organization_id", "workspace_id", "slug",
            name="uq__projects__organization_id__workspace_id__slug",
        ),
        sa.CheckConstraint(
            "deployment_mode IN ('hosted', 'byo_db', 'self_host', 'local_dev')",
            name="ck__projects__deployment_mode_enum",
        ),
    )
    op.execute(
        "CREATE TRIGGER set_updated_at BEFORE UPDATE ON projects "
        "FOR EACH ROW EXECUTE FUNCTION baseflo_set_updated_at();"
    )

    # ---------- project_versions ----------
    op.create_table(
        "project_versions",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "project_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "projects.id", ondelete="CASCADE",
                name="fk__project_versions__project_id__projects",
            ),
            nullable=False,
        ),
        sa.Column(
            "parent_version_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "project_versions.id", ondelete="SET NULL",
                name="fk__project_versions__parent_version_id__project_versions",
            ),
            nullable=True,
        ),
        sa.Column("version_number", sa.Integer, nullable=False),
        sa.Column("schema_ir", sa.dialects.postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("kpi_definitions", sa.dialects.postgresql.JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("dashboard_spec", sa.dialects.postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("intelligence_taxonomy", sa.dialects.postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("assumptions", sa.dialects.postgresql.JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("validation_status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("validation_report", sa.dialects.postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column(
            "created_by",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL", name="fk__project_versions__created_by__users"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint(
            "project_id", "version_number",
            name="uq__project_versions__project_id__version_number",
        ),
        sa.CheckConstraint(
            "validation_status IN ('passed', 'warning', 'failed', 'pending')",
            name="ck__project_versions__validation_status_enum",
        ),
    )

    # ---------- projects.current_version_id FK to project_versions ----------
    # Added now (post-create) to avoid a chicken-and-egg cycle.
    op.create_foreign_key(
        "fk__projects__current_version_id__project_versions",
        source_table="projects",
        referent_table="project_versions",
        local_cols=["current_version_id"],
        remote_cols=["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk__projects__current_version_id__project_versions",
        "projects",
        type_="foreignkey",
    )
    op.drop_table("project_versions")

    op.execute("DROP TRIGGER IF EXISTS set_updated_at ON projects")
    op.drop_table("projects")

    op.execute("DROP TRIGGER IF EXISTS set_updated_at ON workspaces")
    op.drop_table("workspaces")

    op.execute("DROP TRIGGER IF EXISTS set_updated_at ON oauth_identities")
    op.drop_table("oauth_identities")
