"""Event ingestion endpoint.

POST /api/v1/projects/{project_id}/events — ingest a batch of behavioral
events. Validates each event against the project's current taxonomy;
returns a typed report of accepted + rejected.

The hosted SDK posts here; webhook adapters can use the same shape by setting
`source=webhook` on the service call.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field

from app.auth.dependencies import require_tenant
from app.core.context import TenantCtx
from app.observability.logging import get_logger
from app.services.events import (
    EventIngestionInput,
    EventIngestionService,
)


router = APIRouter(prefix="/projects", tags=["events"])
logger = get_logger("api.events")


# ---------- Request / response ----------


class IngestEventsRequest(BaseModel):
    events: list[EventIngestionInput] = Field(min_length=1, max_length=500)


class RejectedEventResponse(BaseModel):
    index: int
    name: str
    reason: str


class IngestEventsResponse(BaseModel):
    accepted: int
    persisted: int
    rejected: list[RejectedEventResponse] = Field(default_factory=list)


# ---------- DI ----------


def _ingestion_service() -> EventIngestionService:
    return EventIngestionService()


# ---------- Routes ----------


@router.post(
    "/{project_id}/events",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=IngestEventsResponse,
    summary="Ingest a batch of behavioral events for a project",
)
async def ingest_events(
    project_id: UUID,
    body: IngestEventsRequest,
    tenant: Annotated[TenantCtx, Depends(require_tenant)],
    service: Annotated[EventIngestionService, Depends(_ingestion_service)],
) -> IngestEventsResponse:
    result = await service.ingest(
        tenant=tenant, project_id=project_id, events=body.events,
    )
    return IngestEventsResponse(
        accepted=result.accepted,
        persisted=result.persisted,
        rejected=[
            RejectedEventResponse(index=r.index, name=r.name, reason=r.reason)
            for r in result.rejected
        ],
    )
