"""Artifact Plane service.

The Artifact Plane turns operating run output into stable product artifacts.
It is deterministic: no agent calls happen here, and no UI component knowledge
leaks into the backend.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from app.artifact_plane.assembler import assemble_operating_artifacts
from app.artifact_plane.contracts import ArtifactPlaneRunResult
from app.artifact_plane.store import upsert_artifacts


async def materialize_operating_artifacts(
    organization_id: UUID,
    *,
    run: Any,
) -> ArtifactPlaneRunResult:
    drafts = assemble_operating_artifacts(run)
    return await upsert_artifacts(
        organization_id,
        run_id=run.run_id,
        drafts=drafts,
    )
