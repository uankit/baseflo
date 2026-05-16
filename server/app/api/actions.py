"""Action Plane v1 APIs."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.action_plane import (
    ActionList,
    ActionPrepareRequest,
    ActionRecord,
    ActionStatus,
    ActionType,
    SavedCohortList,
    complete_action,
    dismiss_action,
    load_action,
    load_actions,
    load_saved_cohorts,
    prepare_action,
)
from app.auth.dependencies import require_auth
from app.core.context import TenantCtx

router = APIRouter(tags=["actions"])


@router.get("", response_model=ActionList)
async def list_actions_endpoint(
    tenant: Annotated[TenantCtx, Depends(require_auth)],
    action_type: Annotated[ActionType | None, Query()] = None,
    status: Annotated[ActionStatus | None, Query()] = None,
    include_terminal: bool = False,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> ActionList:
    return ActionList(
        actions=await load_actions(
            tenant.organization_id,
            action_type=action_type,
            status=status,
            include_terminal=include_terminal,
            limit=limit,
        )
    )


@router.get("/cohorts", response_model=SavedCohortList)
async def list_saved_cohorts_endpoint(
    tenant: Annotated[TenantCtx, Depends(require_auth)],
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> SavedCohortList:
    return SavedCohortList(
        cohorts=await load_saved_cohorts(tenant.organization_id, limit=limit)
    )


@router.get("/{action_id}", response_model=ActionRecord)
async def get_action_endpoint(
    action_id: UUID,
    tenant: Annotated[TenantCtx, Depends(require_auth)],
) -> ActionRecord:
    return await load_action(tenant.organization_id, action_id=action_id)


@router.post("/{action_id}/prepare", response_model=ActionRecord)
async def prepare_action_endpoint(
    action_id: UUID,
    tenant: Annotated[TenantCtx, Depends(require_auth)],
    body: ActionPrepareRequest | None = None,
) -> ActionRecord:
    return await prepare_action(
        tenant.organization_id,
        action_id=action_id,
        request=body,
    )


@router.post("/{action_id}/complete", response_model=ActionRecord)
async def complete_action_endpoint(
    action_id: UUID,
    tenant: Annotated[TenantCtx, Depends(require_auth)],
) -> ActionRecord:
    return await complete_action(tenant.organization_id, action_id=action_id)


@router.post("/{action_id}/dismiss", response_model=ActionRecord)
async def dismiss_action_endpoint(
    action_id: UUID,
    tenant: Annotated[TenantCtx, Depends(require_auth)],
) -> ActionRecord:
    return await dismiss_action(tenant.organization_id, action_id=action_id)
