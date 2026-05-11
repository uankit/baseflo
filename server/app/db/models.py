"""Core domain models."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin


# ---------------------------------------------------------------------------
# Auth / Tenant
# ---------------------------------------------------------------------------


class Organization(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)

    users: Mapped[list["User"]] = relationship(back_populates="organization")
    projects: Mapped[list["Project"]] = relationship(back_populates="organization")


class User(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "users"

    organization_id: Mapped[PGUUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    hashed_password: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    organization: Mapped[Organization] = relationship(back_populates="users")


# ---------------------------------------------------------------------------
# Projects & Sources
# ---------------------------------------------------------------------------


class Project(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "projects"

    organization_id: Mapped[PGUUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False)

    organization: Mapped[Organization] = relationship(back_populates="projects")
    sources: Mapped[list["DataSource"]] = relationship(back_populates="project")
    semantic_tables: Mapped[list["SemanticTable"]] = relationship(back_populates="project")
    insights: Mapped[list["Insight"]] = relationship(back_populates="project")
    kpis: Mapped[list["KPI"]] = relationship(back_populates="project")

    __table_args__ = (UniqueConstraint("organization_id", "slug"),)


class DataSource(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "data_sources"

    project_id: Mapped[PGUUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("projects.id"), nullable=False
    )
    kind: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    config: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    credentials: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    project: Mapped[Project] = relationship(back_populates="sources")
    sync_runs: Mapped[list["SyncRun"]] = relationship(back_populates="source")


class SyncRun(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "sync_runs"

    source_id: Mapped[PGUUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("data_sources.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    rows_synced: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    source: Mapped[DataSource] = relationship(back_populates="sync_runs")


# ---------------------------------------------------------------------------
# Semantic Layer
# ---------------------------------------------------------------------------


class SemanticTable(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "semantic_tables"

    project_id: Mapped[PGUUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("projects.id"), nullable=False
    )
    source_id: Mapped[PGUUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("data_sources.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_table_name: Mapped[str] = mapped_column(String(200), nullable=False)
    row_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    project: Mapped[Project] = relationship(back_populates="semantic_tables")
    columns: Mapped[list["SemanticColumn"]] = relationship(back_populates="table")


class SemanticColumn(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "semantic_columns"

    table_id: Mapped[PGUUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("semantic_tables.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    data_type: Mapped[str] = mapped_column(String(50), nullable=False)
    physical_type: Mapped[str] = mapped_column(String(50), nullable=False)
    nullable: Mapped[bool] = mapped_column(Boolean, default=True)
    is_primary_key: Mapped[bool] = mapped_column(Boolean, default=False)
    is_foreign_key: Mapped[bool] = mapped_column(Boolean, default=False)
    foreign_key_target: Mapped[str | None] = mapped_column(String(200), nullable=True)
    semantic_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    sample_values: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    distinct_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    null_rate: Mapped[float | None] = mapped_column(Numeric, nullable=True)

    table: Mapped[SemanticTable] = relationship(back_populates="columns")


class Relationship(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "relationships"

    project_id: Mapped[PGUUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("projects.id"), nullable=False
    )
    from_table: Mapped[str] = mapped_column(String(100), nullable=False)
    from_column: Mapped[str] = mapped_column(String(100), nullable=False)
    to_table: Mapped[str] = mapped_column(String(100), nullable=False)
    to_column: Mapped[str] = mapped_column(String(100), nullable=False)
    confidence: Mapped[float] = mapped_column(Numeric, default=0.0)
    detected_by: Mapped[str] = mapped_column(String(20), default="agent")


# ---------------------------------------------------------------------------
# Insights
# ---------------------------------------------------------------------------


class Insight(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "insights"

    project_id: Mapped[PGUUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("projects.id"), nullable=False
    )
    kind: Mapped[str] = mapped_column(String(50), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), default="info")
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    narrative: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float] = mapped_column(Numeric, default=0.0)
    sql: Mapped[str | None] = mapped_column(Text, nullable=True)
    data: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    is_dismissed: Mapped[bool] = mapped_column(Boolean, default=False)

    project: Mapped[Project] = relationship(back_populates="insights")


# ---------------------------------------------------------------------------
# KPIs
# ---------------------------------------------------------------------------


class KPI(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "kpis"

    project_id: Mapped[PGUUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("projects.id"), nullable=False
    )
    slug: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    sql: Mapped[str] = mapped_column(Text, nullable=False)
    unit: Mapped[str | None] = mapped_column(String(50), nullable=True)
    refresh_interval: Mapped[str] = mapped_column(String(20), default="1h")
    is_autogenerated: Mapped[bool] = mapped_column(Boolean, default=True)

    project: Mapped[Project] = relationship(back_populates="kpis")
    values: Mapped[list["KPIValue"]] = relationship(back_populates="kpi")

    __table_args__ = (UniqueConstraint("project_id", "slug"),)


class KPIValue(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "kpi_values"

    kpi_id: Mapped[PGUUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("kpis.id"), nullable=False
    )
    value: Mapped[float] = mapped_column(Numeric, nullable=False)
    previous_value: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    change_percent: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    kpi: Mapped[KPI] = relationship(back_populates="values")


# ---------------------------------------------------------------------------
# Conversations (drill-down)
# ---------------------------------------------------------------------------


class Conversation(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "conversations"

    project_id: Mapped[PGUUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("projects.id"), nullable=False
    )
    user_id: Mapped[PGUUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    title: Mapped[str | None] = mapped_column(String(200), nullable=True)

    messages: Mapped[list["Message"]] = relationship(back_populates="conversation")


class Message(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "messages"

    conversation_id: Mapped[PGUUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("conversations.id"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    sql: Mapped[str | None] = mapped_column(Text, nullable=True)
    data: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)

    conversation: Mapped[Conversation] = relationship(back_populates="messages")


class MagicLinkToken(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "magic_link_tokens"

    email: Mapped[str] = mapped_column(String(255), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)
