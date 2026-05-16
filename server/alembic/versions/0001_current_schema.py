"""Current Baseflo backend schema.

Revision ID: 0001_current_schema
Revises:
Create Date: 2026-05-16
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0001_current_schema"
down_revision = None
branch_labels = None
depends_on = None


def _timestamps() -> list[sa.Column]:
    return [
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
    ]


def _json_object() -> sa.TextClause:
    return sa.text("'{}'::jsonb")


def _json_array() -> sa.TextClause:
    return sa.text("'[]'::jsonb")


def _enum_ref(name: str) -> postgresql.ENUM:
    return postgresql.ENUM(name=name, create_type=False)


def _create_enums() -> None:
    bind = op.get_bind()
    for enum in (
        sa.Enum("free", "pro", "team", "enterprise", name="org_plan"),
        sa.Enum("active", "suspended", "deleted", name="user_status"),
        sa.Enum("owner", "admin", "member", "viewer", name="member_role"),
        sa.Enum("active", "pending", "revoked", name="membership_status"),
        sa.Enum("sign_in", name="magic_link_purpose"),
        sa.Enum(
            "signup",
            "login",
            "login_failed",
            "logout",
            "magic_link_requested",
            "magic_link_consumed",
            "refresh_token_issued",
            "refresh_token_rotated",
            "refresh_token_revoked",
            "org_created",
            "membership_created",
            "membership_revoked",
            "invitation_sent",
            "invitation_accepted",
            "invitation_revoked",
            name="auth_event_kind",
        ),
        sa.Enum("active", "error", "disconnected", name="connection_status"),
        sa.Enum("active", "error", "disconnected", name="data_source_status"),
    ):
        enum.create(bind, checkfirst=False)


def _drop_enums() -> None:
    bind = op.get_bind()
    for name in (
        "data_source_status",
        "connection_status",
        "auth_event_kind",
        "magic_link_purpose",
        "membership_status",
        "member_role",
        "user_status",
        "org_plan",
    ):
        sa.Enum(name=name).drop(bind, checkfirst=False)


def upgrade() -> None:
    _create_enums()

    op.create_table(
        "organizations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False),
        sa.Column("plan", _enum_ref("org_plan"), nullable=False, server_default="free"),
        *_timestamps(),
        sa.UniqueConstraint("slug", name="uq_organizations_slug"),
    )

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("status", _enum_ref("user_status"), nullable=False, server_default="active"),
        *_timestamps(),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )

    op.create_table(
        "memberships",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", _enum_ref("member_role"), nullable=False),
        sa.Column(
            "status",
            _enum_ref("membership_status"),
            nullable=False,
            server_default="active",
        ),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.UniqueConstraint("user_id", "organization_id", name="uq_membership_user_org"),
    )
    op.create_index("ix_memberships_user", "memberships", ["user_id"])
    op.create_index("ix_memberships_org", "memberships", ["organization_id"])

    op.create_table(
        "invitations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("role", _enum_ref("member_role"), nullable=False),
        sa.Column(
            "invited_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
    )
    op.create_index("ix_invitations_token_hash", "invitations", ["token_hash"])
    op.create_index(
        "ix_invitations_org_email",
        "invitations",
        ["organization_id", "email"],
    )

    op.create_table(
        "magic_link_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column(
            "purpose",
            _enum_ref("magic_link_purpose"),
            nullable=False,
            server_default="sign_in",
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ip_address", sa.String(64), nullable=True),
        sa.Column("user_agent", sa.String(500), nullable=True),
        *_timestamps(),
    )
    op.create_index(
        "ix_magic_link_email_active",
        "magic_link_tokens",
        ["email", "consumed_at", "expires_at"],
    )

    op.create_table(
        "refresh_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "replaced_by_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("refresh_tokens.id"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("token_hash", name="uq_refresh_tokens_token_hash"),
    )

    op.create_table(
        "auth_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id"),
            nullable=True,
        ),
        sa.Column("kind", _enum_ref("auth_event_kind"), nullable=False),
        sa.Column("ip_address", sa.String(64), nullable=True),
        sa.Column("user_agent", sa.String(500), nullable=True),
        sa.Column("details", postgresql.JSONB, nullable=False, server_default=_json_object()),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_auth_events_user", "auth_events", ["user_id", "occurred_at"])
    op.create_index("ix_auth_events_org", "auth_events", ["organization_id", "occurred_at"])
    op.create_index("ix_auth_events_kind", "auth_events", ["kind", "occurred_at"])

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
        sa.Column("credentials", postgresql.JSONB, nullable=False, server_default=_json_object()),
        sa.Column(
            "status",
            _enum_ref("connection_status"),
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
        *_timestamps(),
        sa.UniqueConstraint(
            "organization_id",
            "kind",
            "external_account_id",
            name="uq_connection_org_kind_account",
        ),
    )
    op.create_index("ix_connections_org_kind", "connections", ["organization_id", "kind"])

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
        sa.Column("config", postgresql.JSONB, nullable=False, server_default=_json_object()),
        sa.Column("discovered_schema", postgresql.JSONB, nullable=True),
        sa.Column(
            "status",
            _enum_ref("data_source_status"),
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
        *_timestamps(),
    )
    op.create_index("ix_data_sources_org", "data_sources", ["organization_id"])
    op.create_index("ix_data_sources_connection", "data_sources", ["connection_id"])

    op.create_table(
        "canonical_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "data_source_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("data_sources.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("snapshot_key", sa.String(255), nullable=False),
        sa.Column("mode", sa.String(40), nullable=False, server_default="full_refresh"),
        sa.Column("status", sa.String(40), nullable=False, server_default="running"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("asset_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("row_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("metadata", postgresql.JSONB, nullable=False, server_default=_json_object()),
        *_timestamps(),
        sa.UniqueConstraint(
            "organization_id",
            "snapshot_key",
            name="uq_canonical_snapshot_org_key",
        ),
    )
    op.create_index(
        "ix_canonical_snapshots_org",
        "canonical_snapshots",
        ["organization_id", "started_at"],
    )
    op.create_index(
        "ix_canonical_snapshots_source",
        "canonical_snapshots",
        ["data_source_id", "started_at"],
    )

    op.create_table(
        "canonical_assets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "data_source_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("data_sources.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "snapshot_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("canonical_snapshots.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("asset_key", sa.String(255), nullable=False),
        sa.Column("qualified_name", sa.String(255), nullable=False),
        sa.Column("storage_table", sa.String(255), nullable=False),
        sa.Column("label", sa.String(255), nullable=False),
        sa.Column("asset_type", sa.String(60), nullable=False, server_default="table"),
        sa.Column("status", sa.String(40), nullable=False, server_default="active"),
        sa.Column("row_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("field_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("metadata", postgresql.JSONB, nullable=False, server_default=_json_object()),
        sa.Column("profile", postgresql.JSONB, nullable=False, server_default=_json_object()),
        *_timestamps(),
        sa.UniqueConstraint(
            "organization_id",
            "qualified_name",
            name="uq_canonical_asset_org_qname",
        ),
    )
    op.create_index("ix_canonical_assets_org", "canonical_assets", ["organization_id"])
    op.create_index("ix_canonical_assets_source", "canonical_assets", ["data_source_id"])
    op.create_index("ix_canonical_assets_snapshot", "canonical_assets", ["snapshot_id"])

    op.create_table(
        "canonical_fields",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "asset_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("canonical_assets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("ordinal", sa.Integer, nullable=False),
        sa.Column("storage_type", sa.String(40), nullable=False, server_default="varchar"),
        sa.Column("observed_type", sa.String(40), nullable=False, server_default="unknown"),
        sa.Column("nullable", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("sample_values", postgresql.JSONB, nullable=False, server_default=_json_array()),
        sa.Column("profile", postgresql.JSONB, nullable=False, server_default=_json_object()),
        *_timestamps(),
        sa.UniqueConstraint("asset_id", "name", name="uq_canonical_field_asset_name"),
    )
    op.create_index("ix_canonical_fields_org", "canonical_fields", ["organization_id"])
    op.create_index("ix_canonical_fields_asset", "canonical_fields", ["asset_id"])

    op.create_table(
        "data_graph_edges",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "snapshot_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("canonical_snapshots.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("subject_type", sa.String(80), nullable=False),
        sa.Column("subject_id", sa.String(255), nullable=False),
        sa.Column("predicate", sa.String(120), nullable=False),
        sa.Column("object_type", sa.String(80), nullable=False),
        sa.Column("object_id", sa.String(255), nullable=False),
        sa.Column("status", sa.String(40), nullable=False, server_default="active"),
        sa.Column("confidence", sa.Float, nullable=False, server_default="1"),
        sa.Column("created_by", sa.String(80), nullable=False, server_default="system"),
        sa.Column("evidence", postgresql.JSONB, nullable=False, server_default=_json_object()),
        *_timestamps(),
    )
    op.create_index(
        "ix_data_graph_edges_org_predicate",
        "data_graph_edges",
        ["organization_id", "predicate"],
    )
    op.create_index(
        "ix_data_graph_edges_subject",
        "data_graph_edges",
        ["subject_type", "subject_id"],
    )
    op.create_index(
        "ix_data_graph_edges_object",
        "data_graph_edges",
        ["object_type", "object_id"],
    )
    op.create_index("ix_data_graph_edges_snapshot", "data_graph_edges", ["snapshot_id"])

    op.create_table(
        "business_memories",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("key", sa.String(255), nullable=False),
        sa.Column("value", sa.Text, nullable=False),
        sa.Column("kind", sa.String(80), nullable=False, server_default="note"),
        sa.Column("scope", sa.String(80), nullable=False, server_default="org"),
        sa.Column("subject_ref", postgresql.JSONB, nullable=False, server_default=_json_object()),
        sa.Column("evidence_refs", postgresql.JSONB, nullable=False, server_default=_json_array()),
        sa.Column("metadata", postgresql.JSONB, nullable=False, server_default=_json_object()),
        sa.Column("source", sa.String(80), nullable=False, server_default="user"),
        sa.Column("status", sa.String(40), nullable=False, server_default="active"),
        sa.Column("confidence", sa.Float, nullable=False, server_default="1"),
        sa.Column("last_confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.UniqueConstraint("organization_id", "key", name="uq_business_memory_org_key"),
    )
    op.create_index("ix_business_memories_org", "business_memories", ["organization_id"])
    op.create_index(
        "ix_business_memories_org_kind",
        "business_memories",
        ["organization_id", "kind"],
    )
    op.create_index(
        "ix_business_memories_org_scope",
        "business_memories",
        ["organization_id", "scope"],
    )

    op.create_table(
        "runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("kind", sa.String(40), nullable=False),
        sa.Column("status", sa.String(40), nullable=False, server_default="queued"),
        sa.Column("request", postgresql.JSONB, nullable=False, server_default=_json_object()),
        sa.Column("result", postgresql.JSONB, nullable=True),
        sa.Column("error", postgresql.JSONB, nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
    )
    op.create_index("ix_runs_org_status", "runs", ["organization_id", "status"])
    op.create_index("ix_runs_org_kind_created", "runs", ["organization_id", "kind", "created_at"])

    op.create_table(
        "run_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("type", sa.String(160), nullable=False),
        sa.Column("stage", sa.String(120), nullable=False),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column("progress", sa.Float, nullable=True),
        sa.Column("payload", postgresql.JSONB, nullable=False, server_default=_json_object()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_run_events_run_created", "run_events", ["run_id", "created_at"])
    op.create_index("ix_run_events_org_created", "run_events", ["organization_id", "created_at"])

    op.create_table(
        "agent_cache_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("scope_key", sa.String(120), nullable=False, server_default="global"),
        sa.Column("agent_name", sa.String(120), nullable=False),
        sa.Column("model_name", sa.String(160), nullable=False),
        sa.Column("input_hash", sa.String(64), nullable=False),
        sa.Column("output", postgresql.JSONB, nullable=False, server_default=_json_object()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("hit_count", sa.Integer, nullable=False, server_default="0"),
        sa.UniqueConstraint(
            "scope_key",
            "agent_name",
            "model_name",
            "input_hash",
            name="uq_agent_cache_agent_model_input",
        ),
    )
    op.create_index(
        "ix_agent_cache_scope_agent_last_used",
        "agent_cache_entries",
        ["scope_key", "agent_name", "last_used_at"],
    )

    op.create_table(
        "operating_artifacts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("artifact_key", sa.String(500), nullable=False),
        sa.Column("kind", sa.String(80), nullable=False),
        sa.Column("status", sa.String(40), nullable=False, server_default="new"),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("summary", sa.Text, nullable=False, server_default=""),
        sa.Column("why", sa.Text, nullable=False, server_default=""),
        sa.Column("tags", postgresql.JSONB, nullable=False, server_default=_json_array()),
        sa.Column("priority", sa.Float, nullable=False, server_default="0.5"),
        sa.Column("source_refs", postgresql.JSONB, nullable=False, server_default=_json_object()),
        sa.Column("payload", postgresql.JSONB, nullable=False, server_default=_json_object()),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("snoozed_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("dismissed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.UniqueConstraint("organization_id", "artifact_key", name="uq_operating_artifact_org_key"),
    )
    op.create_index(
        "ix_operating_artifacts_org_kind_status",
        "operating_artifacts",
        ["organization_id", "kind", "status"],
    )
    op.create_index(
        "ix_operating_artifacts_org_last_seen",
        "operating_artifacts",
        ["organization_id", "last_seen_at"],
    )
    op.create_index("ix_operating_artifacts_run", "operating_artifacts", ["run_id"])

    op.create_table(
        "operating_actions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "artifact_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("operating_artifacts.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("action_key", sa.String(500), nullable=False),
        sa.Column("action_type", sa.String(80), nullable=False),
        sa.Column("status", sa.String(40), nullable=False, server_default="proposed"),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("summary", sa.Text, nullable=False, server_default=""),
        sa.Column("why", sa.Text, nullable=False, server_default=""),
        sa.Column("source_refs", postgresql.JSONB, nullable=False, server_default=_json_object()),
        sa.Column("payload", postgresql.JSONB, nullable=False, server_default=_json_object()),
        sa.Column(
            "prepared_payload",
            postgresql.JSONB,
            nullable=False,
            server_default=_json_object(),
        ),
        sa.Column("prepared_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("dismissed_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.UniqueConstraint("organization_id", "action_key", name="uq_operating_action_org_key"),
    )
    op.create_index("ix_operating_actions_org_status", "operating_actions", ["organization_id", "status"])
    op.create_index("ix_operating_actions_org_type", "operating_actions", ["organization_id", "action_type"])
    op.create_index("ix_operating_actions_artifact", "operating_actions", ["artifact_id"])
    op.create_index("ix_operating_actions_run", "operating_actions", ["run_id"])

    op.create_table(
        "saved_cohorts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "action_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("operating_actions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("cohort_key", sa.String(500), nullable=False),
        sa.Column("name", sa.String(500), nullable=False),
        sa.Column("description", sa.Text, nullable=False, server_default=""),
        sa.Column("audience", postgresql.JSONB, nullable=False, server_default=_json_object()),
        sa.Column("rows", postgresql.JSONB, nullable=False, server_default=_json_array()),
        sa.Column("source_refs", postgresql.JSONB, nullable=False, server_default=_json_object()),
        *_timestamps(),
        sa.UniqueConstraint("organization_id", "cohort_key", name="uq_saved_cohort_org_key"),
    )
    op.create_index("ix_saved_cohorts_org", "saved_cohorts", ["organization_id"])
    op.create_index("ix_saved_cohorts_action", "saved_cohorts", ["action_id"])


def downgrade() -> None:
    for table_name in (
        "saved_cohorts",
        "operating_actions",
        "operating_artifacts",
        "agent_cache_entries",
        "run_events",
        "runs",
        "business_memories",
        "data_graph_edges",
        "canonical_fields",
        "canonical_assets",
        "canonical_snapshots",
        "data_sources",
        "connections",
        "auth_events",
        "refresh_tokens",
        "magic_link_tokens",
        "invitations",
        "memberships",
        "users",
        "organizations",
    ):
        op.drop_table(table_name)
    _drop_enums()
