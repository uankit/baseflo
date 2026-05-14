"""Connections and data sources.

Revision ID: 0002_connections_and_sources
Revises: 0001_auth_initial
Create Date: 2026-05-11
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0002_connections_and_sources"
down_revision = "0001_auth_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    connection_status = sa.Enum(
        "active", "error", "disconnected", name="connection_status",
    )
    data_source_status = sa.Enum(
        "active", "error", "disconnected", name="data_source_status",
    )
    connection_status.create(bind, checkfirst=False)
    data_source_status.create(bind, checkfirst=False)

    op.create_table(
        "connections",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("kind", sa.String(50), nullable=False),
        sa.Column("external_account_id", sa.String(255), nullable=False),
        sa.Column("external_account_label", sa.String(255), nullable=False),
        sa.Column(
            "credentials",
            postgresql.JSONB,
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "status",
            postgresql.ENUM(name="connection_status", create_type=False),
            nullable=False,
            server_default="active",
        ),
        sa.Column("last_error", sa.Text, nullable=True),
        sa.Column(
            "created_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
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
        sa.UniqueConstraint(
            "organization_id", "kind", "external_account_id",
            name="uq_connection_org_kind_account",
        ),
    )
    op.create_index(
        "ix_connections_org_kind", "connections", ["organization_id", "kind"],
    )

    op.create_table(
        "data_sources",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "connection_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("connections.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("kind", sa.String(50), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column(
            "config",
            postgresql.JSONB,
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("discovered_schema", postgresql.JSONB, nullable=True),
        sa.Column(
            "status",
            postgresql.ENUM(name="data_source_status", create_type=False),
            nullable=False,
            server_default="active",
        ),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text, nullable=True),
        sa.Column(
            "created_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
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
    )
    op.create_index("ix_data_sources_org", "data_sources", ["organization_id"])
    op.create_index(
        "ix_data_sources_connection", "data_sources", ["connection_id"],
    )


def downgrade() -> None:
    bind = op.get_bind()
    op.drop_index("ix_data_sources_connection", table_name="data_sources")
    op.drop_index("ix_data_sources_org", table_name="data_sources")
    op.drop_table("data_sources")
    op.drop_index("ix_connections_org_kind", table_name="connections")
    op.drop_table("connections")
    sa.Enum(name="data_source_status").drop(bind, checkfirst=False)
    sa.Enum(name="connection_status").drop(bind, checkfirst=False)
