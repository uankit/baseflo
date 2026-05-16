"""Artifact Plane read APIs."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.artifact_plane import (
    ArtifactKind,
    ArtifactList,
    ArtifactRecord,
    ArtifactStatus,
    ArtifactStatusUpdate,
    latest_artifact,
    load_artifacts,
    load_run_artifacts,
    update_artifact_status,
)
from app.auth.dependencies import require_auth
from app.core.context import TenantCtx
from app.core.errors import NotFoundError

router = APIRouter(tags=["artifacts"])


async def _latest_required(
    tenant: TenantCtx,
    *,
    kind: ArtifactKind,
    label: str,
    code: str,
) -> ArtifactRecord:
    artifact = await latest_artifact(tenant.organization_id, kind=kind)
    if artifact is None:
        raise NotFoundError(
            message=f"No {label} artifact exists yet",
            code=code,
            status_hint=404,
        )
    return artifact


@router.get("", response_model=ArtifactList)
async def list_artifacts_endpoint(
    tenant: Annotated[TenantCtx, Depends(require_auth)],
    kind: Annotated[ArtifactKind | None, Query()] = None,
    status: Annotated[ArtifactStatus | None, Query()] = None,
    include_terminal: bool = False,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> ArtifactList:
    return ArtifactList(
        artifacts=await load_artifacts(
            tenant.organization_id,
            kind=kind,
            status=status,
            include_terminal=include_terminal,
            limit=limit,
        )
    )


@router.get("/brief", response_model=ArtifactRecord)
async def latest_brief_artifact_endpoint(
    tenant: Annotated[TenantCtx, Depends(require_auth)],
) -> ArtifactRecord:
    return await _latest_required(
        tenant,
        kind="brief",
        label="brief",
        code="ARTIFACT_BRIEF_NOT_FOUND",
    )


@router.get("/business-view", response_model=ArtifactRecord)
async def latest_business_view_artifact_endpoint(
    tenant: Annotated[TenantCtx, Depends(require_auth)],
) -> ArtifactRecord:
    return await _latest_required(
        tenant,
        kind="business_view",
        label="business view",
        code="ARTIFACT_BUSINESS_VIEW_NOT_FOUND",
    )


@router.get("/business-surfaces", response_model=ArtifactRecord)
async def latest_business_surfaces_artifact_endpoint(
    tenant: Annotated[TenantCtx, Depends(require_auth)],
) -> ArtifactRecord:
    return await _latest_required(
        tenant,
        kind="business_surfaces",
        label="business surfaces",
        code="ARTIFACT_BUSINESS_SURFACES_NOT_FOUND",
    )


@router.get("/semantic-layer", response_model=ArtifactRecord)
async def latest_semantic_layer_artifact_endpoint(
    tenant: Annotated[TenantCtx, Depends(require_auth)],
) -> ArtifactRecord:
    return await _latest_required(
        tenant,
        kind="semantic_layer",
        label="semantic layer",
        code="ARTIFACT_SEMANTIC_LAYER_NOT_FOUND",
    )


@router.get("/chart-grammar", response_model=ArtifactRecord)
async def latest_chart_grammar_artifact_endpoint(
    tenant: Annotated[TenantCtx, Depends(require_auth)],
) -> ArtifactRecord:
    return await _latest_required(
        tenant,
        kind="chart_grammar",
        label="chart grammar",
        code="ARTIFACT_CHART_GRAMMAR_NOT_FOUND",
    )


@router.get("/insight-ranking", response_model=ArtifactRecord)
async def latest_insight_ranking_artifact_endpoint(
    tenant: Annotated[TenantCtx, Depends(require_auth)],
) -> ArtifactRecord:
    return await _latest_required(
        tenant,
        kind="insight_ranking",
        label="insight ranking",
        code="ARTIFACT_INSIGHT_RANKING_NOT_FOUND",
    )


@router.get("/entity-resolution", response_model=ArtifactRecord)
async def latest_entity_resolution_artifact_endpoint(
    tenant: Annotated[TenantCtx, Depends(require_auth)],
) -> ArtifactRecord:
    return await _latest_required(
        tenant,
        kind="entity_resolution",
        label="entity resolution",
        code="ARTIFACT_ENTITY_RESOLUTION_NOT_FOUND",
    )


@router.get("/knowledge-graph", response_model=ArtifactRecord)
async def latest_knowledge_graph_artifact_endpoint(
    tenant: Annotated[TenantCtx, Depends(require_auth)],
) -> ArtifactRecord:
    return await _latest_required(
        tenant,
        kind="knowledge_graph",
        label="knowledge graph",
        code="ARTIFACT_KNOWLEDGE_GRAPH_NOT_FOUND",
    )


@router.get("/lineage", response_model=ArtifactRecord)
async def latest_lineage_artifact_endpoint(
    tenant: Annotated[TenantCtx, Depends(require_auth)],
) -> ArtifactRecord:
    return await _latest_required(
        tenant,
        kind="lineage",
        label="lineage",
        code="ARTIFACT_LINEAGE_NOT_FOUND",
    )


@router.get("/inbox", response_model=ArtifactList)
async def inbox_artifacts_endpoint(
    tenant: Annotated[TenantCtx, Depends(require_auth)],
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> ArtifactList:
    return ArtifactList(
        artifacts=await load_artifacts(
            tenant.organization_id,
            kind="inbox_item",
            limit=limit,
        )
    )


@router.get("/runs/{run_id}", response_model=ArtifactList)
async def run_artifacts_endpoint(
    run_id: UUID,
    tenant: Annotated[TenantCtx, Depends(require_auth)],
) -> ArtifactList:
    return ArtifactList(
        artifacts=await load_run_artifacts(tenant.organization_id, run_id=run_id)
    )


@router.patch("/{artifact_id}/status", response_model=ArtifactRecord)
async def update_artifact_status_endpoint(
    artifact_id: UUID,
    body: ArtifactStatusUpdate,
    tenant: Annotated[TenantCtx, Depends(require_auth)],
) -> ArtifactRecord:
    return await update_artifact_status(
        tenant.organization_id,
        artifact_id=artifact_id,
        status=body.status,
        snoozed_until=body.snoozed_until,
    )
