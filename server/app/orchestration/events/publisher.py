"""SSE event publisher.

Per docs/40-features/JOBS-AND-SSE.md §3.4. The publisher persists an event row
inside the caller's transaction; the DB trigger
`baseflo_conversation_event_notify` (created in migration 0004) fires
`pg_notify('conversation_<id>', sequence)` automatically.

The publisher does NOT do its own NOTIFY — the trigger handles it. This keeps
the event log and the broadcast atomic with the caller's other writes.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import UUID

from app.db.models.conversation import ConversationEvent
from app.observability.logging import get_logger
from app.orchestration.events.types import EventPayload, EventType
from app.repositories.conversations import ConversationEventRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger("orchestration.events.publisher")


async def emit_event(
    session: AsyncSession,
    *,
    conversation_id: UUID,
    payload: EventPayload,
) -> ConversationEvent:
    """Append an event to the persisted log. The DB trigger broadcasts.

    The `payload.type` field doubles as the event_type discriminator.
    """
    repo = ConversationEventRepository(session)
    event = ConversationEvent(
        conversation_id=conversation_id,
        sequence=0,  # repo computes the real sequence under advisory lock
        event_type=payload.type.value,
        payload=payload.model_dump(mode="json"),
    )
    persisted = await repo.append(event)

    logger.debug(
        "event_emitted",
        conversation_id=str(conversation_id),
        event_type=payload.type.value,
        sequence=persisted.sequence,
    )
    return persisted


async def emit_typed(
    session: AsyncSession,
    *,
    conversation_id: UUID,
    event_type: EventType,
    payload_data: dict[str, Any],
) -> ConversationEvent:
    """Lower-level helper for tests / dynamic publishers.

    Caller supplies the raw payload dict; we trust it matches the type. Use
    `emit_event` from production code for typed safety.
    """
    repo = ConversationEventRepository(session)
    event = ConversationEvent(
        conversation_id=conversation_id,
        sequence=0,
        event_type=event_type.value,
        payload=payload_data,
    )
    return await repo.append(event)
