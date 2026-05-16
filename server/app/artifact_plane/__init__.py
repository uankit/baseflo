"""Durable Baseflo artifact read model."""

from app.artifact_plane.assembler import artifact_fingerprint, assemble_operating_artifacts
from app.artifact_plane.contracts import (
    ArtifactDraft,
    ArtifactKind,
    ArtifactList,
    ArtifactPlaneRunResult,
    ArtifactRecord,
    ArtifactStatus,
    ArtifactStatusUpdate,
)
from app.artifact_plane.service import materialize_operating_artifacts
from app.artifact_plane.store import (
    latest_artifact,
    load_artifacts,
    load_run_artifacts,
    update_artifact_status,
    upsert_artifacts,
)

__all__ = [
    "ArtifactDraft",
    "ArtifactKind",
    "ArtifactList",
    "ArtifactPlaneRunResult",
    "ArtifactRecord",
    "ArtifactStatus",
    "ArtifactStatusUpdate",
    "assemble_operating_artifacts",
    "artifact_fingerprint",
    "latest_artifact",
    "load_artifacts",
    "load_run_artifacts",
    "materialize_operating_artifacts",
    "update_artifact_status",
    "upsert_artifacts",
]
