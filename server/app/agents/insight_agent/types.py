"""InsightAgent input/output types."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.artifacts.types import InsightBoard


class InsightAgentInput(BaseModel):
    """Input for the InsightAgent."""

    model_config = ConfigDict(extra="forbid")

    business_description: str
    schema_ir: dict  # serialized SchemaIR artifact
    entity_graph: dict | None = None  # optional serialized EntityGraph
    question: str | None = None  # user question; if None, generate default KPIs


class InsightAgentOutput(BaseModel):
    """Output for the InsightAgent — produces an InsightBoard artifact."""

    model_config = ConfigDict(extra="forbid")

    insight_board: InsightBoard
    confidence: float = Field(ge=0.0, le=1.0, default=0.85)
