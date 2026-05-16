"""Contracts for durable Baseflo product artifacts."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

ArtifactKind = Literal[
    "brief",
    "business_view",
    "business_surfaces",
    "entity_resolution",
    "knowledge_graph",
    "semantic_layer",
    "chart_grammar",
    "insight_ranking",
    "insight",
    "inbox_item",
    "ask_answer",
    "chart",
    "table",
    "narrative",
    "audience",
    "lineage",
    "action",
    "run_summary",
]
ArtifactStatus = Literal["new", "seen", "snoozed", "dismissed", "resolved"]


class ArtifactModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ArtifactDraft(ArtifactModel):
    artifact_key: str
    kind: ArtifactKind
    title: str
    summary: str = ""
    why: str = ""
    tags: list[str] = Field(default_factory=list)
    priority: float = Field(default=0.5, ge=0, le=1)
    source_refs: dict[str, Any] = Field(default_factory=dict)
    payload: dict[str, Any] = Field(default_factory=dict)


class ArtifactRecord(ArtifactModel):
    id: UUID
    organization_id: UUID
    run_id: UUID | None = None
    artifact_key: str
    kind: ArtifactKind
    status: ArtifactStatus
    title: str
    summary: str
    why: str
    tags: list[str] = Field(default_factory=list)
    priority: float = Field(ge=0, le=1)
    source_refs: dict[str, Any] = Field(default_factory=dict)
    payload: dict[str, Any] = Field(default_factory=dict)
    fingerprint: str
    first_seen_at: datetime
    last_seen_at: datetime
    snoozed_until: datetime | None = None
    dismissed_at: datetime | None = None
    resolved_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class ArtifactPlaneRunResult(ArtifactModel):
    organization_id: UUID
    run_id: UUID
    artifacts: list[ArtifactRecord] = Field(default_factory=list)
    brief_artifact_id: UUID | None = None
    business_view_artifact_id: UUID | None = None
    business_surfaces_artifact_id: UUID | None = None
    entity_resolution_artifact_id: UUID | None = None
    knowledge_graph_artifact_id: UUID | None = None
    semantic_layer_artifact_id: UUID | None = None
    chart_grammar_artifact_id: UUID | None = None
    insight_ranking_artifact_id: UUID | None = None
    lineage_artifact_id: UUID | None = None
    inbox_item_ids: list[UUID] = Field(default_factory=list)
    ask_artifact_ids: list[UUID] = Field(default_factory=list)
    action_artifact_ids: list[UUID] = Field(default_factory=list)
    created_count: int = 0
    updated_count: int = 0
    unchanged_count: int = 0


class ArtifactList(ArtifactModel):
    artifacts: list[ArtifactRecord] = Field(default_factory=list)


class ArtifactStatusUpdate(ArtifactModel):
    status: ArtifactStatus
    snoozed_until: datetime | None = None
