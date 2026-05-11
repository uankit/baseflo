"""share token scoped RLS lookup

Revision ID: 0023_share_token_rls
Revises: 0022_real_cancel_web
Create Date: 2026-05-07 00:23:00.000000
"""

from __future__ import annotations

from alembic import op

revision = "0023_share_token_rls"
down_revision = "0022_real_cancel_web"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DROP POLICY IF EXISTS share_link_lookup_by_token ON share_links")
    op.execute(
        """
        CREATE POLICY share_link_lookup_by_token ON share_links
        FOR SELECT
        USING (
            token = current_setting('app.share_token', true)
        );
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS share_link_lookup_by_token ON share_links")
