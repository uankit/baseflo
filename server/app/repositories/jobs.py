"""GenerationJob repository — idempotency-aware enqueue."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, NotFoundError
from app.db.models.generation import GenerationJob, JobStatus


class GenerationJobRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, job_id: UUID) -> GenerationJob:
        result = await self._session.get(GenerationJob, job_id)
        if result is None:
            raise NotFoundError(
                message=f"Job {job_id} not found.",
                error_code="BF-API-001",
                details={"job_id": str(job_id)},
            )
        return result

    async def get_by_idempotency_key(self, key: str) -> GenerationJob | None:
        stmt = select(GenerationJob).where(GenerationJob.idempotency_key == key)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def get_by_conversation(self, conversation_id: UUID) -> GenerationJob | None:
        stmt = (
            select(GenerationJob)
            .where(GenerationJob.conversation_id == conversation_id)
            .order_by(GenerationJob.created_at.desc())
            .limit(1)
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def create_or_get_idempotent(
        self,
        *,
        job: GenerationJob,
        payload_fingerprint: str,
    ) -> tuple[GenerationJob, bool]:
        """Insert the job; if the idempotency key already exists, compare
        payload fingerprints and either return the existing job or raise.

        Returns (job, created) where `created` is True for fresh inserts.
        """
        existing = await self.get_by_idempotency_key(job.idempotency_key)
        if existing is not None:
            existing_fp = (existing.error or {}).get("_idempotency_fingerprint")
            if existing_fp != payload_fingerprint:
                raise ConflictError(
                    message=(
                        "Idempotency key reused with a different payload. "
                        "See docs/40-features/JOBS-AND-SSE.md §3.2."
                    ),
                    error_code="BF-JOB-001",
                    details={
                        "idempotency_key": job.idempotency_key,
                        "existing_job_id": str(existing.id),
                    },
                )
            return existing, False

        # Stash the fingerprint inside the `error` JSONB; it's a benign
        # piggy-back. A dedicated column would be cleaner but requires a new
        # migration; M0 takes the slim path. Tracked as v1 polish.
        job.error = {"_idempotency_fingerprint": payload_fingerprint}
        self._session.add(job)
        await self._session.flush()
        return job, True

    async def update_status(
        self,
        job_id: UUID,
        *,
        status: JobStatus,
        error: dict[str, Any] | None = None,
    ) -> GenerationJob:
        job = await self.get(job_id)
        job.status = status.value
        if error is not None:
            existing = job.error or {}
            existing.update({k: v for k, v in error.items() if k != "_idempotency_fingerprint"})
            job.error = existing
        await self._session.flush()
        return job

    async def mark_cancelled(
        self,
        job_id: UUID,
        *,
        error: dict[str, Any] | None = None,
    ) -> GenerationJob:
        return await self.update_status(
            job_id,
            status=JobStatus.CANCELLED,
            error=error
            or {
                "error_code": "BF-JOB-003",
                "message": "Build cancelled.",
            },
        )
