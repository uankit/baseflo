"""Packaged operating pipeline routes."""

from __future__ import annotations

import asyncio
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, status
from fastapi.responses import StreamingResponse

from app.auth.dependencies import require_auth
from app.communication import RunAccepted, RunState, run_event_bus, sse_response
from app.core.context import TenantCtx
from app.core.errors import ConflictError
from app.operating_pipeline import (
    OperatingRunRequest,
    OperatingRunResult,
    run_operating_pipeline,
)

router = APIRouter(tags=["operating"])


@router.post("/runs", response_model=RunAccepted, status_code=status.HTTP_202_ACCEPTED)
async def start_operating_run_endpoint(
    body: OperatingRunRequest,
    tenant: Annotated[TenantCtx, Depends(require_auth)],
) -> RunAccepted:
    run = await run_event_bus.create_run(
        organization_id=tenant.organization_id,
        kind="operating",
        request=body.model_dump(mode="json"),
    )
    asyncio.create_task(_execute_operating_run(run.run_id, tenant.organization_id, body))
    return RunAccepted(
        run_id=run.run_id,
        kind=run.kind,
        status=run.status,
        result_url=f"/api/v1/operating/runs/{run.run_id}/result",
        events_url=f"/api/v1/operating/runs/{run.run_id}/events",
    )


@router.get("/runs/{run_id}", response_model=RunState)
async def get_operating_run_state_endpoint(
    run_id: UUID,
    tenant: Annotated[TenantCtx, Depends(require_auth)],
) -> RunState:
    run = await run_event_bus.get_run(run_id, organization_id=tenant.organization_id)
    events = await run_event_bus.list_events(run_id, organization_id=tenant.organization_id)
    return RunState(run=run, events=events)


@router.get("/runs/{run_id}/result", response_model=OperatingRunResult)
async def get_operating_run_result_endpoint(
    run_id: UUID,
    tenant: Annotated[TenantCtx, Depends(require_auth)],
) -> OperatingRunResult:
    run = await run_event_bus.get_run(run_id, organization_id=tenant.organization_id)
    if run.result is None:
        raise ConflictError(
            message=f"Run is {run.status}; result is not ready",
            code="RUN_RESULT_NOT_READY",
            status_hint=409,
        )
    return OperatingRunResult.model_validate(run.result)


@router.get("/runs/{run_id}/events", response_class=StreamingResponse)
async def stream_operating_run_events_endpoint(
    run_id: UUID,
    tenant: Annotated[TenantCtx, Depends(require_auth)],
) -> StreamingResponse:
    return sse_response(
        run_event_bus.stream_events(run_id, organization_id=tenant.organization_id)
    )


async def _execute_operating_run(
    run_id: UUID,
    organization_id: UUID,
    body: OperatingRunRequest,
) -> None:
    await run_event_bus.mark_running(run_id, organization_id=organization_id)

    async def publish(
        *,
        type: str,
        stage: str,
        message: str,
        progress: float | None = None,
        payload: dict[str, Any] | None = None,
    ) -> None:
        await run_event_bus.publish(
            run_id,
            organization_id=organization_id,
            type=type,
            stage=stage,
            message=message,
            progress=progress,
            payload=payload,
        )

    try:
        result = await run_operating_pipeline(
            organization_id,
            body,
            event_publisher=publish,
        )
        result = result.model_copy(update={"run_id": run_id})
        await run_event_bus.complete_run(
            run_id,
            organization_id=organization_id,
            status=result.status,
            result=result.model_dump(mode="json"),
        )
    except Exception as exc:
        await run_event_bus.complete_run(
            run_id,
            organization_id=organization_id,
            status="failed",
            error={"message": str(exc), "type": type(exc).__name__},
        )
