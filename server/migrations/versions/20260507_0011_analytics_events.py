"""analytics_events — typed behavioral event log per project.

Per docs/40-features/ANALYTICS.md §4 (event ingestion). Every event the SDK
or webhook posts lands here after the taxonomy validates it. Hot-path query
shapes:
  - "events for project P in window W" — for the digest composer
  - "count of event_name=X for project P in window W" — for KPI widgets
  - "recent events for distinct_id=Y" — for the customer-detail admin view

Indexed accordingly. RLS enforces tenant isolation; idempotency_key guards
SDK retries.

Revision ID: 0011_analytics_events
Revises: 0010_indexes
Create Date: 2026-05-07
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0011_analytics_events"
down_revision: str | None = "0010_indexes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "analytics_events",
        sa.Column(
            "id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True,
        ),
        sa.Column(
            "organization_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "organizations.id", ondelete="CASCADE",
                name="fk__analytics_events__organization_id__organizations",
            ),
            nullable=False,
        ),
        sa.Column(
            "project_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "projects.id", ondelete="CASCADE",
                name="fk__analytics_events__project_id__projects",
            ),
            nullable=False,
        ),
        sa.Column(
            "project_version_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "project_versions.id", ondelete="SET NULL",
                name="fk__analytics_events__project_version_id__project_versions",
            ),
            nullable=True,
        ),
        sa.Column("event_name", sa.String(120), nullable=False),
        sa.Column("distinct_id", sa.String(255), nullable=False),
        sa.Column("entity_id", sa.String(255), nullable=True),
        sa.Column(
            "properties",
            sa.dialects.postgresql.JSONB,
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("source", sa.String(20), nullable=False, server_default="sdk"),
        sa.Column("idempotency_key", sa.String(120), nullable=True),
        sa.Column(
            "occurred_at", sa.DateTime(timezone=True), nullable=False,
        ),
        sa.Column(
            "ingested_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "source IN ('sdk', 'webhook', 'connector', 'manual')",
            name="ck__analytics_events__source_enum",
        ),
        sa.CheckConstraint(
            r"event_name ~ '^[a-z][a-z0-9_]*$'",
            name="ck__analytics_events__event_name_shape",
        ),
    )

    # Hot-path indexes per docs/40-features/ANALYTICS.md §4.3.
    op.create_index(
        "ix__analytics_events__org_project_occurred",
        "analytics_events",
        ["organization_id", "project_id", "occurred_at"],
        postgresql_using="btree",
    )
    op.create_index(
        "ix__analytics_events__org_project_event_occurred",
        "analytics_events",
        ["organization_id", "project_id", "event_name", "occurred_at"],
    )
    op.create_index(
        "ix__analytics_events__distinct_id",
        "analytics_events",
        ["organization_id", "project_id", "distinct_id"],
    )
    # Idempotency: per (organization_id, project_id, idempotency_key) — safe to
    # re-post the same key, but two different payloads with the same key conflict.
    op.create_index(
        "uq__analytics_events__idempotency",
        "analytics_events",
        ["organization_id", "project_id", "idempotency_key"],
        unique=True,
        postgresql_where=sa.text("idempotency_key IS NOT NULL"),
    )

    # RLS — analytics_events has organization_id, so it's a direct-tenant table.
    op.execute("ALTER TABLE analytics_events ENABLE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON analytics_events
        USING (organization_id = current_setting('app.organization_id', true)::uuid)
        WITH CHECK (organization_id = current_setting('app.organization_id', true)::uuid);
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON analytics_events")
    op.execute("ALTER TABLE analytics_events DISABLE ROW LEVEL SECURITY")
    op.drop_index(
        "uq__analytics_events__idempotency", table_name="analytics_events"
    )
    op.drop_index(
        "ix__analytics_events__distinct_id", table_name="analytics_events"
    )
    op.drop_index(
        "ix__analytics_events__org_project_event_occurred",
        table_name="analytics_events",
    )
    op.drop_index(
        "ix__analytics_events__org_project_occurred", table_name="analytics_events"
    )
    op.drop_table("analytics_events")
