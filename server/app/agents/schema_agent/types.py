"""SchemaAgent input/output types."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from app.engines.schema.ir import SchemaIR


class SchemaAgentInput(BaseModel):
    """Input for the SchemaAgent."""

    model_config = ConfigDict(extra="forbid")

    business_description: str
    entity_graph: dict  # serialized EntityGraph artifact


class SchemaAgentOutput(BaseModel):
    """Output for the SchemaAgent — produces a SchemaIR artifact."""

    model_config = ConfigDict(extra="forbid")

    schema_ir: SchemaIR
    assumptions: list[str]
