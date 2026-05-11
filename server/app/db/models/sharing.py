"""Export, ShareLink, FeedbackEvent — sharing and flywheel."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from sqlalchemy import ARRAY, CheckConstraint, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base import Base, uuid7_default


class ExportFormat(StrEnum):
    CSV = "csv"
    SQL = "sql"
    JSON = "json"
    FULL = "full"


class ExportStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    READY = "ready"
    EXPIRED = "expired"
    FAILED = "failed"


class FeedbackTargetType(StrEnum):
    ENTITY_RECONCILIATION = "entity_reconciliation"
    COLUMN_CLASSIFICATION = "column_classification"
    KPI_SELECTION = "kpi_selection"
    CARDINALITY = "cardinality"
    GENERAL = "general"


class Export(Base):
    __tablename__ = "exports"
    __table_args__ = (
        CheckConstraint(
            "format IN ('csv', 'sql', 'json', 'full')",
            name="format_enum",
        ),
        CheckConstraint(
            "status IN ('queued', 'running', 'ready', 'expired', 'failed')",
            name="status_enum",
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid7_default)
    organization_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE", name="fk__exports__organization_id__organizations"),
        nullable=False,
    )
    project_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE", name="fk__exports__project_id__projects"),
        nullable=False,
    )
    project_version_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("project_versions.id", ondelete="RESTRICT", name="fk__exports__project_version_id__project_versions"),
        nullable=False,
    )
    format: Mapped[str] = mapped_column(String(10), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=ExportStatus.QUEUED)
    file_url_signed: Mapped[str | None] = mapped_column(Text, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    requested_by: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT", name="fk__exports__requested_by__users"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ShareLink(Base):
    __tablename__ = "share_links"
    __table_args__ = (
        UniqueConstraint("token", name="uq__share_links__token"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid7_default)
    organization_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE", name="fk__share_links__organization_id__organizations"),
        nullable=False,
    )
    project_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE", name="fk__share_links__project_id__projects"),
        nullable=False,
    )
    project_version_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("project_versions.id", ondelete="RESTRICT", name="fk__share_links__project_version_id__project_versions"),
        nullable=False,
    )
    token: Mapped[str] = mapped_column(String(64), nullable=False)
    permissions: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, default=list)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT", name="fk__share_links__created_by__users"),
        nullable=False,
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class FeedbackEvent(Base):
    __tablename__ = "feedback_events"
    __table_args__ = (
        CheckConstraint(
            "target_type IN ('entity_reconciliation', 'column_classification', 'kpi_selection', 'cardinality', 'general')",
            name="target_type_enum",
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid7_default)
    organization_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE", name="fk__feedback_events__organization_id__organizations"),
        nullable=False,
    )
    project_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE", name="fk__feedback_events__project_id__projects"),
        nullable=False,
    )
    project_version_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("project_versions.id", ondelete="RESTRICT", name="fk__feedback_events__project_version_id__project_versions"),
        nullable=False,
    )
    target_type: Mapped[str] = mapped_column(String(40), nullable=False)
    target_id: Mapped[str] = mapped_column(String(120), nullable=False)
    correction: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT", name="fk__feedback_events__created_by__users"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
