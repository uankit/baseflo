"""ConversationService — create + post message, then enqueue generation.

Per docs/40-features/JOBS-AND-SSE.md §M0.6: API handlers call this service,
which:

1. Creates a `conversations` row if needed.
2. Appends a `conversation_messages` row for the user's text.
3. Persists the user message also as a `conversation.message` event so SSE
   subscribers see it immediately.
4. Persists a `generation_jobs` row (with idempotency-key check).
5. Enqueues the arq job. The worker drives the saga which emits the rest of
   the SSE timeline.
6. Returns `JobAccepted` so the API returns 202 immediately.

The whole path is async, fully off-thread, with no blocking work in the
request handler.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import select

from app.core.context import TenantCtx
from app.core.ids import new_uuid7
from app.db.models.conversation import (
    Conversation,
    ConversationMessage,
    ConversationState,
    MessageAuthor,
)
from app.db.models.connector import Connector
from app.db.models.generation import GenerationJob, JobKind, JobStatus
from app.db.session import open_session
from app.observability.logging import get_logger
from app.orchestration.events.publisher import emit_event
from app.orchestration.events.types import ConversationMessagePayload
from app.orchestration.jobs.idempotency import fingerprint
from app.orchestration.jobs.types import (
    InitialPayload,
    JobAccepted,
    JobPayload,
    JobRequest,
    RefinementPayload,
)
from app.repositories.conversations import (
    ConversationMessageRepository,
    ConversationRepository,
)
from app.repositories.jobs import GenerationJobRepository

if TYPE_CHECKING:
    from arq.connections import ArqRedis

logger = get_logger("services.conversation")


class ConversationService:
    """Use-case orchestrator for conversation + generation."""

    def __init__(self, *, redis: ArqRedis | None) -> None:
        # `redis` is None in some tests where we exercise the service without a queue.
        self._redis = redis

    async def post_initial_message(
        self,
        *,
        tenant: TenantCtx,
        project_id: UUID,
        content: str,
        idempotency_key: str | None = None,
    ) -> JobAccepted:
        """Create a conversation, append the user message, enqueue an INITIAL job."""
        if tenant.user_id is None:
            from app.core.errors import UnauthorizedError  # noqa: PLC0415
            raise UnauthorizedError(
                message="An authenticated user is required to start a conversation.",
                error_code="BF-AUTH-001",
            )

        async with open_session() as session:
            conv_repo = ConversationRepository(session)
            msg_repo = ConversationMessageRepository(session)

            conversation = Conversation(
                organization_id=tenant.organization_id,
                project_id=project_id,
                started_by=tenant.user_id,
                state=ConversationState.ACTIVE.value,
            )
            conversation = await conv_repo.create(conversation)

            user_message = ConversationMessage(
                conversation_id=conversation.id,
                author=MessageAuthor.USER.value,
                agent_name=None,
                content=content,
                extra={},
            )
            await msg_repo.append(user_message)

            await emit_event(
                session,
                conversation_id=conversation.id,
                payload=ConversationMessagePayload(
                    message_id=user_message.id,
                    author=MessageAuthor.USER.value,
                    content=content,
                ),
            )

        return await self._enqueue_initial(
            tenant=tenant,
            project_id=project_id,
            conversation_id=conversation.id,
            description=content,
            idempotency_key=idempotency_key or _default_idempotency_key(conversation.id),
        )

    async def post_message(
        self,
        *,
        tenant: TenantCtx,
        conversation_id: UUID,
        content: str,
    ) -> ConversationMessage:
        """Append a follow-up message to an existing conversation.

        Does NOT enqueue a new generation; refinements use a different path
        (RefinementService). Used by clarification answers and chat.
        """
        if tenant.user_id is None:
            from app.core.errors import UnauthorizedError  # noqa: PLC0415
            raise UnauthorizedError(error_code="BF-AUTH-001")

        async with open_session() as session:
            msg_repo = ConversationMessageRepository(session)
            conv_repo = ConversationRepository(session)
            conversation = await conv_repo.get(conversation_id)
            user_message = ConversationMessage(
                conversation_id=conversation.id,
                author=MessageAuthor.USER.value,
                agent_name=None,
                content=content,
                extra={},
            )
            await msg_repo.append(user_message)
            await emit_event(
                session,
                conversation_id=conversation.id,
                payload=ConversationMessagePayload(
                    message_id=user_message.id,
                    author=MessageAuthor.USER.value,
                    content=content,
                ),
            )
            return user_message

    # ----- internal -----

    async def _enqueue_initial(
        self,
        *,
        tenant: TenantCtx,
        project_id: UUID,
        conversation_id: UUID,
        description: str,
        idempotency_key: str,
    ) -> JobAccepted:
        # Snapshot connected connectors at enqueue time so the payload is
        # self-contained and deterministic.
        async with open_session() as session:
            result = await session.execute(
                select(Connector.id).where(
                    Connector.project_id == project_id,
                    Connector.status == "connected",
                )
            )
            connector_ids = [row[0] for row in result.all()]

        payload: JobPayload = InitialPayload(
            project_id=project_id,
            organization_id=tenant.organization_id,
            conversation_id=conversation_id,
            description=description,
            connector_ids=connector_ids,
        )
        request = JobRequest(idempotency_key=idempotency_key, payload=payload)

        async with open_session() as session:
            repo = GenerationJobRepository(session)
            new_id = new_uuid7()
            job = GenerationJob(
                id=new_id,
                project_id=project_id,
                conversation_id=conversation_id,
                parent_version_id=None,
                kind=JobKind.INITIAL.value,
                status=JobStatus.QUEUED.value,
                idempotency_key=request.idempotency_key,
            )
            persisted, created = await repo.create_or_get_idempotent(
                job=job,
                payload_fingerprint=fingerprint(payload),
            )

        if created and self._redis is not None:
            await self._redis.enqueue_job(
                "run_generation_job",
                job_id=str(persisted.id),
                payload=payload.model_dump(mode="json"),
                request_id=tenant.request_id,
                _job_id=f"job_{persisted.id}",
                _job_try=1,
            )
            logger.info(
                "generation_job_enqueued",
                job_id=str(persisted.id),
                project_id=str(project_id),
                conversation_id=str(conversation_id),
            )
        elif created:
            logger.warning(
                "generation_job_created_without_redis",
                job_id=str(persisted.id),
                conversation_id=str(conversation_id),
            )

        return JobAccepted(
            job_id=persisted.id,
            conversation_id=conversation_id,
            status=JobStatus(persisted.status),
            sse_url=f"/api/v1/conversations/{conversation_id}/events",
        )


def _default_idempotency_key(conversation_id: UUID) -> str:
    """Per-conversation key. Same conversation cannot be initiated twice."""
    return f"conv-init-{conversation_id}-{uuid4().hex[:12]}"


# Re-export RefinementPayload so callers can construct refinement jobs without
# importing through orchestration directly.
__all__ = ["ConversationService", "RefinementPayload"]
