"""Autonomous business-memory service."""

from __future__ import annotations

from uuid import UUID

from app.agent_plane.contracts import (
    AssetRole,
    BusinessGraph,
    BusinessModel,
    FieldRole,
    PatternBatch,
)
from app.memory_plane.candidates import candidates_from_agent_artifacts
from app.memory_plane.contracts import MemoryPlaneRunResult
from app.memory_plane.store import upsert_memory_candidates


async def remember_agent_artifacts(
    organization_id: UUID,
    *,
    business_model: BusinessModel,
    asset_roles: list[AssetRole],
    field_roles: list[FieldRole],
    business_graph: BusinessGraph,
    patterns: PatternBatch | None = None,
) -> MemoryPlaneRunResult:
    """Autonomously persist stable business semantics from one operating run."""
    candidates = candidates_from_agent_artifacts(
        business_model=business_model,
        asset_roles=asset_roles,
        field_roles=field_roles,
        business_graph=business_graph,
        patterns=patterns,
    )
    writes = await upsert_memory_candidates(organization_id, candidates)
    return MemoryPlaneRunResult(candidates=candidates, writes=writes)
