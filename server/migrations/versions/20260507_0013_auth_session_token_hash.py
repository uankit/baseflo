"""Add `token_hash` column to `sessions` (Lucia-style sign-in tokens).

Per docs/40-features/AUTH.md §3.3. Cookie value is the raw 256-bit URL-safe
token; the DB stores `sha256(raw)` and looks up by that. The `id` UUID stays
as the row PK so audit logs and admin tooling can reference sessions by id
without leaking raw tokens.

The migration deletes any existing `sessions` rows. M0 has no real users, so
this is acceptable; the column is added NOT NULL afterward, which would
otherwise fail on a non-empty table.

Revision ID: 0013_auth_session_token_hash
Revises: 0012_auth_magic_link_tokens
Create Date: 2026-05-07
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0013_auth_session_token_hash"
down_revision: str | None = "0012_auth_magic_link_tokens"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # M0 reset — sessions issued before this migration carried no `token_hash`
    # and cannot be re-bound to a raw token.
    op.execute("DELETE FROM sessions")
    op.add_column(
        "sessions",
        sa.Column("token_hash", sa.LargeBinary(), nullable=False),
    )
    op.create_unique_constraint(
        "uq__sessions__token_hash", "sessions", ["token_hash"],
    )


def downgrade() -> None:
    op.drop_constraint("uq__sessions__token_hash", "sessions", type_="unique")
    op.drop_column("sessions", "token_hash")
