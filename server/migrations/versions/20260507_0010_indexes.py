"""indexes for hot query paths

Per docs/04-database-schema.md §7. Most FK columns are already indexed by their
constraint definitions (Postgres does NOT auto-create FK indexes; we add them
explicitly here). Activity-feed indexes use `created_at DESC` ordering.

Revision ID: 0010_indexes
Revises: 0009_rls_policies
Create Date: 2026-05-07
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0010_indexes"
down_revision: str | None = "0009_rls_policies"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# (index_name, table, columns)
INDEXES: tuple[tuple[str, str, str], ...] = (
    # Foreign-key columns (Postgres doesn't auto-index FKs)
    ("ix__memberships__organization_id", "memberships", "organization_id"),
    ("ix__oauth_identities__user_id", "oauth_identities", "user_id"),
    ("ix__workspaces__organization_id", "workspaces", "organization_id"),
    ("ix__projects__organization_id", "projects", "organization_id"),
    ("ix__projects__workspace_id", "projects", "workspace_id"),
    ("ix__projects__current_version_id", "projects", "current_version_id"),
    ("ix__project_versions__project_id", "project_versions", "project_id"),
    ("ix__project_versions__parent_version_id", "project_versions", "parent_version_id"),
    ("ix__connectors__organization_id", "connectors", "organization_id"),
    ("ix__connectors__project_id", "connectors", "project_id"),
    ("ix__connector_tokens__connector_id", "connector_tokens", "connector_id"),
    ("ix__conversations__organization_id", "conversations", "organization_id"),
    ("ix__conversations__project_id", "conversations", "project_id"),
    ("ix__conversation_messages__conversation_id", "conversation_messages", "conversation_id"),
    ("ix__generation_jobs__project_id", "generation_jobs", "project_id"),
    ("ix__generation_jobs__parent_version_id", "generation_jobs", "parent_version_id"),
    ("ix__generation_jobs__status", "generation_jobs", "status"),
    ("ix__generation_steps__job_id", "generation_steps", "job_id"),
    ("ix__agent_runs__step_id", "agent_runs", "step_id"),
    ("ix__agent_runs__agent_name", "agent_runs", "agent_name"),
    ("ix__agent_run_attempts__agent_run_id", "agent_run_attempts", "agent_run_id"),
    ("ix__refinements__project_id", "refinements", "project_id"),
    ("ix__refinements__parent_version_id", "refinements", "parent_version_id"),
    ("ix__exports__project_id", "exports", "project_id"),
    ("ix__share_links__project_id", "share_links", "project_id"),
    ("ix__feedback_events__project_id", "feedback_events", "project_id"),
    ("ix__digest_subscriptions__user_id", "digest_subscriptions", "user_id"),
    ("ix__digest_subscriptions__project_id", "digest_subscriptions", "project_id"),
    ("ix__api_keys__organization_id", "api_keys", "organization_id"),
    ("ix__api_keys__prefix", "api_keys", "prefix"),
    ("ix__billing_subscriptions__organization_id", "billing_subscriptions", "organization_id"),
)


def upgrade() -> None:
    for name, table, column in INDEXES:
        op.create_index(name, table, [column])


def downgrade() -> None:
    for name, table, _ in reversed(INDEXES):
        op.drop_index(name, table_name=table)
