"""Entity Resolution Plane public API."""

from app.entity_resolution_plane.contracts import (
    EntityCluster,
    EntityMatch,
    EntityResolutionDataset,
    EntityResolutionExecution,
    EntityResolutionField,
    EntityResolutionPlan,
    EntityResolutionRunResult,
)
from app.entity_resolution_plane.service import (
    execute_entity_resolution,
    plan_entity_resolution_from_surfaces,
    run_entity_resolution_from_surfaces,
)
from app.entity_resolution_plane.splink_engine import (
    SplinkDependencyError,
    SplinkEntityResolutionEngine,
)

__all__ = [
    "EntityCluster",
    "EntityMatch",
    "EntityResolutionDataset",
    "EntityResolutionExecution",
    "EntityResolutionField",
    "EntityResolutionPlan",
    "EntityResolutionRunResult",
    "SplinkDependencyError",
    "SplinkEntityResolutionEngine",
    "execute_entity_resolution",
    "plan_entity_resolution_from_surfaces",
    "run_entity_resolution_from_surfaces",
]
