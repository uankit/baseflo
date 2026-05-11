"""Conversation + ConversationMessage + ConversationEvent.

ConversationEvent is the persisted SSE stream — clients can resume from a
sequence number after a disconnect (see docs/40-features/JOBS-AND-SSE.md §3.4).
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base import Base, TimestampedMixin, uuid7_default


class ConversationState(StrEnum):
    ACTIVE = "active"
    AWAITING_CLARIFICATION = "awaiting_clarification"
    CLOSED = "closed"


class MessageAuthor(StrEnum):
    USER = "user"
    SYSTEM = "system"
    AGENT = "agent"


class EventType(StrEnum):
    CONVERSATION_MESSAGE = "conversation.message"
    CLARIFICATION_REQUIRED = "clarification.required"
    AGENT_START = "agent.start"
    AGENT_COMPLETE = "agent.complete"
    VALIDATION_PASSED = "validation.passed"
    VALIDATION_WARNING = "validation.warning"
    VALIDATION_FAILED = "validation.failed"
    ARTIFACT_READY = "artifact.ready"
    WORKSPACE_READY = "workspace.ready"
    ERROR_RECOVERABLE = "error.recoverable"
    ERROR_TERMINAL = "error.terminal"


class Conversation(Base, TimestampedMixin):
    __tablename__ = "conversations"
    __table_args__ = (
        CheckConstraint(
            "state IN ('active', 'awaiting_clarification', 'closed')",
            name="state_enum",
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid7_default)
    organization_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE", name="fk__conversations__organization_id__organizations"),
        nullable=False,
    )
    project_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE", name="fk__conversations__project_id__projects"),
        nullable=False,
    )
    started_by: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT", name="fk__conversations__started_by__users"),
        nullable=False,
    )
    state: Mapped[str] = mapped_column(String(30), nullable=False, default=ConversationState.ACTIVE)


class ConversationMessage(Base):
    __tablename__ = "conversation_messages"
    __table_args__ = (
        CheckConstraint(
            "author IN ('user', 'system', 'agent')",
            name="author_enum",
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid7_default)
    conversation_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE", name="fk__conversation_messages__conversation_id__conversations"),
        nullable=False,
    )
    author: Mapped[str] = mapped_column(String(20), nullable=False)
    agent_name: Mapped[str | None] = mapped_column(String(80), nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    extra: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ConversationEvent(Base):
    __tablename__ = "conversation_events"
    __table_args__ = (
        UniqueConstraint(
            "conversation_id", "sequence",
            name="uq__conversation_events__conversation_id__sequence",
        ),
        Index(
            "ix__conversation_events__created_at",
            "created_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid7_default)
    conversation_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE", name="fk__conversation_events__conversation_id__conversations"),
        nullable=False,
    )
    sequence: Mapped[int] = mapped_column(BigInteger, nullable=False)
    event_type: Mapped[str] = mapped_column(String(60), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
