"""audit_events, digest_subscriptions, api_keys, billing_subscriptions

Revision ID: 0007_audit_digests_apikeys_billing
Revises: 0006_refinements_exports_shares_feedback
Create Date: 2026-05-07
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007_audit_digests_apikeys_billing"
down_revision: str | None = "0006_refinements_exports_shares_feedback"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ----- audit_events -----
    op.create_table(
        "audit_events",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE", name="fk__audit_events__organization_id__organizations"),
            nullable=False,
        ),
        sa.Column("actor_type", sa.String(20), nullable=False),
        sa.Column("actor_id", sa.String(255), nullable=False),
        sa.Column("action", sa.String(60), nullable=False),
        sa.Column("target_kind", sa.String(80), nullable=False),
        sa.Column("target_id", sa.String(255), nullable=False),
        sa.Column("extra", sa.dialects.postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "actor_type IN ('user', 'agent', 'system', 'api_key')",
            name="ck__audit_events__actor_type_enum",
        ),
    )
    op.create_index(
        "ix__audit_events__organization_id__created_at",
        "audit_events",
        ["organization_id", sa.text("created_at DESC")],
    )
    op.create_index(
        "ix__audit_events__pii_reveal",
        "audit_events",
        ["organization_id", "created_at"],
        postgresql_where=sa.text("action = 'pii.reveal'"),
    )

    # ----- digest_subscriptions -----
    op.create_table(
        "digest_subscriptions",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE", name="fk__digest_subscriptions__organization_id__organizations"),
            nullable=False,
        ),
        sa.Column(
            "project_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE", name="fk__digest_subscriptions__project_id__projects"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE", name="fk__digest_subscriptions__user_id__users"),
            nullable=False,
        ),
        sa.Column("cadence", sa.String(10), nullable=False, server_default="daily"),
        sa.Column("delivery_time_local", sa.Time(), nullable=False),
        sa.Column("timezone", sa.String(80), nullable=False, server_default="UTC"),
        sa.Column("channels", sa.dialects.postgresql.ARRAY(sa.String), nullable=False, server_default=sa.text("ARRAY[]::varchar[]")),
        sa.Column("last_sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "cadence IN ('daily', 'weekly', 'off')",
            name="ck__digest_subscriptions__cadence_enum",
        ),
    )
    op.execute(
        "CREATE TRIGGER set_updated_at BEFORE UPDATE ON digest_subscriptions "
        "FOR EACH ROW EXECUTE FUNCTION baseflo_set_updated_at();"
    )

    # ----- api_keys -----
    op.create_table(
        "api_keys",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE", name="fk__api_keys__organization_id__organizations"),
            nullable=False,
        ),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("prefix", sa.String(16), nullable=False),
        sa.Column("hash", sa.String(255), nullable=False),
        sa.Column("scopes", sa.dialects.postgresql.ARRAY(sa.String), nullable=False, server_default=sa.text("ARRAY[]::varchar[]")),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_by",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT", name="fk__api_keys__created_by__users"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # ----- billing_subscriptions -----
    op.create_table(
        "billing_subscriptions",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE", name="fk__billing_subscriptions__organization_id__organizations"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(20), nullable=False, server_default="stripe"),
        sa.Column("external_subscription_id", sa.String(255), nullable=False),
        sa.Column("plan", sa.String(20), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "provider IN ('stripe')",
            name="ck__billing_subscriptions__provider_enum",
        ),
    )
    op.execute(
        "CREATE TRIGGER set_updated_at BEFORE UPDATE ON billing_subscriptions "
        "FOR EACH ROW EXECUTE FUNCTION baseflo_set_updated_at();"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS set_updated_at ON billing_subscriptions")
    op.drop_table("billing_subscriptions")
    op.drop_table("api_keys")
    op.execute("DROP TRIGGER IF EXISTS set_updated_at ON digest_subscriptions")
    op.drop_table("digest_subscriptions")
    op.drop_index("ix__audit_events__pii_reveal", table_name="audit_events")
    op.drop_index("ix__audit_events__organization_id__created_at", table_name="audit_events")
    op.drop_table("audit_events")
