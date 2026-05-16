"""Contracts for generated operating surfaces and mined insight candidates."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

SurfaceKind = Literal[
    "sales",
    "receivables",
    "inventory",
    "customers_parties",
    "products_items",
    "expenses",
    "profit_loss",
    "operations",
    "data_quality",
    "connected_data",
]

DimensionKind = Literal[
    "entity",
    "party",
    "customer",
    "product",
    "item",
    "time",
    "status",
    "location",
    "category",
    "channel",
    "source",
    "unknown",
]

MeasureKind = Literal[
    "amount",
    "pending_amount",
    "bill_amount",
    "revenue",
    "cost",
    "expense",
    "quantity",
    "inventory",
    "count",
    "rate",
    "unknown",
]

AggregateKind = Literal["sum", "avg", "count", "min", "max"]

MiningAlgorithm = Literal[
    "semantic_surface_detection",
    "cube_rollup",
    "extreme_rank",
    "coverage_scan",
    "relationship_walk",
    "deviation_scan",
    "long_tail_scan",
    "probabilistic_entity_resolution",
]

BulkActionType = Literal["email_draft", "export_list", "save_cohort"]


class SurfaceModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SurfaceDimension(SurfaceModel):
    dimension_id: str
    label: str
    kind: DimensionKind
    field_id: str
    asset_id: str
    entity_hint: str | None = None
    why: str
    confidence: float = Field(ge=0.0, le=1.0)


class SurfaceMeasure(SurfaceModel):
    measure_id: str
    label: str
    kind: MeasureKind
    field_id: str
    asset_id: str
    default_aggregate: AggregateKind
    unit: str | None = None
    why: str
    confidence: float = Field(ge=0.0, le=1.0)


class CandidateView(SurfaceModel):
    view_id: str
    surface_id: str
    title: str
    question: str
    algorithm: MiningAlgorithm
    dimensions: list[str] = Field(default_factory=list)
    measures: list[str] = Field(default_factory=list)
    expected_output: Literal["table", "metric", "bar", "line", "comparison", "cohort"]
    priority: float = Field(ge=0.0, le=1.0)
    why: str
    execution_hint: dict[str, Any] = Field(default_factory=dict)


class SurfaceCohort(SurfaceModel):
    cohort_id: str
    surface_id: str
    label: str
    entity: str | None = None
    description: str
    filter_refs: list[str] = Field(default_factory=list)
    measure_refs: list[str] = Field(default_factory=list)
    dimension_refs: list[str] = Field(default_factory=list)
    size_hint: str | None = None
    value_hint: str | None = None
    actionability: float = Field(ge=0.0, le=1.0)
    why: str


class BulkActionPack(SurfaceModel):
    action_pack_id: str
    surface_id: str
    title: str
    action_type: BulkActionType
    execution_mode: Literal["prepare_for_user"] = "prepare_for_user"
    target_entity: str | None = None
    cohort_refs: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    payload_template: dict[str, Any] = Field(default_factory=dict)
    why: str
    approval_required: str
    risk: str
    priority: float = Field(ge=0.0, le=1.0)


class InsightGraphNode(SurfaceModel):
    node_id: str
    node_type: Literal[
        "surface",
        "entity",
        "measure",
        "dimension",
        "candidate_view",
        "cohort",
        "action_pack",
        "evidence",
    ]
    label: str
    refs: dict[str, Any] = Field(default_factory=dict)


class InsightGraphEdge(SurfaceModel):
    left_node_id: str
    right_node_id: str
    relationship: Literal[
        "contains",
        "uses",
        "explains",
        "targets",
        "supports",
        "drills_into",
        "can_trigger",
        "matches_with",
    ]
    why: str
    confidence: float = Field(ge=0.0, le=1.0)


class InsightGraph(SurfaceModel):
    nodes: list[InsightGraphNode] = Field(default_factory=list)
    edges: list[InsightGraphEdge] = Field(default_factory=list)


class BusinessSurface(SurfaceModel):
    surface_id: str
    kind: SurfaceKind
    title: str
    description: str
    entity: str | None = None
    why_built: str
    source_asset_ids: list[str] = Field(default_factory=list)
    field_refs: list[str] = Field(default_factory=list)
    graph_refs: list[str] = Field(default_factory=list)
    dimensions: list[SurfaceDimension] = Field(default_factory=list)
    measures: list[SurfaceMeasure] = Field(default_factory=list)
    candidate_views: list[CandidateView] = Field(default_factory=list)
    cohorts: list[SurfaceCohort] = Field(default_factory=list)
    action_packs: list[BulkActionPack] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)


class BusinessSurfacePackage(SurfaceModel):
    headline: str
    summary: str
    why: str
    algorithms: list[MiningAlgorithm] = Field(default_factory=list)
    surfaces: list[BusinessSurface] = Field(default_factory=list)
    insight_graph: InsightGraph = Field(default_factory=InsightGraph)
    generated_from: dict[str, Any] = Field(default_factory=dict)
    confidence: float = Field(ge=0.0, le=1.0)
