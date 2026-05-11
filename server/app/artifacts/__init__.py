"""Artifact-centric state management for Baseflo.

Artifacts are immutable, versioned, typed outputs produced by agents.
They form the shared contract between agents and the deterministic execution layer.
"""

from app.artifacts.types import (
    Artifact,
    ArtifactHeader,
    ArtifactProvenance,
    ArtifactStore,
    SourceMap,
    SourceTable,
    SourceColumn,
    EntityGraph,
    CanonicalEntity,
    EntitySourceMapping,
    SchemaIR,
    InsightBoard,
    KPIResult,
    SegmentResult,
    AnomalyResult,
    ExpectedRange,
    RecommendedAction,
    ActionPlan,
    ActionStep,
)

__all__ = [
    "Artifact",
    "ArtifactHeader",
    "ArtifactProvenance",
    "ArtifactStore",
    "SourceMap",
    "SourceTable",
    "SourceColumn",
    "EntityGraph",
    "CanonicalEntity",
    "EntitySourceMapping",
    "SchemaIR",
    "InsightBoard",
    "KPIResult",
    "SegmentResult",
    "AnomalyResult",
    "ExpectedRange",
    "RecommendedAction",
    "ActionPlan",
    "ActionStep",
]
