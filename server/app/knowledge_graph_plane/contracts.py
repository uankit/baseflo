"""Contracts for the Kuzu-backed Baseflo knowledge graph."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class KnowledgeGraphModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class KnowledgeGraphMaterialization(KnowledgeGraphModel):
    status: Literal["completed", "failed"]
    backend: Literal["kuzu"] = "kuzu"
    graph_path: str
    node_count: int = 0
    edge_count: int = 0
    query_examples: list[str] = Field(default_factory=list)
    error: str | None = None

    @property
    def path(self) -> Path:
        return Path(self.graph_path)
