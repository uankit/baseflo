"""Contracts for Baseflo's end-to-end operating orchestration.

The pipeline is the product-facing run envelope. It coordinates independent
planes, but does not own their internals:

- Data Profiler refreshes deterministic evidence.
- Agent Plane creates semantic plans and result-side artifacts.
- Execution Plane validates and materializes plans.

The output is intentionally one typed result object so Brief, Inbox, Ask, and
debug surfaces can render the same grounded run without scraping logs.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.action_plane.contracts import ActionPlaneRunResult
from app.agent_plane.contracts import (
    ActionBatch,
    AssetRole,
    BriefPackage,
    BusinessGraph,
    BusinessModel,
    ChartSpec,
    FieldRole,
    Interpretation,
    NarrativeSpec,
    PatternBatch,
)
from app.analysis_contracts import AnalysisGraphPlan, AnalysisResultRef
from app.artifact_plane.contracts import ArtifactPlaneRunResult
from app.business_surface_plane.contracts import BusinessSurfacePackage
from app.business_view_plane.contracts import BusinessViewPackage
from app.chart_grammar_plane.contracts import ChartGrammarPackage
from app.data_profiler.contracts import ProfilerRunResult
from app.entity_resolution_plane.contracts import EntityResolutionRunResult
from app.insight_ranking_plane.contracts import InsightRankingPackage
from app.knowledge_graph_plane.contracts import KnowledgeGraphMaterialization
from app.lineage_plane.contracts import LineagePackage
from app.memory_plane.contracts import MemoryWriteResult
from app.semantic_layer.contracts import SemanticLayerPackage

OperatingRunMode = Literal["scan", "ask"]
OperatingRunStatus = Literal["completed", "partial", "failed"]


class OperatingPipelineModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class OperatingRunRequest(OperatingPipelineModel):
    mode: OperatingRunMode = "scan"
    question: str | None = None
    snapshot_ids: list[UUID] | None = None
    refresh_profile: bool = True
    max_preview_rows: int = Field(default=50, ge=1, le=500)
    max_parallel_plans: int = Field(default=3, ge=1, le=10)

    @model_validator(mode="after")
    def _ask_requires_question(self) -> OperatingRunRequest:
        if self.mode == "ask" and not (self.question or "").strip():
            raise ValueError("ask mode requires a question")
        return self


class OperatingContextSummary(OperatingPipelineModel):
    snapshot_count: int = 0
    asset_count: int = 0
    field_count: int = 0
    graph_edge_count: int = 0
    row_count: int = 0


class OperatingRunError(OperatingPipelineModel):
    stage: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class PlanExecution(OperatingPipelineModel):
    graph_id: str
    hypothesis_id: str
    plan: AnalysisGraphPlan
    status: Literal["completed", "failed"]
    result: AnalysisResultRef | None = None
    error: OperatingRunError | None = None


class OperatingRunResult(OperatingPipelineModel):
    run_id: UUID = Field(default_factory=uuid4)
    mode: OperatingRunMode
    organization_id: UUID
    question: str | None = None
    status: OperatingRunStatus
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None

    profile: ProfilerRunResult | None = None
    context_summary: OperatingContextSummary = Field(default_factory=OperatingContextSummary)

    business_model: BusinessModel | None = None
    asset_roles: list[AssetRole] = Field(default_factory=list)
    field_roles: list[FieldRole] = Field(default_factory=list)
    business_graph: BusinessGraph | None = None
    patterns: PatternBatch | None = None
    analysis_plans: list[AnalysisGraphPlan] = Field(default_factory=list)
    executions: list[PlanExecution] = Field(default_factory=list)
    memory_writes: list[MemoryWriteResult] = Field(default_factory=list)

    interpretations: list[Interpretation] = Field(default_factory=list)
    chart_specs: list[ChartSpec] = Field(default_factory=list)
    action_batches: list[ActionBatch] = Field(default_factory=list)
    narratives: list[NarrativeSpec] = Field(default_factory=list)
    brief: BriefPackage | None = None
    business_view: BusinessViewPackage | None = None
    business_surfaces: BusinessSurfacePackage | None = None
    semantic_layer: SemanticLayerPackage | None = None
    chart_grammar: ChartGrammarPackage | None = None
    insight_ranking: InsightRankingPackage | None = None
    entity_resolution: EntityResolutionRunResult | None = None
    knowledge_graph: KnowledgeGraphMaterialization | None = None
    lineage: LineagePackage | None = None
    artifacts: ArtifactPlaneRunResult | None = None
    action_plane: ActionPlaneRunResult | None = None

    errors: list[OperatingRunError] = Field(default_factory=list)
