"""ReconciliationAgent input/output types."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.artifacts.types import EntityGraph


class ReconciliationAgentInput(BaseModel):
    """Input for the ReconciliationAgent."""

    model_config = ConfigDict(extra="forbid")

    business_description: str
    source_maps: list[dict]  # serialized SourceMap artifacts


class ReconciliationAgentOutput(BaseModel):
    """Output for the ReconciliationAgent — produces an EntityGraph artifact."""

    model_config = ConfigDict(extra="forbid")

    entity_graph: EntityGraph
    confidence: float = Field(ge=0.0, le=1.0, default=0.85)
