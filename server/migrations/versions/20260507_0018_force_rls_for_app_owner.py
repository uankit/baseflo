"""force RLS for application-owned connections

Revision ID: 0018_force_rls_for_app_owner
Revises: 0017_webhook_connector_lookup
Create Date: 2026-05-07
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0018_force_rls_for_app_owner"
down_revision: str | None = "0017_webhook_connector_lookup"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


TENANT_TABLES: tuple[str, ...] = (
    "organizations",
    "memberships",
    "workspaces",
    "projects",
    "connectors",
    "conversations",
    "audit_events",
    "digest_subscriptions",
    "api_keys",
    "billing_subscriptions",
    "exports",
    "share_links",
    "feedback_events",
)

TRANSITIVE_TENANT_TABLES: tuple[str, ...] = (
    "project_versions",
    "connector_tokens",
    "conversation_messages",
    "conversation_events",
    "generation_jobs",
    "generation_steps",
    "agent_runs",
    "agent_run_attempts",
    "refinements",
)


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
    op.execute("DROP POLICY IF EXISTS membership_lookup_by_user ON memberships")
    op.execute(
        """
        CREATE POLICY membership_lookup_by_user ON memberships
        FOR SELECT
        USING (
            user_id = NULLIF(current_setting('app.lookup_user_id', true), '')::uuid
        );
        """
    )
    op.execute("DROP POLICY IF EXISTS organization_lookup_by_user ON organizations")
    op.execute(
        """
        CREATE POLICY organization_lookup_by_user ON organizations
        FOR SELECT
        USING (
            EXISTS (
                SELECT 1
                FROM memberships m
                WHERE m.organization_id = organizations.id
                  AND m.user_id = NULLIF(current_setting('app.lookup_user_id', true), '')::uuid
                  AND m.deleted_at IS NULL
                  AND m.accepted_at IS NOT NULL
            )
        );
        """
    )
    for table in TENANT_TABLES + TRANSITIVE_TENANT_TABLES:
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")


def downgrade() -> None:
    for table in TENANT_TABLES + TRANSITIVE_TENANT_TABLES:
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
    op.execute("DROP POLICY IF EXISTS organization_lookup_by_user ON organizations")
    op.execute("DROP POLICY IF EXISTS membership_lookup_by_user ON memberships")
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
