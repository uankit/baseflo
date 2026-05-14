"""Auth domain models.

Only auth/tenant tables live here. Legacy (project, sources, insights, kpis,
conversations) live in `_legacy_models.py` and are NOT loaded into
`Base.metadata` by default — alembic autogen sees only this file.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Float,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
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

    memberships: Mapped[list["Membership"]] = relationship(back_populates="organization")
    invitations: Mapped[list["Invitation"]] = relationship(back_populates="organization")


class User(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    status: Mapped[UserStatus] = mapped_column(
        _pg_enum(UserStatus, "user_status"),
        nullable=False,
        default=UserStatus.ACTIVE,
    )

    memberships: Mapped[list["Membership"]] = relationship(back_populates="user")
    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(back_populates="user")


class Membership(Base, UUIDMixin, TimestampMixin):
    """User ↔ Organization with a role and status. One row per (user, org)."""

    __tablename__ = "memberships"

    user_id: Mapped[PGUUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    organization_id: Mapped[PGUUID] = mapped_column(
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

    organization_id: Mapped[PGUUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[Role] = mapped_column(_pg_enum(Role, "member_role"), nullable=False)
    invited_by_user_id: Mapped[PGUUID | None] = mapped_column(
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

    user_id: Mapped[PGUUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    organization_id: Mapped[PGUUID] = mapped_column(
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
    replaced_by_id: Mapped[PGUUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("refresh_tokens.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    user: Mapped[User] = relationship(back_populates="refresh_tokens")


class AuthEvent(Base, UUIDMixin):
    """Immutable audit log of auth-related actions."""

    __tablename__ = "auth_events"

    user_id: Mapped[PGUUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    organization_id: Mapped[PGUUID | None] = mapped_column(
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

    organization_id: Mapped[PGUUID] = mapped_column(
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
    created_by_user_id: Mapped[PGUUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )

    sources: Mapped[list["DataSource"]] = relationship(back_populates="connection")

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

    organization_id: Mapped[PGUUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    connection_id: Mapped[PGUUID] = mapped_column(
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
    created_by_user_id: Mapped[PGUUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )

    connection: Mapped[Connection] = relationship(back_populates="sources")

    __table_args__ = (
        Index("ix_data_sources_org", "organization_id"),
        Index("ix_data_sources_connection", "connection_id"),
    )


class OperatingAsset(Base, UUIDMixin, TimestampMixin):
    """A queryable business object Baseflo has discovered from connected data.

    This is the first durable layer of the adaptive Business OS: it records what
    exists without forcing the user into a template or pre-selected vertical.
    """

    __tablename__ = "operating_assets"

    organization_id: Mapped[PGUUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    data_source_id: Mapped[PGUUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("data_sources.id", ondelete="SET NULL"),
        nullable=True,
    )
    qualified_name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_name: Mapped[str] = mapped_column(String(200), nullable=False)
    table_label: Mapped[str] = mapped_column(String(200), nullable=False)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    column_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="active")
    profile: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    last_profiled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "qualified_name",
            name="uq_operating_asset_org_qname",
        ),
        Index("ix_operating_assets_org", "organization_id"),
        Index("ix_operating_assets_source", "data_source_id"),
    )


class OperatingColumn(Base, UUIDMixin, TimestampMixin):
    """A profiled column belonging to an OperatingAsset."""

    __tablename__ = "operating_columns"

    organization_id: Mapped[PGUUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    asset_id: Mapped[PGUUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("operating_assets.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    observed_type: Mapped[str] = mapped_column(String(40), nullable=False)
    semantic_type: Mapped[str] = mapped_column(String(60), nullable=False)
    null_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    unique_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    sample_values: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    profile: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)

    __table_args__ = (
        UniqueConstraint("asset_id", "name", name="uq_operating_column_asset_name"),
        Index("ix_operating_columns_org", "organization_id"),
        Index("ix_operating_columns_asset", "asset_id"),
    )


class OperatingRelationship(Base, UUIDMixin, TimestampMixin):
    """A candidate or confirmed relationship inferred across operating assets."""

    __tablename__ = "operating_relationships"

    organization_id: Mapped[PGUUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    left_asset_id: Mapped[PGUUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("operating_assets.id", ondelete="CASCADE"),
        nullable=False,
    )
    right_asset_id: Mapped[PGUUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("operating_assets.id", ondelete="CASCADE"),
        nullable=False,
    )
    left_column: Mapped[str] = mapped_column(String(255), nullable=False)
    right_column: Mapped[str] = mapped_column(String(255), nullable=False)
    relationship_kind: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="candidate")
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)

    __table_args__ = (
        Index("ix_operating_relationships_org", "organization_id"),
        Index("ix_operating_relationships_left", "left_asset_id"),
        Index("ix_operating_relationships_right", "right_asset_id"),
    )


class MetricDefinition(Base, UUIDMixin, TimestampMixin):
    """A tracked, data-grounded metric compiled from the operating model."""

    __tablename__ = "metric_definitions"

    organization_id: Mapped[PGUUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    asset_id: Mapped[PGUUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("operating_assets.id", ondelete="SET NULL"),
        nullable=True,
    )
    key: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    metric_type: Mapped[str] = mapped_column(String(50), nullable=False)
    expression_sql: Mapped[str] = mapped_column(Text, nullable=False)
    grain: Mapped[str | None] = mapped_column(String(80), nullable=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="candidate")
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    definition: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_by: Mapped[str] = mapped_column(String(80), nullable=False, default="system")

    __table_args__ = (
        UniqueConstraint("organization_id", "key", name="uq_metric_definition_org_key"),
        Index("ix_metric_definitions_org", "organization_id"),
        Index("ix_metric_definitions_asset", "asset_id"),
    )


class MetricValue(Base, UUIDMixin):
    """A computed metric value at a point in time."""

    __tablename__ = "metric_values"

    organization_id: Mapped[PGUUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    metric_id: Mapped[PGUUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("metric_definitions.id", ondelete="CASCADE"),
        nullable=False,
    )
    value: Mapped[float | None] = mapped_column(Float, nullable=True)
    value_text: Mapped[str | None] = mapped_column(String(255), nullable=True)
    period_start: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    period_end: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    evidence: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)

    __table_args__ = (
        Index("ix_metric_values_org_computed", "organization_id", "computed_at"),
        Index("ix_metric_values_metric_computed", "metric_id", "computed_at"),
    )


class Insight(Base, UUIDMixin, TimestampMixin):
    """A grounded finding produced by the Watcher or starter analysis."""

    __tablename__ = "insights"

    organization_id: Mapped[PGUUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    kind: Mapped[str] = mapped_column(String(60), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(String(40), nullable=False, default="info")
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="open")
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    impact_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    source: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    dismissed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        Index("ix_insights_org_status", "organization_id", "status", "detected_at"),
        Index("ix_insights_org_kind", "organization_id", "kind", "detected_at"),
    )


class BusinessMemory(Base, UUIDMixin, TimestampMixin):
    """Confirmed business context that should shape future analysis."""

    __tablename__ = "business_memories"

    organization_id: Mapped[PGUUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    key: Mapped[str] = mapped_column(String(255), nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String(80), nullable=False, default="user")
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="active")
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    last_confirmed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        UniqueConstraint("organization_id", "key", name="uq_business_memory_org_key"),
        Index("ix_business_memories_org", "organization_id"),
    )


class ActionProposal(Base, UUIDMixin, TimestampMixin):
    """A controlled next step proposed by Baseflo, never executed silently."""

    __tablename__ = "action_proposals"

    organization_id: Mapped[PGUUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    insight_id: Mapped[PGUUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("insights.id", ondelete="SET NULL"),
        nullable=True,
    )
    kind: Mapped[str] = mapped_column(String(80), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="proposed")
    proposed_payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    approval_scope: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    created_by_agent: Mapped[str] = mapped_column(String(80), nullable=False)
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    executed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        UniqueConstraint("organization_id", "idempotency_key", name="uq_action_org_key"),
        Index("ix_action_proposals_org_status", "organization_id", "status"),
    )


class AuditEvent(Base, UUIDMixin):
    """Append-only governance record for intelligence and action events."""

    __tablename__ = "audit_events"

    organization_id: Mapped[PGUUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    actor_user_id: Mapped[PGUUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    actor_type: Mapped[str] = mapped_column(String(40), nullable=False)
    action: Mapped[str] = mapped_column(String(120), nullable=False)
    target_type: Mapped[str] = mapped_column(String(80), nullable=False)
    target_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict
    )
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    __table_args__ = (
        Index("ix_audit_events_org_time", "organization_id", "occurred_at"),
        Index("ix_audit_events_org_action", "organization_id", "action", "occurred_at"),
    )
