"""magic_link_tokens — passwordless sign-in tokens.

Per docs/40-features/AUTH.md §3.3. Single-use, short-TTL tokens that the
server emails to the requester. The DB stores `sha256(raw_token)` as
`token_hash`; the raw token is only ever transported via the verification URL.

The table is global (no `organization_id`): a sign-in request for an email
does not belong to an org until after the user authenticates and picks one.

Revision ID: 0012_auth_magic_link_tokens
Revises: 0011_analytics_events
Create Date: 2026-05-07
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0012_auth_magic_link_tokens"
down_revision: str | None = "0011_analytics_events"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "magic_link_tokens",
        sa.Column(
            "id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True,
        ),
        sa.Column("email", sa.dialects.postgresql.CITEXT(), nullable=False),
        sa.Column("token_hash", sa.LargeBinary(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ip_address", sa.String(64), nullable=True),
        sa.Column("user_agent", sa.String(500), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("token_hash", name="uq__magic_link_tokens__token_hash"),
    )
    # Cleanup-friendly index for the nightly purge of old/consumed tokens.
    op.create_index(
        "ix__magic_link_tokens__expires_at",
        "magic_link_tokens",
        ["expires_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix__magic_link_tokens__expires_at", table_name="magic_link_tokens",
    )
    op.drop_table("magic_link_tokens")
