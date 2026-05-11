"""membership lookup returns the full web-session org contract

Revision ID: 0019_membership_lookup_contract
Revises: 0018_force_rls_for_app_owner
Create Date: 2026-05-09
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0019_membership_lookup_contract"
down_revision: str | None = "0018_force_rls_for_app_owner"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS app_get_user_memberships(UUID)")
    op.execute(
        """
        CREATE FUNCTION app_get_user_memberships(p_user_id UUID)
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
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = public
        AS $$
        BEGIN
            PERFORM set_config('app.lookup_user_id', p_user_id::text, true);
            RETURN QUERY
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
            PERFORM set_config('app.lookup_user_id', '', true);
        END;
        $$;
        """
    )
    op.execute("REVOKE ALL ON FUNCTION app_get_user_memberships(UUID) FROM PUBLIC")
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
    op.execute(
        """
        CREATE FUNCTION app_get_user_memberships(p_user_id UUID)
        RETURNS TABLE(
            membership_id UUID,
            organization_id UUID,
            organization_slug TEXT,
            role TEXT
        )
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = public
        AS $$
        BEGIN
            PERFORM set_config('app.lookup_user_id', p_user_id::text, true);
            RETURN QUERY
                SELECT m.id, m.organization_id, o.slug::text, m.role::text
                FROM memberships m
                JOIN organizations o ON o.id = m.organization_id
                WHERE m.user_id = p_user_id
                  AND m.deleted_at IS NULL
                  AND o.deleted_at IS NULL
                  AND m.accepted_at IS NOT NULL;
            PERFORM set_config('app.lookup_user_id', '', true);
        END;
        $$;
        """
    )
    op.execute("REVOKE ALL ON FUNCTION app_get_user_memberships(UUID) FROM PUBLIC")
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
