"""row-level-security policies for every multi-tenant table

Per docs/04-database-schema.md §5 and docs/40-features/AUTH.md §3.3:
- Every multi-tenant table includes `organization_id`.
- The application sets `app.organization_id` via SET LOCAL at request start.
- RLS policies enforce equality with that session var.
- Cross-tenant queries are impossible by design.

Tables WITHOUT `organization_id` (`users`, `oauth_identities`, `sessions`,
`failed_jobs`, `system_health`) are NOT under RLS — they're either global
(users span orgs via memberships) or operational (system tables).

Per docs/04 §5: every multi-tenant table includes `organization_id`. The list
below enumerates exactly those tables.

Revision ID: 0009_rls_policies
Revises: 0008_system_health_failed_jobs
Create Date: 2026-05-07
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0009_rls_policies"
down_revision: str | None = "0008_system_health_failed_jobs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Tables with organization_id that must be RLS-scoped.
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

# Tables that are tenant-scoped TRANSITIVELY through a parent.
# We enable RLS but rely on application-level tenant scoping plus the parent
# table's RLS to enforce isolation; cross-tenant access requires forging the
# session var, which the application layer prevents.
TRANSITIVE_TENANT_TABLES: tuple[str, ...] = (
    "project_versions",          # parent: projects
    "connector_tokens",          # parent: connectors
    "conversation_messages",     # parent: conversations
    "conversation_events",       # parent: conversations
    "generation_jobs",           # parent: projects
    "generation_steps",          # parent: generation_jobs
    "agent_runs",                # parent: generation_steps
    "agent_run_attempts",        # parent: agent_runs
    "refinements",               # parent: projects
)


def upgrade() -> None:
    # ----- Application role -----
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'baseflo_app') THEN
                CREATE ROLE baseflo_app NOLOGIN;
            END IF;
        END$$;
        """
    )

    # ----- Direct-tenant tables -----
    # `organizations` is handled separately below: its own `id` IS the tenant
    # scope (no `organization_id` column on the org row itself).
    for table in TENANT_TABLES:
        if table == "organizations":
            continue
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(
            f"""
            CREATE POLICY tenant_isolation ON {table}
            USING (organization_id = current_setting('app.organization_id', true)::uuid)
            WITH CHECK (organization_id = current_setting('app.organization_id', true)::uuid);
            """
        )

    op.execute("ALTER TABLE organizations ENABLE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON organizations
        USING (id = current_setting('app.organization_id', true)::uuid)
        WITH CHECK (id = current_setting('app.organization_id', true)::uuid);
        """
    )

    # ----- Transitive-tenant tables: enable RLS, rely on parent join -----
    # For tables without organization_id, enabling RLS without a policy denies
    # all access from non-superuser roles. We add policies that join up to the
    # parent and check there.
    transitive_policies = {
        "project_versions": "EXISTS (SELECT 1 FROM projects p WHERE p.id = project_id "
                            "AND p.organization_id = current_setting('app.organization_id', true)::uuid)",
        "connector_tokens": "EXISTS (SELECT 1 FROM connectors c WHERE c.id = connector_id "
                            "AND c.organization_id = current_setting('app.organization_id', true)::uuid)",
        "conversation_messages": "EXISTS (SELECT 1 FROM conversations cv WHERE cv.id = conversation_id "
                                 "AND cv.organization_id = current_setting('app.organization_id', true)::uuid)",
        "conversation_events": "EXISTS (SELECT 1 FROM conversations cv WHERE cv.id = conversation_id "
                               "AND cv.organization_id = current_setting('app.organization_id', true)::uuid)",
        "generation_jobs": "EXISTS (SELECT 1 FROM projects p WHERE p.id = project_id "
                           "AND p.organization_id = current_setting('app.organization_id', true)::uuid)",
        "generation_steps": "EXISTS (SELECT 1 FROM generation_jobs j JOIN projects p ON p.id = j.project_id "
                            "WHERE j.id = job_id AND p.organization_id = current_setting('app.organization_id', true)::uuid)",
        "agent_runs": "EXISTS (SELECT 1 FROM generation_steps s JOIN generation_jobs j ON j.id = s.job_id "
                      "JOIN projects p ON p.id = j.project_id "
                      "WHERE s.id = step_id AND p.organization_id = current_setting('app.organization_id', true)::uuid)",
        "agent_run_attempts": "EXISTS (SELECT 1 FROM agent_runs r JOIN generation_steps s ON s.id = r.step_id "
                              "JOIN generation_jobs j ON j.id = s.job_id JOIN projects p ON p.id = j.project_id "
                              "WHERE r.id = agent_run_id AND p.organization_id = current_setting('app.organization_id', true)::uuid)",
        "refinements": "EXISTS (SELECT 1 FROM projects p WHERE p.id = project_id "
                       "AND p.organization_id = current_setting('app.organization_id', true)::uuid)",
    }
    for table, predicate in transitive_policies.items():
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(
            f"""
            CREATE POLICY tenant_isolation ON {table}
            USING ({predicate})
            WITH CHECK ({predicate});
            """
        )


def downgrade() -> None:
    for table in TENANT_TABLES + TRANSITIVE_TENANT_TABLES:
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
