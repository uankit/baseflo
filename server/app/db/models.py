"""Database models for auth, connectors, and the packaged data/agent planes."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy import (
    Enum as SAEnum,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import (
    AuthEventKind,
    ConnectionStatus,
    DataSourceStatus,
    MagicLinkPurpose,
    MembershipStatus,
    OrgPlan,
    Role,
    UserStatus,
)
from app.db.base import Base, TimestampMixin, UUIDMixin


def _enum_values(enum_cls: type[Any]) -> list[str]:
    """Persist Python Enum `.value` strings, not member names.

    PostgreSQL enum types in the migrations use lowercase values (for example
    `active`). SQLAlchemy's Enum defaults to binding member names (for example
    `ACTIVE`) unless values_callable is supplied.
    """
    return [member.value for member in enum_cls]


def _pg_enum(enum_cls: type[Any], name: str) -> SAEnum:
    return SAEnum(
        enum_cls,
        name=name,
        values_callable=_enum_values,
        validate_strings=True,
    )


class Organization(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    plan: Mapped[OrgPlan] = mapped_column(
        _pg_enum(OrgPlan, "org_plan"),
        nullable=False,
        default=OrgPlan.FREE,
    )

    memberships: Mapped[list[Membership]] = relationship(back_populates="organization")
    invitations: Mapped[list[Invitation]] = relationship(back_populates="organization")


class User(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    status: Mapped[UserStatus] = mapped_column(
        _pg_enum(UserStatus, "user_status"),
        nullable=False,
        default=UserStatus.ACTIVE,
    )

    memberships: Mapped[list[Membership]] = relationship(back_populates="user")
    refresh_tokens: Mapped[list[RefreshToken]] = relationship(back_populates="user")


class Membership(Base, UUIDMixin, TimestampMixin):
    """User ↔ Organization with a role and status. One row per (user, org)."""

    __tablename__ = "memberships"

    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    organization_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[Role] = mapped_column(_pg_enum(Role, "member_role"), nullable=False)
    status: Mapped[MembershipStatus] = mapped_column(
        _pg_enum(MembershipStatus, "membership_status"),
        nullable=False,
        default=MembershipStatus.ACTIVE,
    )
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    user: Mapped[User] = relationship(back_populates="memberships")
    organization: Mapped[Organization] = relationship(back_populates="memberships")

    __table_args__ = (
        UniqueConstraint("user_id", "organization_id", name="uq_membership_user_org"),
        Index("ix_memberships_user", "user_id"),
        Index("ix_memberships_org", "organization_id"),
    )


class Invitation(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "invitations"

    organization_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[Role] = mapped_column(_pg_enum(Role, "member_role"), nullable=False)
    invited_by_user_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    accepted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    organization: Mapped[Organization] = relationship(back_populates="invitations")

    __table_args__ = (
        Index("ix_invitations_token_hash", "token_hash"),
        Index("ix_invitations_org_email", "organization_id", "email"),
    )


class MagicLinkToken(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "magic_link_tokens"

    email: Mapped[str] = mapped_column(String(255), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    purpose: Mapped[MagicLinkPurpose] = mapped_column(
        _pg_enum(MagicLinkPurpose, "magic_link_purpose"),
        nullable=False,
        default=MagicLinkPurpose.SIGN_IN,
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    consumed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)

    __table_args__ = (
        Index("ix_magic_link_email_active", "email", "consumed_at", "expires_at"),
    )


class RefreshToken(Base, UUIDMixin):
    """Opaque, table-backed refresh token. Rotated on each use."""

    __tablename__ = "refresh_tokens"

    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    organization_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    replaced_by_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("refresh_tokens.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    user: Mapped[User] = relationship(back_populates="refresh_tokens")


class AuthEvent(Base, UUIDMixin):
    """Immutable audit log of auth-related actions."""

    __tablename__ = "auth_events"

    user_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    organization_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id"), nullable=True
    )
    kind: Mapped[AuthEventKind] = mapped_column(
        _pg_enum(AuthEventKind, "auth_event_kind"), nullable=False
    )
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    __table_args__ = (
        Index("ix_auth_events_user", "user_id", "occurred_at"),
        Index("ix_auth_events_org", "organization_id", "occurred_at"),
        Index("ix_auth_events_kind", "kind", "occurred_at"),
    )


class Connection(Base, UUIDMixin, TimestampMixin):
    """An authenticated session with an external service (per org, kind, external account).

    One Connection per (org, kind, external_account). Holds the credentials.
    Many DataSources can hang off a single Connection (e.g., multiple sheets
    from one Google account).
    """

    __tablename__ = "connections"

    organization_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    kind: Mapped[str] = mapped_column(String(50), nullable=False)
    external_account_id: Mapped[str] = mapped_column(String(255), nullable=False)
    external_account_label: Mapped[str] = mapped_column(String(255), nullable=False)
    credentials: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    status: Mapped[ConnectionStatus] = mapped_column(
        _pg_enum(ConnectionStatus, "connection_status"),
        nullable=False,
        default=ConnectionStatus.ACTIVE,
    )
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )

    sources: Mapped[list[DataSource]] = relationship(back_populates="connection")

    __table_args__ = (
        UniqueConstraint(
            "organization_id", "kind", "external_account_id",
            name="uq_connection_org_kind_account",
        ),
        Index("ix_connections_org_kind", "organization_id", "kind"),
    )


class DataSource(Base, UUIDMixin, TimestampMixin):
    """A specific resource exposed by a Connection (e.g., one spreadsheet)."""

    __tablename__ = "data_sources"

    organization_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    connection_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("connections.id", ondelete="CASCADE"),
        nullable=False,
    )
    kind: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    config: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    discovered_schema: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB, nullable=True
    )
    status: Mapped[DataSourceStatus] = mapped_column(
        _pg_enum(DataSourceStatus, "data_source_status"),
        nullable=False,
        default=DataSourceStatus.ACTIVE,
    )
    last_synced_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )

    connection: Mapped[Connection] = relationship(back_populates="sources")

    __table_args__ = (
        Index("ix_data_sources_org", "organization_id"),
        Index("ix_data_sources_connection", "connection_id"),
    )


class CanonicalSnapshot(Base, UUIDMixin, TimestampMixin):
    """One immutable-ish ingestion attempt for a data source.

    The snapshot is data-layer metadata only. It records when Baseflo mirrored a
    source into the canonical plane, how many assets/rows it saw, and any
    source-neutral evidence needed to replay or debug the mirror.
    """

    __tablename__ = "canonical_snapshots"

    organization_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    data_source_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("data_sources.id", ondelete="CASCADE"),
        nullable=False,
    )
    snapshot_key: Mapped[str] = mapped_column(String(255), nullable=False)
    mode: Mapped[str] = mapped_column(String(40), nullable=False, default="full_refresh")
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="running")
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    asset_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict
    )

    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "snapshot_key",
            name="uq_canonical_snapshot_org_key",
        ),
        Index("ix_canonical_snapshots_org", "organization_id", "started_at"),
        Index("ix_canonical_snapshots_source", "data_source_id", "started_at"),
    )


class CanonicalAsset(Base, UUIDMixin, TimestampMixin):
    """A source-neutral asset physically mirrored into DuckDB.

    Examples: one spreadsheet tab, one Shopify collection, one JSON child-array,
    one database table. This is not a business object; it is the canonical data
    catalog node agents and profilers can rely on.
    """

    __tablename__ = "canonical_assets"

    organization_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    data_source_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("data_sources.id", ondelete="CASCADE"),
        nullable=False,
    )
    snapshot_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("canonical_snapshots.id", ondelete="SET NULL"),
        nullable=True,
    )
    asset_key: Mapped[str] = mapped_column(String(255), nullable=False)
    qualified_name: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_table: Mapped[str] = mapped_column(String(255), nullable=False)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    asset_type: Mapped[str] = mapped_column(String(60), nullable=False, default="table")
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="active")
    row_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    field_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict
    )
    profile: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)

    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "qualified_name",
            name="uq_canonical_asset_org_qname",
        ),
        Index("ix_canonical_assets_org", "organization_id"),
        Index("ix_canonical_assets_source", "data_source_id"),
        Index("ix_canonical_assets_snapshot", "snapshot_id"),
    )


class CanonicalField(Base, UUIDMixin, TimestampMixin):
    """A physical field in a canonical asset."""

    __tablename__ = "canonical_fields"

    organization_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    asset_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("canonical_assets.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    storage_type: Mapped[str] = mapped_column(String(40), nullable=False, default="varchar")
    observed_type: Mapped[str] = mapped_column(String(40), nullable=False, default="unknown")
    nullable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sample_values: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    profile: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)

    __table_args__ = (
        UniqueConstraint("asset_id", "name", name="uq_canonical_field_asset_name"),
        Index("ix_canonical_fields_org", "organization_id"),
        Index("ix_canonical_fields_asset", "asset_id"),
    )


class DataGraphEdge(Base, UUIDMixin, TimestampMixin):
    """A typed edge in Baseflo's source-neutral data graph.

    Edges intentionally use string node ids so the graph can link different
    node kinds without a polymorphic-FK maze: sources, snapshots, canonical
    assets, fields, source paths, future structure maps, and external records.
    """

    __tablename__ = "data_graph_edges"

    organization_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    snapshot_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("canonical_snapshots.id", ondelete="SET NULL"),
        nullable=True,
    )
    subject_type: Mapped[str] = mapped_column(String(80), nullable=False)
    subject_id: Mapped[str] = mapped_column(String(255), nullable=False)
    predicate: Mapped[str] = mapped_column(String(120), nullable=False)
    object_type: Mapped[str] = mapped_column(String(80), nullable=False)
    object_id: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="active")
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    created_by: Mapped[str] = mapped_column(String(80), nullable=False, default="system")
    evidence: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)

    __table_args__ = (
        Index("ix_data_graph_edges_org_predicate", "organization_id", "predicate"),
        Index("ix_data_graph_edges_subject", "subject_type", "subject_id"),
        Index("ix_data_graph_edges_object", "object_type", "object_id"),
        Index("ix_data_graph_edges_snapshot", "snapshot_id"),
    )


class BusinessMemory(Base, UUIDMixin, TimestampMixin):
    """Confirmed business context that should shape future analysis."""

    __tablename__ = "business_memories"

    organization_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    key: Mapped[str] = mapped_column(String(255), nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[str] = mapped_column(String(80), nullable=False, default="note")
    scope: Mapped[str] = mapped_column(String(80), nullable=False, default="org")
    subject_ref: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    evidence_refs: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict
    )
    source: Mapped[str] = mapped_column(String(80), nullable=False, default="user")
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="active")
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    last_confirmed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        UniqueConstraint("organization_id", "key", name="uq_business_memory_org_key"),
        Index("ix_business_memories_org", "organization_id"),
        Index("ix_business_memories_org_kind", "organization_id", "kind"),
        Index("ix_business_memories_org_scope", "organization_id", "scope"),
    )


class Run(Base, UUIDMixin, TimestampMixin):
    """Durable async run envelope used by REST polling and SSE streams."""

    __tablename__ = "runs"

    organization_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    kind: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="queued")
    request: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    error: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_runs_org_status", "organization_id", "status"),
        Index("ix_runs_org_kind_created", "organization_id", "kind", "created_at"),
    )


class RunEvent(Base, UUIDMixin):
    """Durable event emitted during an async run."""

    __tablename__ = "run_events"

    run_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("runs.id", ondelete="CASCADE"), nullable=False
    )
    organization_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    type: Mapped[str] = mapped_column(String(160), nullable=False)
    stage: Mapped[str] = mapped_column(String(120), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    progress: Mapped[float | None] = mapped_column(Float, nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        Index("ix_run_events_run_created", "run_id", "created_at"),
        Index("ix_run_events_org_created", "organization_id", "created_at"),
    )


class AgentCacheEntry(Base, UUIDMixin):
    """Cached typed agent output keyed by agent, model, and canonical input hash."""

    __tablename__ = "agent_cache_entries"

    scope_key: Mapped[str] = mapped_column(String(120), nullable=False, default="global")
    agent_name: Mapped[str] = mapped_column(String(120), nullable=False)
    model_name: Mapped[str] = mapped_column(String(160), nullable=False)
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    output: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_used_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    hit_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    __table_args__ = (
        UniqueConstraint(
            "scope_key",
            "agent_name",
            "model_name",
            "input_hash",
            name="uq_agent_cache_agent_model_input",
        ),
        Index("ix_agent_cache_scope_agent_last_used", "scope_key", "agent_name", "last_used_at"),
    )


class OperatingArtifact(Base, UUIDMixin, TimestampMixin):
    """Durable product artifact produced from operating runs.

    The Artifact Plane owns the stable read model for Brief, Inbox, Ask, and
    future surfaces. It stores typed UI-ready payloads without tying the backend
    to a particular screen layout.
    """

    __tablename__ = "operating_artifacts"

    organization_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    run_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    artifact_key: Mapped[str] = mapped_column(String(500), nullable=False)
    kind: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="new")
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    why: Mapped[str] = mapped_column(Text, nullable=False, default="")
    tags: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    priority: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    source_refs: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    snoozed_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    dismissed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("organization_id", "artifact_key", name="uq_operating_artifact_org_key"),
        Index("ix_operating_artifacts_org_kind_status", "organization_id", "kind", "status"),
        Index("ix_operating_artifacts_org_last_seen", "organization_id", "last_seen_at"),
        Index("ix_operating_artifacts_run", "run_id"),
    )


class OperatingAction(Base, UUIDMixin, TimestampMixin):
    """Prepared/internal action created from a supported action artifact."""

    __tablename__ = "operating_actions"

    organization_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    artifact_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("operating_artifacts.id", ondelete="SET NULL"),
        nullable=True,
    )
    run_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    action_key: Mapped[str] = mapped_column(String(500), nullable=False)
    action_type: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="proposed")
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    why: Mapped[str] = mapped_column(Text, nullable=False, default="")
    source_refs: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    prepared_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    prepared_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    dismissed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("organization_id", "action_key", name="uq_operating_action_org_key"),
        Index("ix_operating_actions_org_status", "organization_id", "status"),
        Index("ix_operating_actions_org_type", "organization_id", "action_type"),
        Index("ix_operating_actions_artifact", "artifact_id"),
        Index("ix_operating_actions_run", "run_id"),
    )


class SavedCohort(Base, UUIDMixin, TimestampMixin):
    """Saved audience/cohort produced by Action Plane v1."""

    __tablename__ = "saved_cohorts"

    organization_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    action_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("operating_actions.id", ondelete="SET NULL"),
        nullable=True,
    )
    cohort_key: Mapped[str] = mapped_column(String(500), nullable=False)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    audience: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    rows: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    source_refs: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)

    __table_args__ = (
        UniqueConstraint("organization_id", "cohort_key", name="uq_saved_cohort_org_key"),
        Index("ix_saved_cohorts_org", "organization_id"),
        Index("ix_saved_cohorts_action", "action_id"),
    )
