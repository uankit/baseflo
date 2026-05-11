"""Conversation endpoints: create, post message, stream events.

POST /api/v1/conversations                    — start a conversation + first message
POST /api/v1/conversations/{id}/messages      — append a follow-up
GET  /api/v1/conversations/{id}/events        — SSE stream (with replay support)
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.api.v1.sse import conversation_event_stream_response, resolve_last_sequence
from app.auth.dependencies import require_tenant
from app.core.context import TenantCtx
from app.core.errors import NotFoundError, ValidationError
from app.db.session import open_session
from app.observability.logging import get_logger
from app.orchestration.jobs.types import JobAccepted
from app.repositories.conversations import ConversationRepository
from app.services.conversation import ConversationService

router = APIRouter(prefix="/conversations", tags=["conversations"])

logger = get_logger("api.conversations")


# ---------- Request / response models ----------


class CreateConversationRequest(BaseModel):
    project_id: UUID
    content: str = Field(min_length=3, max_length=4000)


class MessageRequest(BaseModel):
    content: str = Field(min_length=1, max_length=4000)


class MessageResponse(BaseModel):
    message_id: UUID
    conversation_id: UUID


# ---------- DI helpers ----------


async def _conversation_service() -> ConversationService:
    """Build a ConversationService with the arq Redis pool when available."""
    from app.orchestration.jobs.arq_settings import _redis_settings  # noqa: PLC0415

    try:
        from arq import create_pool  # noqa: PLC0415

        pool = await create_pool(_redis_settings())
    except Exception:  # noqa: BLE001 — Redis may be down in dev; service degrades
        logger.warning("redis_unavailable_for_conversation_service")
        pool = None
    return ConversationService(redis=pool)


# ---------- Routes ----------


@router.post(
    "",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=JobAccepted,
    summary="Start a conversation and enqueue initial generation",
)
async def create_conversation(
    body: CreateConversationRequest,
    tenant: Annotated[TenantCtx, Depends(require_tenant)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> JobAccepted:
    if idempotency_key is not None and len(idempotency_key) < 8:
        raise ValidationError(
            message="Idempotency-Key must be at least 8 characters.",
            error_code="BF-VALID-009",
        )
    service = await _conversation_service()
    return await service.post_initial_message(
        tenant=tenant,
        project_id=body.project_id,
        content=body.content,
        idempotency_key=idempotency_key,
    )


@router.post(
    "/{conversation_id}/messages",
    status_code=status.HTTP_201_CREATED,
    response_model=MessageResponse,
    summary="Append a follow-up message to a conversation",
)
async def post_message(
    conversation_id: UUID,
    body: MessageRequest,
    tenant: Annotated[TenantCtx, Depends(require_tenant)],
) -> MessageResponse:
    service = await _conversation_service()
    msg = await service.post_message(
        tenant=tenant,
        conversation_id=conversation_id,
        content=body.content,
    )
    return MessageResponse(message_id=msg.id, conversation_id=conversation_id)


@router.get(
    "/{conversation_id}/events",
    summary="SSE stream of conversation events (with replay)",
)
async def stream_events(
    conversation_id: UUID,
    tenant: Annotated[TenantCtx, Depends(require_tenant)],
    last_event_id: Annotated[
        int | None,
        Header(alias="Last-Event-ID"),
    ] = None,
    seq: Annotated[int | None, Query(ge=0)] = None,
) -> StreamingResponse:
    """Server-Sent Events stream.

    `Last-Event-ID` (standard SSE header) or `?seq=` (manual reconnect
    fallback) is the sequence number to resume from. Absent or 0 means deliver
    from the beginning.
    """
    last_seq = resolve_last_sequence(last_event_id=last_event_id, seq=seq)
    async with open_session() as session:
        conversation = await ConversationRepository(session).get(conversation_id)
        if conversation.organization_id != tenant.organization_id:
            raise NotFoundError(
                message=f"Conversation {conversation_id} not found.",
                error_code="BF-API-001",
                details={"conversation_id": str(conversation_id)},
            )

    return conversation_event_stream_response(
        conversation_id=conversation_id,
        organization_id=tenant.organization_id,
        last_sequence=last_seq,
    )
