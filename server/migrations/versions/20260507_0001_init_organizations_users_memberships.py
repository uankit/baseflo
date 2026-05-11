"""init_organizations_users_memberships

Creates the foundational identity tables: `organizations`, `users`,
`memberships`, `sessions`, plus required Postgres extensions.

Revision ID: 0001_init
Revises:
Create Date: 2026-05-07
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_init"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ---------- Extensions ----------
    op.execute('CREATE EXTENSION IF NOT EXISTS "citext"')
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto"')

    # ---------- Shared trigger function for updated_at ----------
    op.execute(
        """
        CREATE OR REPLACE FUNCTION baseflo_set_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = now();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )

    # ---------- organizations ----------
    op.create_table(
        "organizations",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("slug", sa.String(80), nullable=False),
        sa.Column("plan", sa.String(20), nullable=False, server_default="hobby"),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("kms_key_arn", sa.String(500), nullable=True),
        sa.Column("region", sa.String(20), nullable=False, server_default="us-east-1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("slug", name="uq__organizations__slug"),
        sa.CheckConstraint(
            "plan IN ('hobby', 'pro', 'business', 'enterprise')",
            name="ck__organizations__plan_enum",
        ),
        sa.CheckConstraint(
            "status IN ('active', 'paused', 'cancelled')",
            name="ck__organizations__status_enum",
        ),
    )
    op.execute(
        """
        CREATE TRIGGER set_updated_at BEFORE UPDATE ON organizations
        FOR EACH ROW EXECUTE FUNCTION baseflo_set_updated_at();
        """
    )
    op.create_index(
        "ix__organizations__status_created_at",
        "organizations",
        ["status", "created_at"],
    )

    # ---------- users ----------
    op.create_table(
        "users",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.dialects.postgresql.CITEXT(), nullable=False),
        sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("display_name", sa.String(200), nullable=True),
        sa.Column("password_hash", sa.String(500), nullable=True),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("email", name="uq__users__email"),
    )
    op.execute(
        """
        CREATE TRIGGER set_updated_at BEFORE UPDATE ON users
        FOR EACH ROW EXECUTE FUNCTION baseflo_set_updated_at();
        """
    )

    # ---------- memberships ----------
    op.create_table(
        "memberships",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE", name="fk__memberships__organization_id__organizations"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE", name="fk__memberships__user_id__users"),
            nullable=False,
        ),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column(
            "invited_by",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL", name="fk__memberships__invited_by__users"),
            nullable=True,
        ),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint(
            "organization_id", "user_id", name="uq__memberships__organization_id__user_id"
        ),
        sa.CheckConstraint(
            "role IN ('owner', 'admin', 'editor', 'viewer')",
            name="ck__memberships__role_enum",
        ),
    )
    op.execute(
        """
        CREATE TRIGGER set_updated_at BEFORE UPDATE ON memberships
        FOR EACH ROW EXECUTE FUNCTION baseflo_set_updated_at();
        """
    )
    op.create_index(
        "ix__memberships__user_id",
        "memberships",
        ["user_id"],
    )

    # ---------- sessions ----------
    op.create_table(
        "sessions",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE", name="fk__sessions__user_id__users"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("user_agent", sa.String(500), nullable=True),
        sa.Column("ip_address", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "ix__sessions__user_id_expires_at",
        "sessions",
        ["user_id", "expires_at"],
    )


def downgrade() -> None:
    op.drop_index("ix__sessions__user_id_expires_at", table_name="sessions")
    op.drop_table("sessions")

    op.execute("DROP TRIGGER IF EXISTS set_updated_at ON memberships")
    op.drop_index("ix__memberships__user_id", table_name="memberships")
    op.drop_table("memberships")

    op.execute("DROP TRIGGER IF EXISTS set_updated_at ON users")
    op.drop_table("users")

    op.execute("DROP TRIGGER IF EXISTS set_updated_at ON organizations")
    op.drop_index("ix__organizations__status_created_at", table_name="organizations")
    op.drop_table("organizations")

    op.execute("DROP FUNCTION IF EXISTS baseflo_set_updated_at()")
    # Keep extensions; they're harmless and other DBs in the cluster may use them.
