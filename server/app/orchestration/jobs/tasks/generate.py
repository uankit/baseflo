"""arq task — runs the generation pipeline.

The worker entry point that arq dispatches. Responsibilities:

1. Set the `TenantCtx` so RLS scoping works inside the graph run.
2. Mark the GenerationJob as `running`.
3. Run `BuildPipeline.run(...)` which produces versioned artifacts.
4. Mark the job as `succeeded` or `failed` on completion.
5. Re-raise unhandled exceptions so arq's retry/DLQ logic fires.

Per docs/40-features/JOBS-AND-SSE.md §3.1 — every job category is just an
`arq` async function returning typed status. Idempotency is enforced at
*enqueue* time (in the API layer) so worker code stays linear.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from app.core.context import TenantCtx, set_job_id, set_tenant_ctx
from app.core.errors import BasefloError
from app.db.models.generation import JobStatus
from app.db.session import open_session
from app.observability.logging import get_logger
from app.orchestration.events.publisher import emit_event
from app.orchestration.events.types import ErrorPayload, EventType
from app.orchestration.jobs.cancellation import GenerationCancelledError
from app.repositories.jobs import GenerationJobRepository

if TYPE_CHECKING:
    from app.orchestration.jobs.types import JobPayload

logger = get_logger("orchestration.jobs.generate")


async def run_generation_job(
    ctx: dict[str, Any],
    *,
    job_id: str,
    payload: dict[str, Any],
    request_id: str | None = None,
) -> dict[str, Any]:
    """arq function. Receives the typed payload as JSON-roundtripped dict.

    Returns a small result dict that arq stores in Redis (read-only history).
    """
    from app.orchestration.jobs.types import (
        ConnectorAddedPayload,
        InitialPayload,
        RefinementPayload,
        ReIntrospectPayload,
    )

    parsed: JobPayload
    kind = payload.get("kind")
    match kind:
        case "initial":
            parsed = InitialPayload(**payload)
        case "refinement":
            parsed = RefinementPayload(**payload)
        case "connector_added":
            parsed = ConnectorAddedPayload(**payload)
        case "re_introspect":
            parsed = ReIntrospectPayload(**payload)
        case _:
            raise BasefloError(
                error_code="BF-JOB-003",
                message=f"Unknown job kind: {kind!r}",
                status_code=500,
            )

    job_uuid = UUID(job_id)
    set_job_id(job_uuid)
    set_tenant_ctx(
        TenantCtx(
            organization_id=parsed.organization_id,
            user_id=None,  # worker-side; original actor is on the persisted job row
            request_id=request_id or f"job_{job_id}",
        )
    )

    return await _run_with_status_tracking(
        job_uuid=job_uuid,
        payload=parsed,
    )


async def _run_with_status_tracking(
    *,
    job_uuid: UUID,
    payload: JobPayload,
) -> dict[str, Any]:
    """Wrap the artifact-centric build pipeline in transactional status updates."""
    started_at = datetime.now(UTC)

    # Mark running
    async with open_session() as session:
        repo = GenerationJobRepository(session)
        job = await repo.get(job_uuid)
        if job.status == JobStatus.CANCELLED.value:
            job.completed_at = datetime.now(UTC)
            await _emit_terminal_error(
                payload=payload,
                error_code="BF-JOB-003",
                message="Build cancelled.",
            )
            return {
                "job_id": str(job_uuid),
                "status": JobStatus.CANCELLED.value,
            }
        job.status = JobStatus.RUNNING.value
        job.started_at = started_at

    try:
        from app.pipeline import BuildPipeline, BuildRequest
        from app.orchestration.jobs.types import (
            ConnectorAddedPayload,
            InitialPayload,
            RefinementPayload,
            ReIntrospectPayload,
        )

        match payload:
            case InitialPayload():
                connector_ids = payload.connector_ids
                business_description = payload.description
            case ConnectorAddedPayload():
                connector_ids = [payload.connector_id]
                business_description = ""
            case ReIntrospectPayload():
                connector_ids = [payload.connector_id]
                business_description = ""
            case RefinementPayload():
                # Refinement re-runs with all connected connectors.
                # The payload currently does not carry connector_ids; fetch from DB.
                from sqlalchemy import select
                from app.db.models.connector import Connector

                async with open_session() as session:
                    result = await session.execute(
                        select(Connector.id).where(
                            Connector.project_id == payload.project_id,
                            Connector.status == "connected",
                        )
                    )
                    connector_ids = [row[0] for row in result.all()]
                business_description = ""
            case _:
                raise BasefloError(
                    error_code="BF-JOB-003",
                    message=f"Unhandled job payload kind: {type(payload).__name__}",
                    status_code=500,
                )

        if not connector_ids:
            raise BasefloError(
                error_code="BF-JOB-005",
                message="No connected connectors found for project.",
                status_code=400,
            )

        async with open_session() as session:
            pipeline = BuildPipeline(
                session,
                conversation_id=payload.conversation_id,
            )
            request = BuildRequest(
                project_id=payload.project_id,
                connector_ids=connector_ids,
                business_description=business_description,
            )
            result = await pipeline.run(request)
    except GenerationCancelledError as exc:
        async with open_session() as session:
            repo = GenerationJobRepository(session)
            await repo.mark_cancelled(
                job_uuid,
                error={"error_code": exc.error_code, "message": exc.message},
            )
            job = await repo.get(job_uuid)
            job.completed_at = datetime.now(UTC)
        logger.info("generation_job_cancelled", job_id=str(job_uuid))
        await _emit_terminal_error(
            payload=payload,
            error_code=exc.error_code,
            message=exc.message,
        )
        return {
            "job_id": str(job_uuid),
            "status": JobStatus.CANCELLED.value,
        }
    except BasefloError as exc:
        async with open_session() as session:
            repo = GenerationJobRepository(session)
            await repo.update_status(
                job_uuid,
                status=JobStatus.FAILED,
                error={"error_code": exc.error_code, "message": exc.message},
            )
            job = await repo.get(job_uuid)
            job.completed_at = datetime.now(UTC)
        logger.exception("generation_job_failed", job_id=str(job_uuid), error_code=exc.error_code)
        await _emit_terminal_error(
            payload=payload,
            error_code=exc.error_code,
            message=exc.message,
        )
        raise
    except Exception as exc:
        async with open_session() as session:
            repo = GenerationJobRepository(session)
            await repo.update_status(
                job_uuid,
                status=JobStatus.FAILED,
                error={"error_code": "BF-JOB-002", "message": str(exc)},
            )
            job = await repo.get(job_uuid)
            job.completed_at = datetime.now(UTC)
        logger.exception("generation_job_unhandled_error", job_id=str(job_uuid))
        await _emit_terminal_error(
            payload=payload,
            error_code="BF-JOB-002",
            message=str(exc),
        )
        raise

    async with open_session() as session:
        repo = GenerationJobRepository(session)
        job = await repo.get(job_uuid)
        if job.status == JobStatus.CANCELLED.value:
            job.completed_at = datetime.now(UTC)
            return {
                "job_id": str(job_uuid),
                "status": JobStatus.CANCELLED.value,
            }
        await repo.update_status(job_uuid, status=JobStatus.SUCCEEDED)
        job = await repo.get(job_uuid)
        job.completed_at = datetime.now(UTC)

    return {
        "job_id": str(job_uuid),
        "status": JobStatus.SUCCEEDED.value,
        "saga_result": result,
    }


async def _emit_terminal_error(
    *,
    payload: JobPayload,
    error_code: str,
    message: str,
) -> None:
    """Surface failed background builds to the live SSE viewer."""
    if payload.conversation_id is None:
        return
    async with open_session() as session:
        await emit_event(
            session,
            conversation_id=payload.conversation_id,
            payload=ErrorPayload(
                type=EventType.ERROR_TERMINAL,
                error_code=error_code,
                message=message,
            ),
        )
