"""Typed job models for the arq queue.

Per docs/40-features/JOBS-AND-SSE.md §3.2, every job carries an idempotency
key and a typed payload discriminated by `kind`.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

# `JobKind` and `JobStatus` are persisted enums whose values back the
# `generation_jobs.kind` / `.status` CHECK constraints. The DB model is the
# canonical source of truth; we re-export here so the orchestration layer
# doesn't have a hard import on the DB layer.
from app.db.models.generation import JobKind, JobStatus

__all__ = [
    "JobKind",
    "JobStatus",
    "InitialPayload",
    "JobAccepted",
    "JobPayload",
    "JobRequest",
    "RefinementPayload",
]


# ---------- Per-kind payloads ----------


class _BasePayload(BaseModel):
    project_id: UUID
    organization_id: UUID
    conversation_id: UUID | None = None


class InitialPayload(_BasePayload):
    kind: Literal[JobKind.INITIAL] = JobKind.INITIAL
    description: str = Field(min_length=3, max_length=4000)
    connector_ids: list[UUID] = Field(default_factory=list)
    """Snapshot of connected connectors at enqueue time."""


class RefinementPayload(_BasePayload):
    kind: Literal[JobKind.REFINEMENT] = JobKind.REFINEMENT
    refinement_id: UUID
    parent_version_id: UUID


class ConnectorAddedPayload(_BasePayload):
    kind: Literal[JobKind.CONNECTOR_ADDED] = JobKind.CONNECTOR_ADDED
    connector_id: UUID


class ReIntrospectPayload(_BasePayload):
    kind: Literal[JobKind.RE_INTROSPECT] = JobKind.RE_INTROSPECT
    connector_id: UUID


JobPayload = Annotated[
    InitialPayload | RefinementPayload | ConnectorAddedPayload | ReIntrospectPayload,
    Field(discriminator="kind"),
]


# ---------- Job request from API → queue ----------


class JobRequest(BaseModel):
    """Submission record carried through enqueue → arq → worker.

    `idempotency_key` is required and provided by the caller. Same key + same
    payload returns the existing job; same key + different payload raises
    `BF-JOB-001` per docs/40-features/JOBS-AND-SSE.md §3.2.
    """

    idempotency_key: str = Field(min_length=8, max_length=120)
    payload: JobPayload


class JobAccepted(BaseModel):
    """Returned from enqueue — what the API hands back to the client."""

    job_id: UUID
    conversation_id: UUID | None
    status: JobStatus
    sse_url: str | None = None


# ---------- Worker-side context handed to task functions ----------


class WorkerJobContext(BaseModel):
    """The state arq tasks receive (typed wrapper around what the worker materialises)."""

    job_id: UUID
    payload: JobPayload
    attempt: int = 1
    extra: dict[str, Any] = Field(default_factory=dict)
