"""refinements, exports, share_links, feedback_events

Revision ID: 0006_refinements_exports_shares_feedback
Revises: 0005_generation
Create Date: 2026-05-07
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006_refinements_exports_shares_feedback"
down_revision: str | None = "0005_generation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ----- refinements -----
    op.create_table(
        "refinements",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "project_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "projects.id", ondelete="CASCADE",
                name="fk__refinements__project_id__projects",
            ),
            nullable=False,
        ),
        sa.Column(
            "parent_version_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "project_versions.id", ondelete="RESTRICT",
                name="fk__refinements__parent_version_id__project_versions",
            ),
            nullable=False,
        ),
        sa.Column(
            "child_version_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "project_versions.id", ondelete="SET NULL",
                name="fk__refinements__child_version_id__project_versions",
            ),
            nullable=True,
        ),
        sa.Column("intent_text", sa.Text, nullable=False),
        sa.Column("interpreted_intent", sa.dialects.postgresql.JSONB, nullable=True),
        sa.Column("change_plan", sa.dialects.postgresql.JSONB, nullable=True),
        sa.Column("impact_summary", sa.dialects.postgresql.JSONB, nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="proposed"),
        sa.Column(
            "created_by",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT", name="fk__refinements__created_by__users"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "status IN ('proposed', 'applied', 'discarded', 'failed')",
            name="ck__refinements__status_enum",
        ),
    )
    op.execute(
        "CREATE TRIGGER set_updated_at BEFORE UPDATE ON refinements "
        "FOR EACH ROW EXECUTE FUNCTION baseflo_set_updated_at();"
    )

    # ----- exports -----
    op.create_table(
        "exports",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE", name="fk__exports__organization_id__organizations"),
            nullable=False,
        ),
        sa.Column(
            "project_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE", name="fk__exports__project_id__projects"),
            nullable=False,
        ),
        sa.Column(
            "project_version_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("project_versions.id", ondelete="RESTRICT", name="fk__exports__project_version_id__project_versions"),
            nullable=False,
        ),
        sa.Column("format", sa.String(10), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="queued"),
        sa.Column("file_url_signed", sa.Text, nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "requested_by",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT", name="fk__exports__requested_by__users"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "format IN ('csv', 'sql', 'json', 'full')",
            name="ck__exports__format_enum",
        ),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'ready', 'expired', 'failed')",
            name="ck__exports__status_enum",
        ),
    )

    # ----- share_links -----
    op.create_table(
        "share_links",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE", name="fk__share_links__organization_id__organizations"),
            nullable=False,
        ),
        sa.Column(
            "project_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE", name="fk__share_links__project_id__projects"),
            nullable=False,
        ),
        sa.Column(
            "project_version_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("project_versions.id", ondelete="RESTRICT", name="fk__share_links__project_version_id__project_versions"),
            nullable=False,
        ),
        sa.Column("token", sa.String(64), nullable=False),
        sa.Column("permissions", sa.dialects.postgresql.ARRAY(sa.String), nullable=False, server_default=sa.text("ARRAY[]::varchar[]")),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_by",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT", name="fk__share_links__created_by__users"),
            nullable=False,
        ),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("token", name="uq__share_links__token"),
    )

    # ----- feedback_events -----
    op.create_table(
        "feedback_events",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE", name="fk__feedback_events__organization_id__organizations"),
            nullable=False,
        ),
        sa.Column(
            "project_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE", name="fk__feedback_events__project_id__projects"),
            nullable=False,
        ),
        sa.Column(
            "project_version_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("project_versions.id", ondelete="RESTRICT", name="fk__feedback_events__project_version_id__project_versions"),
            nullable=False,
        ),
        sa.Column("target_type", sa.String(40), nullable=False),
        sa.Column("target_id", sa.String(120), nullable=False),
        sa.Column("correction", sa.dialects.postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("note", sa.Text, nullable=True),
        sa.Column(
            "created_by",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT", name="fk__feedback_events__created_by__users"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "target_type IN ('entity_reconciliation', 'column_classification', 'kpi_selection', 'cardinality', 'general')",
            name="ck__feedback_events__target_type_enum",
        ),
    )


def downgrade() -> None:
    op.drop_table("feedback_events")
    op.drop_table("share_links")
    op.drop_table("exports")
    op.execute("DROP TRIGGER IF EXISTS set_updated_at ON refinements")
    op.drop_table("refinements")
