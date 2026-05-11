"""Connector + ConnectorToken — per-project source connections."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from sqlalchemy import ARRAY, CheckConstraint, DateTime, ForeignKey, LargeBinary, String
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base import Base, SoftDeleteMixin, TimestampedMixin, uuid7_default


class ConnectorStatus(StrEnum):
    CONNECTED = "connected"
    ERROR = "error"
    REVOKED = "revoked"
    EXPIRED = "expired"


class TokenType(StrEnum):
    OAUTH2 = "oauth2"
    API_KEY = "api_key"
    DB_URL = "db_url"
    SERVICE_ACCOUNT = "service_account"


class Connector(Base, TimestampedMixin, SoftDeleteMixin):
    __tablename__ = "connectors"
    __table_args__ = (
        CheckConstraint(
            "status IN ('connected', 'error', 'revoked', 'expired')",
            name="status_enum",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid7_default
    )
    organization_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE", name="fk__connectors__organization_id__organizations"),
        nullable=False,
    )
    project_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE", name="fk__connectors__project_id__projects"),
        nullable=False,
    )
    kind: Mapped[str] = mapped_column(String(60), nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=ConnectorStatus.CONNECTED)
    config: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)


class ConnectorToken(Base):
    __tablename__ = "connector_tokens"
    __table_args__ = (
        CheckConstraint(
            "token_type IN ('oauth2', 'api_key', 'db_url', 'service_account')",
            name="token_type_enum",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid7_default
    )
    connector_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("connectors.id", ondelete="CASCADE", name="fk__connector_tokens__connector_id__connectors"),
        nullable=False,
    )
    token_type: Mapped[str] = mapped_column(String(30), nullable=False)
    ciphertext: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    wrapped_dek: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    scopes: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, default=list)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
