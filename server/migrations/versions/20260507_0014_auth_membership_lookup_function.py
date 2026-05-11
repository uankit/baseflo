"""SECURITY DEFINER function for auth-time membership discovery.

Per docs/40-features/AUTH.md §3.3 the auth middleware must discover a user's
memberships *before* an active organization (and its RLS scope) has been
picked. Memberships and organizations are RLS-protected, so we expose a
SECURITY DEFINER function that the application role can call to walk the
join safely.

The function:
  - Filters by `user_id` on the input.
  - Joins `organizations` to expose the slug for org-by-slug routing.
  - Excludes soft-deleted rows.
  - Excludes pending invites (`accepted_at IS NULL`).

Revision ID: 0014_auth_membership_lookup_function
Revises: 0013_auth_session_token_hash
Create Date: 2026-05-07
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op


revision: str = "0014_auth_membership_lookup_function"
down_revision: str | None = "0013_auth_session_token_hash"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION app_get_user_memberships(p_user_id UUID)
        RETURNS TABLE(
            membership_id UUID,
            organization_id UUID,
            organization_slug TEXT,
            organization_name TEXT,
            role TEXT,
            plan TEXT,
            region TEXT,
            status TEXT,
            organization_created_at TIMESTAMPTZ
        )
        LANGUAGE sql
        SECURITY DEFINER
        SET search_path = public
        AS $$
            SELECT
                m.id,
                m.organization_id,
                o.slug::text,
                o.name::text,
                m.role::text,
                o.plan::text,
                o.region::text,
                o.status::text,
                o.created_at
            FROM memberships m
            JOIN organizations o ON o.id = m.organization_id
            WHERE m.user_id = p_user_id
              AND m.deleted_at IS NULL
              AND o.deleted_at IS NULL
              AND m.accepted_at IS NOT NULL;
        $$;
        """
    )
    # Lock down: only the application role can call this.
    op.execute(
        "REVOKE ALL ON FUNCTION app_get_user_memberships(UUID) FROM PUBLIC"
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'baseflo_app') THEN
                EXECUTE 'GRANT EXECUTE ON FUNCTION app_get_user_memberships(UUID) TO baseflo_app';
            END IF;
        END$$;
        """
    )


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS app_get_user_memberships(UUID)")
