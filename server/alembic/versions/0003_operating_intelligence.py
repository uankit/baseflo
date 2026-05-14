"""Operating intelligence foundation.

Revision ID: 0003_operating_intelligence
Revises: 0002_connections_and_sources
Create Date: 2026-05-12
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0003_operating_intelligence"
down_revision = "0002_connections_and_sources"
branch_labels = None
depends_on = None


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    ]


def upgrade() -> None:
    op.create_table(
        "operating_assets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "data_source_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("data_sources.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("qualified_name", sa.String(255), nullable=False),
        sa.Column("source_name", sa.String(200), nullable=False),
        sa.Column("table_label", sa.String(200), nullable=False),
        sa.Column("row_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("column_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("status", sa.String(40), nullable=False, server_default="active"),
        sa.Column(
            "profile",
            postgresql.JSONB,
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("last_profiled_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.UniqueConstraint(
            "organization_id",
            "qualified_name",
            name="uq_operating_asset_org_qname",
        ),
    )
    op.create_index("ix_operating_assets_org", "operating_assets", ["organization_id"])
    op.create_index("ix_operating_assets_source", "operating_assets", ["data_source_id"])

    op.create_table(
        "operating_columns",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "asset_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("operating_assets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("observed_type", sa.String(40), nullable=False),
        sa.Column("semantic_type", sa.String(60), nullable=False),
        sa.Column("null_rate", sa.Float, nullable=False, server_default="0"),
        sa.Column("unique_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("confidence", sa.Float, nullable=False, server_default="0"),
        sa.Column(
            "sample_values",
            postgresql.JSONB,
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "profile",
            postgresql.JSONB,
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        *_timestamps(),
        sa.UniqueConstraint("asset_id", "name", name="uq_operating_column_asset_name"),
    )
    op.create_index("ix_operating_columns_org", "operating_columns", ["organization_id"])
    op.create_index("ix_operating_columns_asset", "operating_columns", ["asset_id"])

    op.create_table(
        "operating_relationships",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "left_asset_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("operating_assets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "right_asset_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("operating_assets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("left_column", sa.String(255), nullable=False),
        sa.Column("right_column", sa.String(255), nullable=False),
        sa.Column("relationship_kind", sa.String(40), nullable=False),
        sa.Column("status", sa.String(40), nullable=False, server_default="candidate"),
        sa.Column("confidence", sa.Float, nullable=False, server_default="0"),
        sa.Column(
            "evidence",
            postgresql.JSONB,
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        *_timestamps(),
    )
    op.create_index(
        "ix_operating_relationships_org",
        "operating_relationships",
        ["organization_id"],
    )
    op.create_index(
        "ix_operating_relationships_left",
        "operating_relationships",
        ["left_asset_id"],
    )
    op.create_index(
        "ix_operating_relationships_right",
        "operating_relationships",
        ["right_asset_id"],
    )

    op.create_table(
        "metric_definitions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "asset_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("operating_assets.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("key", sa.String(255), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("metric_type", sa.String(50), nullable=False),
        sa.Column("expression_sql", sa.Text, nullable=False),
        sa.Column("grain", sa.String(80), nullable=True),
        sa.Column("status", sa.String(40), nullable=False, server_default="candidate"),
        sa.Column("confidence", sa.Float, nullable=False, server_default="0"),
        sa.Column(
            "definition",
            postgresql.JSONB,
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("created_by", sa.String(80), nullable=False, server_default="system"),
        *_timestamps(),
        sa.UniqueConstraint("organization_id", "key", name="uq_metric_definition_org_key"),
    )
    op.create_index(
        "ix_metric_definitions_org", "metric_definitions", ["organization_id"]
    )
    op.create_index("ix_metric_definitions_asset", "metric_definitions", ["asset_id"])

    op.create_table(
        "metric_values",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "metric_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("metric_definitions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("value", sa.Float, nullable=True),
        sa.Column("value_text", sa.String(255), nullable=True),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "evidence",
            postgresql.JSONB,
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.create_index(
        "ix_metric_values_org_computed",
        "metric_values",
        ["organization_id", "computed_at"],
    )
    op.create_index(
        "ix_metric_values_metric_computed",
        "metric_values",
        ["metric_id", "computed_at"],
    )

    op.create_table(
        "insights",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("kind", sa.String(60), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("summary", sa.Text, nullable=False),
        sa.Column("severity", sa.String(40), nullable=False, server_default="info"),
        sa.Column("status", sa.String(40), nullable=False, server_default="open"),
        sa.Column("confidence", sa.Float, nullable=False, server_default="0"),
        sa.Column("impact_score", sa.Float, nullable=False, server_default="0"),
        sa.Column(
            "evidence",
            postgresql.JSONB,
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "source",
            postgresql.JSONB,
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("dismissed_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
    )
    op.create_index(
        "ix_insights_org_status", "insights", ["organization_id", "status", "detected_at"]
    )
    op.create_index(
        "ix_insights_org_kind", "insights", ["organization_id", "kind", "detected_at"]
    )

    op.create_table(
        "business_memories",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("key", sa.String(255), nullable=False),
        sa.Column("value", sa.Text, nullable=False),
        sa.Column("source", sa.String(80), nullable=False, server_default="user"),
        sa.Column("status", sa.String(40), nullable=False, server_default="active"),
        sa.Column("confidence", sa.Float, nullable=False, server_default="1"),
        sa.Column("last_confirmed_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.UniqueConstraint("organization_id", "key", name="uq_business_memory_org_key"),
    )
    op.create_index(
        "ix_business_memories_org", "business_memories", ["organization_id"]
    )

    op.create_table(
        "action_proposals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "insight_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("insights.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("kind", sa.String(80), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("summary", sa.Text, nullable=False),
        sa.Column("status", sa.String(40), nullable=False, server_default="proposed"),
        sa.Column(
            "proposed_payload",
            postgresql.JSONB,
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "approval_scope",
            postgresql.JSONB,
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("idempotency_key", sa.String(255), nullable=False),
        sa.Column("created_by_agent", sa.String(80), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.UniqueConstraint("organization_id", "idempotency_key", name="uq_action_org_key"),
    )
    op.create_index(
        "ix_action_proposals_org_status",
        "action_proposals",
        ["organization_id", "status"],
    )

    op.create_table(
        "audit_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("actor_type", sa.String(40), nullable=False),
        sa.Column("action", sa.String(120), nullable=False),
        sa.Column("target_type", sa.String(80), nullable=False),
        sa.Column("target_id", sa.String(120), nullable=True),
        sa.Column(
            "metadata",
            postgresql.JSONB,
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_audit_events_org_time", "audit_events", ["organization_id", "occurred_at"]
    )
    op.create_index(
        "ix_audit_events_org_action",
        "audit_events",
        ["organization_id", "action", "occurred_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_audit_events_org_action", table_name="audit_events")
    op.drop_index("ix_audit_events_org_time", table_name="audit_events")
    op.drop_table("audit_events")

    op.drop_index("ix_action_proposals_org_status", table_name="action_proposals")
    op.drop_table("action_proposals")

    op.drop_index("ix_business_memories_org", table_name="business_memories")
    op.drop_table("business_memories")

    op.drop_index("ix_insights_org_kind", table_name="insights")
    op.drop_index("ix_insights_org_status", table_name="insights")
    op.drop_table("insights")

    op.drop_index("ix_metric_values_metric_computed", table_name="metric_values")
    op.drop_index("ix_metric_values_org_computed", table_name="metric_values")
    op.drop_table("metric_values")

    op.drop_index("ix_metric_definitions_asset", table_name="metric_definitions")
    op.drop_index("ix_metric_definitions_org", table_name="metric_definitions")
    op.drop_table("metric_definitions")

    op.drop_index("ix_operating_relationships_right", table_name="operating_relationships")
    op.drop_index("ix_operating_relationships_left", table_name="operating_relationships")
    op.drop_index("ix_operating_relationships_org", table_name="operating_relationships")
    op.drop_table("operating_relationships")

    op.drop_index("ix_operating_columns_asset", table_name="operating_columns")
    op.drop_index("ix_operating_columns_org", table_name="operating_columns")
    op.drop_table("operating_columns")

    op.drop_index("ix_operating_assets_source", table_name="operating_assets")
    op.drop_index("ix_operating_assets_org", table_name="operating_assets")
    op.drop_table("operating_assets")
