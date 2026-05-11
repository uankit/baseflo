"""Refinement endpoint — POST /api/v1/projects/{id}/refinements.

Per docs/40-features/AGENT-COHE.md §3.6. The request is the user's
plain-English refinement text; the response is either a clarification
question or the new project_version_id + diff_summary the user can
confirm + apply.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, ConfigDict, Field

from app.auth.dependencies import require_tenant
from app.core.context import TenantCtx
from app.observability.logging import get_logger
from app.orchestration.sagas.refinement import RefinementResult, RefinementSaga


router = APIRouter(prefix="/projects", tags=["refinements"])
logger = get_logger("api.refinements")


class RefinementRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request: str = Field(min_length=2, max_length=2000)


@router.post(
    "/{project_id}/refinements",
    status_code=status.HTTP_200_OK,
    response_model=RefinementResult,
    summary="Run a natural-language refinement against the project",
)
async def post_refinement(
    project_id: UUID,
    body: RefinementRequest,
    tenant: Annotated[TenantCtx, Depends(require_tenant)],
) -> RefinementResult:
    saga = RefinementSaga()
    result = await saga.run(
        project_id=project_id,
        organization_id=tenant.organization_id,
        request=body.request,
    )
    logger.info(
        "refinement_completed",
        project_id=str(project_id),
        new_version_id=str(result.new_version_id) if result.new_version_id else None,
        clarification_needed=result.is_clarification_needed,
    )
    return result
