"""Adaptive operating intelligence routes."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from app.auth.dependencies import require_auth
from app.core.context import TenantCtx
from app.intelligence import (
    OperatingBrief,
    RememberInput,
    approve_action,
    dismiss_insight,
    read_operating_brief,
    rebuild_operating_intelligence,
    remember,
    scan_operating_intelligence,
)

router = APIRouter(tags=["operating"])


@router.get("/brief", response_model=OperatingBrief)
async def get_operating_brief(
    tenant: Annotated[TenantCtx, Depends(require_auth)],
) -> OperatingBrief:
    return await read_operating_brief(tenant)


@router.post("/rebuild", response_model=OperatingBrief)
async def rebuild_operating_brief(
    tenant: Annotated[TenantCtx, Depends(require_auth)],
) -> OperatingBrief:
    return await rebuild_operating_intelligence(tenant)


@router.post("/scan", response_model=OperatingBrief)
async def scan_operating_brief(
    tenant: Annotated[TenantCtx, Depends(require_auth)],
) -> OperatingBrief:
    return await scan_operating_intelligence(tenant)


@router.post("/memory")
async def remember_business_context(
    body: RememberInput,
    tenant: Annotated[TenantCtx, Depends(require_auth)],
) -> dict[str, object]:
    return await remember(tenant, body)


@router.post("/insights/{insight_id}/dismiss")
async def dismiss_operating_insight(
    insight_id: UUID,
    tenant: Annotated[TenantCtx, Depends(require_auth)],
) -> dict[str, bool]:
    return await dismiss_insight(tenant, insight_id)


@router.post("/actions/{action_id}/approve")
async def approve_operating_action(
    action_id: UUID,
    tenant: Annotated[TenantCtx, Depends(require_auth)],
) -> dict[str, bool]:
    return await approve_action(tenant, action_id)
