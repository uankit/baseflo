"""Conversation, ConversationMessage, ConversationEvent repositories."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.db.models.conversation import (
    Conversation,
    ConversationEvent,
    ConversationMessage,
)


class ConversationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, conversation_id: UUID) -> Conversation:
        result = await self._session.get(Conversation, conversation_id)
        if result is None:
            raise NotFoundError(
                message=f"Conversation {conversation_id} not found.",
                error_code="BF-API-001",
                details={"conversation_id": str(conversation_id)},
            )
        return result

    async def create(self, conversation: Conversation) -> Conversation:
        self._session.add(conversation)
        await self._session.flush()
        return conversation


class ConversationMessageRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def append(self, message: ConversationMessage) -> ConversationMessage:
        self._session.add(message)
        await self._session.flush()
        return message

    async def list_for_conversation(
        self, conversation_id: UUID
    ) -> list[ConversationMessage]:
        stmt = (
            select(ConversationMessage)
            .where(ConversationMessage.conversation_id == conversation_id)
            .order_by(ConversationMessage.created_at)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())


class ConversationEventRepository:
    """Persisted SSE event log per conversation.

    The unique `(conversation_id, sequence)` constraint provides the gap-free
    monotonic sequence. We compute the next sequence under a per-conversation
    advisory lock to avoid the obvious race.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def _next_sequence(self, conversation_id: UUID) -> int:
        # Advisory lock keyed on a deterministic hash of the conversation UUID.
        # The lock auto-releases at transaction end (we're always inside one).
        # `pg_advisory_xact_lock` returns void; SELECT it as a scalar.
        await self._session.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:cid, 0))"),
            {"cid": str(conversation_id)},
        )
        stmt = (
            select(func.coalesce(func.max(ConversationEvent.sequence), 0))
            .where(ConversationEvent.conversation_id == conversation_id)
        )
        current_max = (await self._session.execute(stmt)).scalar_one()
        return int(current_max) + 1

    async def append(self, event: ConversationEvent) -> ConversationEvent:
        if event.sequence is None or event.sequence <= 0:
            event.sequence = await self._next_sequence(event.conversation_id)
        self._session.add(event)
        await self._session.flush()
        return event

    async def list_since(
        self, conversation_id: UUID, after_sequence: int = 0, limit: int = 1000
    ) -> list[ConversationEvent]:
        stmt = (
            select(ConversationEvent)
            .where(ConversationEvent.conversation_id == conversation_id)
            .where(ConversationEvent.sequence > after_sequence)
            .order_by(ConversationEvent.sequence)
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_sequence(
        self, conversation_id: UUID, sequence: int
    ) -> ConversationEvent | None:
        stmt = (
            select(ConversationEvent)
            .where(ConversationEvent.conversation_id == conversation_id)
            .where(ConversationEvent.sequence == sequence)
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()
