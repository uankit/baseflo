"""connectors, connector_tokens

Revision ID: 0003_connectors_tokens
Revises: 0002_workspaces_projects_versions
Create Date: 2026-05-07
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_connectors_tokens"
down_revision: str | None = "0002_workspaces_projects_versions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "connectors",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "organizations.id", ondelete="CASCADE",
                name="fk__connectors__organization_id__organizations",
            ),
            nullable=False,
        ),
        sa.Column(
            "project_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "projects.id", ondelete="CASCADE",
                name="fk__connectors__project_id__projects",
            ),
            nullable=False,
        ),
        sa.Column("kind", sa.String(60), nullable=False),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="connected"),
        sa.Column("config", sa.dialects.postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.dialects.postgresql.JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('connected', 'error', 'revoked', 'expired')",
            name="ck__connectors__status_enum",
        ),
    )
    op.execute(
        "CREATE TRIGGER set_updated_at BEFORE UPDATE ON connectors "
        "FOR EACH ROW EXECUTE FUNCTION baseflo_set_updated_at();"
    )

    op.create_table(
        "connector_tokens",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "connector_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "connectors.id", ondelete="CASCADE",
                name="fk__connector_tokens__connector_id__connectors",
            ),
            nullable=False,
        ),
        sa.Column("token_type", sa.String(30), nullable=False),
        sa.Column("ciphertext", sa.LargeBinary, nullable=False),
        sa.Column("wrapped_dek", sa.LargeBinary, nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("scopes", sa.dialects.postgresql.ARRAY(sa.String), nullable=False, server_default=sa.text("ARRAY[]::varchar[]")),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "token_type IN ('oauth2', 'api_key', 'db_url', 'service_account')",
            name="ck__connector_tokens__token_type_enum",
        ),
    )


def downgrade() -> None:
    op.drop_table("connector_tokens")
    op.execute("DROP TRIGGER IF EXISTS set_updated_at ON connectors")
    op.drop_table("connectors")
