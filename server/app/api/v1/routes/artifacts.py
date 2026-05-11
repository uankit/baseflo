"""Artifact API routes.

Expose the artifact store to the frontend for real-time workspace
visualization.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID  # noqa: TC003 - FastAPI resolves annotations at runtime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ValidationError

from app.artifacts import Artifact, ArtifactStore
from app.artifacts.types import EntityGraph, InsightBoard, SourceMap
from app.auth.dependencies import require_tenant
from app.core.context import TenantCtx  # noqa: TC001 - FastAPI resolves annotations
from app.core.errors import BasefloError
from app.db.session import open_session
from app.engines.schema.ir import SchemaIR

router = APIRouter(prefix="/projects", tags=["artifacts"])
REQUIRE_TENANT = Depends(require_tenant)


@router.get("/{project_id}/artifacts")
async def list_artifacts(
    project_id: UUID,
    tenant: TenantCtx = REQUIRE_TENANT,
) -> dict[str, Any]:
    """List all artifact headers for a project."""
    async with open_session() as session:
        store = ArtifactStore(session)
        headers = await store.list_headers(project_id)
        return {
            "artifacts": [
                {
                    "artifactId": str(h.artifact_id),
                    "projectId": str(h.project_id),
                    "artifactType": h.artifact_type,
                    "version": h.version,
                    "producedBy": h.produced_by,
                    "createdAt": h.created_at.isoformat(),
                }
                for h in headers
            ],
        }


@router.get("/{project_id}/artifacts/latest")
async def get_latest_artifact(
    project_id: UUID,
    artifact_type: str = Query(
        ...,
        description="e.g. source_map, entity_graph, schema_ir, insight_board",
    ),
    tenant: TenantCtx = REQUIRE_TENANT,
) -> dict[str, Any]:
    """Get the latest artifact of a specific type for a project."""
    type_map: dict[str, type[BaseModel]] = {
        "source_map": SourceMap,
        "entity_graph": EntityGraph,
        "schema_ir": SchemaIR,
        "insight_board": InsightBoard,
    }

    payload_cls = type_map.get(artifact_type)
    if payload_cls is None:
        raise BasefloError(
            error_code="BF-API-010",
            message=f"Unknown artifact type: {artifact_type!r}",
            status_code=400,
        )

    async with open_session() as session:
        store = ArtifactStore(session)
        artifact: Artifact[BaseModel] | None
        try:
            artifact = await store.get_latest(project_id, artifact_type, payload_cls)
            payload = artifact.payload if artifact is not None else None
        except ValidationError:
            legacy_payload_cls = _legacy_payload_type(artifact_type)
            if legacy_payload_cls is None:
                raise
            artifact = await store.get_latest(project_id, artifact_type, legacy_payload_cls)
            payload = (
                _unwrap_legacy_payload(artifact_type, artifact.payload)
                if artifact is not None
                else None
            )
        if artifact is None:
            raise BasefloError(
                error_code="BF-API-011",
                message=f"No artifact of type {artifact_type!r} found for project {project_id}.",
                status_code=404,
            )

        dumped_payload = (
            payload.model_dump(mode="json") if isinstance(payload, BaseModel) else payload
        )
        return {
            "artifactId": str(artifact.header.artifact_id),
            "projectId": str(artifact.header.project_id),
            "artifactType": artifact.header.artifact_type,
            "version": artifact.header.version,
            "producedBy": artifact.header.produced_by,
            "createdAt": artifact.header.created_at.isoformat(),
            "payload": dumped_payload,
            "provenance": {
                "agentName": artifact.provenance.agent_name,
                "modelName": artifact.provenance.model_name,
                "tokensPrompt": artifact.provenance.tokens_prompt,
                "tokensCompletion": artifact.provenance.tokens_completion,
                "latencyMs": artifact.provenance.latency_ms,
                "startedAt": artifact.provenance.started_at.isoformat(),
                "finishedAt": artifact.provenance.finished_at.isoformat(),
            },
        }


def _legacy_payload_type(artifact_type: str) -> type[BaseModel] | None:
    """Return wrapper payload classes used by older pipeline artifacts."""
    from app.agents.insight_agent.types import InsightAgentOutput
    from app.agents.reconciliation_agent.types import ReconciliationAgentOutput
    from app.agents.schema_agent.types import SchemaAgentOutput
    from app.agents.source_agent.types import SourceAgentOutput

    legacy_map: dict[str, type[BaseModel]] = {
        "source_map": SourceAgentOutput,
        "entity_graph": ReconciliationAgentOutput,
        "schema_ir": SchemaAgentOutput,
        "insight_board": InsightAgentOutput,
    }
    return legacy_map.get(artifact_type)


def _unwrap_legacy_payload(artifact_type: str, payload: BaseModel) -> BaseModel:
    from app.agents.insight_agent.types import InsightAgentOutput
    from app.agents.reconciliation_agent.types import ReconciliationAgentOutput
    from app.agents.schema_agent.types import SchemaAgentOutput
    from app.agents.source_agent.types import SourceAgentOutput

    if isinstance(payload, SourceAgentOutput):
        return payload.source_map
    if isinstance(payload, ReconciliationAgentOutput):
        return payload.entity_graph
    if isinstance(payload, SchemaAgentOutput):
        return payload.schema_ir
    if isinstance(payload, InsightAgentOutput):
        return payload.insight_board
    raise BasefloError(
        error_code="BF-API-012",
        message=f"Artifact type {artifact_type!r} used an unknown legacy payload shape.",
        status_code=500,
    )
