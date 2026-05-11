"""SourceAgent input/output types."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.artifacts.types import SourceMap


class SourceAgentInput(BaseModel):
    """Input for the SourceAgent."""

    model_config = ConfigDict(extra="forbid")

    connector_id: str
    connector_kind: str
    business_description: str
    raw_schema: dict  # tables, columns, sample rows from connector.introspect_schema
    sample_rows: list[dict] = Field(default_factory=list)


class SourceAgentOutput(BaseModel):
    """Output for the SourceAgent — produces a SourceMap artifact."""

    model_config = ConfigDict(extra="forbid")

    source_map: SourceMap
    assumptions: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0, default=0.9)
