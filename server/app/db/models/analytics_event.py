"""AnalyticsEvent — typed behavioral event row.

One row per event the SDK / webhook / connector ingests. The `event_name`
must be in the project's event taxonomy at insert time; the validator
runs in the service layer (see `app/services/events/ingestion.py`).
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base import Base, uuid7_default


class EventSource(StrEnum):
    SDK = "sdk"
    WEBHOOK = "webhook"
    CONNECTOR = "connector"
    MANUAL = "manual"


class AnalyticsEvent(Base):
    __tablename__ = "analytics_events"
    __table_args__ = (
        CheckConstraint(
            "source IN ('sdk', 'webhook', 'connector', 'manual')",
            name="source_enum",
        ),
        Index(
            "ix__analytics_events__org_project_occurred",
            "organization_id", "project_id", "occurred_at",
        ),
        Index(
            "ix__analytics_events__org_project_event_occurred",
            "organization_id", "project_id", "event_name", "occurred_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid7_default,
    )
    organization_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(
            "organizations.id", ondelete="CASCADE",
            name="fk__analytics_events__organization_id__organizations",
        ),
        nullable=False,
    )
    project_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(
            "projects.id", ondelete="CASCADE",
            name="fk__analytics_events__project_id__projects",
        ),
        nullable=False,
    )
    project_version_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(
            "project_versions.id", ondelete="SET NULL",
            name="fk__analytics_events__project_version_id__project_versions",
        ),
        nullable=True,
    )
    event_name: Mapped[str] = mapped_column(String(120), nullable=False)
    distinct_id: Mapped[str] = mapped_column(String(255), nullable=False)
    entity_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    properties: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict,
    )
    source: Mapped[str] = mapped_column(
        String(20), nullable=False, default=EventSource.SDK,
    )
    idempotency_key: Mapped[str | None] = mapped_column(String(120), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
    )
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
    )
