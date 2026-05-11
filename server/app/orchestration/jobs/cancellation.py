"""Cooperative cancellation checks for generation jobs."""

from __future__ import annotations

from uuid import UUID  # noqa: TC003

from app.core.errors import BasefloError
from app.db.models.generation import JobStatus
from app.db.session import open_session
from app.repositories.jobs import GenerationJobRepository


class GenerationCancelledError(BasefloError):
    """Raised when a queued or running generation has been cancelled."""

    def __init__(self, *, job_id: UUID) -> None:
        super().__init__(
            error_code="BF-JOB-003",
            message="Build cancelled.",
            status_code=409,
            details={"job_id": str(job_id)},
        )


async def ensure_job_not_cancelled(job_id: UUID) -> None:
    """Abort the graph at the next node boundary after a user cancellation."""
    async with open_session() as session:
        job = await GenerationJobRepository(session).get(job_id)
        if job.status == JobStatus.CANCELLED.value:
            raise GenerationCancelledError(job_id=job_id)
