"""Typed contracts for Baseflo's fresh Agent Plane.

The Agent Plane starts after the canonical data plane is ready. It consumes
canonical assets, fields, graph edges, profiler evidence, and business memory;
it emits typed reasoning artifacts. Agents never see connector objects and never
execute queries directly.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ---------------------------------------------------------------------------
# Canonical context packs
# ---------------------------------------------------------------------------


class FieldEvidence(ContractModel):
    field_id: str
    asset_id: str
    name: str
    ordinal: int
    storage_type: str
    observed_type: str
    nullable: bool
    sample_values: list[Any] = Field(default_factory=list)
    profile: dict[str, Any] = Field(default_factory=dict)


class AssetEvidence(ContractModel):
    asset_id: str
    data_source_id: str
    snapshot_id: str | None
    asset_key: str
    qualified_name: str
    storage_table: str
    label: str
    asset_type: str
    row_count: int
    field_count: int
    metadata: dict[str, Any] = Field(default_factory=dict)
    profile: dict[str, Any] = Field(default_factory=dict)
    fields: list[FieldEvidence] = Field(default_factory=list)
    preview_rows: list[dict[str, Any]] = Field(default_factory=list)


class GraphEdgeEvidence(ContractModel):
    edge_id: str
    snapshot_id: str | None
    subject_type: str
    subject_id: str
    predicate: str
    object_type: str
    object_id: str
    status: str
    confidence: float = Field(ge=0.0, le=1.0)
    created_by: str
    evidence: dict[str, Any] = Field(default_factory=dict)


class SnapshotEvidence(ContractModel):
    snapshot_id: str
    data_source_id: str
    snapshot_key: str
    mode: str
    status: str
    started_at: str
    completed_at: str | None
    asset_count: int
    row_count: int
    metadata: dict[str, Any] = Field(default_factory=dict)


class CanonicalContextPack(ContractModel):
    organization_id: str
    snapshots: list[SnapshotEvidence]
    assets: list[AssetEvidence]
    graph_edges: list[GraphEdgeEvidence]
    memories: list[dict[str, Any]] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Agent outputs
# ---------------------------------------------------------------------------


class BusinessEntity(ContractModel):
    name: str
    plural: str
    description: str
    primary_asset_id: str
    related_asset_ids: list[str] = Field(default_factory=list)


class BusinessKpi(ContractModel):
    name: str
    description: str
    field_refs: list[str] = Field(default_factory=list)
    source_asset_ids: list[str] = Field(default_factory=list)


class BusinessAssumption(ContractModel):
    text: str
    confidence: float = Field(ge=0.0, le=1.0)
    impact_if_wrong: str


class BusinessModel(ContractModel):
    agent: Literal["BusinessUnderstander"] = "BusinessUnderstander"
    paragraph: str
    business_kind: str
    primary_currency: str | None = None
    entities: list[BusinessEntity]
    primary_kpis: list[BusinessKpi]
    useful_lenses: list[str] = Field(default_factory=list)
    assumptions: list[BusinessAssumption] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)


class AssetRole(ContractModel):
    agent: Literal["AssetSemanticist"] = "AssetSemanticist"
    asset_id: str
    role: str
    entity_type: str
    label: str
    tags: list[str] = Field(default_factory=list)
    why: str
    confidence: float = Field(ge=0.0, le=1.0)


class FieldRole(ContractModel):
    agent: Literal["FieldSemanticist"] = "FieldSemanticist"
    field_id: str
    asset_id: str
    field_name: str
    semantic_type: str
    role: Literal[
        "primary_key",
        "foreign_key",
        "label",
        "measure",
        "timestamp",
        "status",
        "category",
        "identifier",
        "text",
        "unknown",
    ]
    entity_hint: str | None = None
    measure_kind: str | None = None
    why: str
    confidence: float = Field(ge=0.0, le=1.0)


class FieldRoleBatch(ContractModel):
    agent: Literal["FieldSemanticist"] = "FieldSemanticist"
    fields: list[FieldRole]


class BusinessGraphNode(ContractModel):
    entity: str
    asset_id: str
    label: str
    why: str


class BusinessGraphEdge(ContractModel):
    left_entity: str
    left_asset_id: str
    left_field_id: str
    right_entity: str
    right_asset_id: str
    right_field_id: str
    cardinality: Literal["one_to_one", "one_to_many", "many_to_one", "many_to_many"]
    meaning: str
    evidence_edge_ids: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)


class BusinessGraph(ContractModel):
    agent: Literal["RelationshipMapper"] = "RelationshipMapper"
    nodes: list[BusinessGraphNode]
    edges: list[BusinessGraphEdge]
    notes: list[str] = Field(default_factory=list)


class SignalRef(ContractModel):
    asset_id: str
    field_id: str | None = None
    role: str
    aggregate: Literal["sum", "avg", "count", "min", "max"] = "count"
    direction: Literal["asc", "desc"] = "desc"


class PatternHypothesis(ContractModel):
    agent: Literal["PatternProposer"] = "PatternProposer"
    hypothesis_id: str
    pattern_type: str
    target_entity: str
    target_asset_id: str
    signals: list[SignalRef] = Field(default_factory=list)
    question: str
    why_this_matters: str
    priority: float = Field(ge=0.0, le=1.0)


class PatternBatch(ContractModel):
    agent: Literal["PatternProposer"] = "PatternProposer"
    hypotheses: list[PatternHypothesis]


class Interpretation(ContractModel):
    agent: Literal["Hypothesizer"] = "Hypothesizer"
    claim: str
    why: str
    causal_candidates: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)


class ChartSpec(ContractModel):
    agent: Literal["ChartSpecAgent"] = "ChartSpecAgent"
    artifact_id: str
    viz_type: Literal["table", "metric", "bar", "line", "scatter"]
    title: str
    why: str
    x_field: str | None = None
    y_field: str | None = None
    data_ref: str


class ActionDraft(ContractModel):
    agent: Literal["ActionDrafter"] = "ActionDrafter"
    action_id: str
    action_type: str
    title: str
    why: str
    why_now: str
    evidence_refs: list[str] = Field(default_factory=list)
    capability_required: str
    execution_mode: Literal[
        "draft_only",
        "prepare_for_user",
        "delegate_inside_baseflo",
        "adapter_executable",
        "manual_external",
    ]
    payload: dict[str, Any] = Field(default_factory=dict)
    approval_scope: dict[str, Any] = Field(default_factory=dict)
    risk: str


class ActionBatch(ContractModel):
    agent: Literal["ActionDrafter"] = "ActionDrafter"
    actions: list[ActionDraft]


class NarrativeSpec(ContractModel):
    agent: Literal["Narrator"] = "Narrator"
    headline: str
    summary: str
    why: str
    style: Literal["brief", "inbox", "ask"] = "brief"


class BriefPackage(ContractModel):
    agent: Literal["BriefSynthesizer"] = "BriefSynthesizer"
    headline: str
    summary_points: list[str]
    urgent_artifact_ids: list[str] = Field(default_factory=list)
    why: str
