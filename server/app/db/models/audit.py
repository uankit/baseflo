"""AuditEvent — append-only security audit log."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base import Base, uuid7_default


class ActorType(StrEnum):
    USER = "user"
    AGENT = "agent"
    SYSTEM = "system"
    API_KEY = "api_key"


class AuditAction(StrEnum):
    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    EXPORT = "export"
    CONNECTOR_CONNECT = "connector.connect"
    CONNECTOR_REVOKE = "connector.revoke"
    AUTH_LOGIN = "auth.login"
    AUTH_LOGOUT = "auth.logout"
    PII_REVEAL = "pii.reveal"


class AuditEvent(Base):
    __tablename__ = "audit_events"
    __table_args__ = (
        CheckConstraint(
            "actor_type IN ('user', 'agent', 'system', 'api_key')",
            name="actor_type_enum",
        ),
        Index(
            "ix__audit_events__organization_id__created_at",
            "organization_id", "created_at",
        ),
        Index(
            "ix__audit_events__pii_reveal",
            "organization_id", "created_at",
            postgresql_where="action = 'pii.reveal'",
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid7_default)
    organization_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE", name="fk__audit_events__organization_id__organizations"),
        nullable=False,
    )
    actor_type: Mapped[str] = mapped_column(String(20), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(255), nullable=False)
    action: Mapped[str] = mapped_column(String(60), nullable=False)
    target_kind: Mapped[str] = mapped_column(String(80), nullable=False)
    target_id: Mapped[str] = mapped_column(String(255), nullable=False)
    extra: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
