"""Typed contracts for the agentic pipeline.

Every agent emits one of these. The runtime reads them. No agent writes raw
SQL. No runtime makes a semantic decision. The contracts are the boundary.

The older types — AssetRole, JoinProposal, PatternHypothesis, AnalysisGraph,
Interpretation, ActionDraft, ChartSpec, NarrativeSpec — live in
`app.agentic`. They remain the executor-level payloads. The contracts in
this module sit one level higher and describe the *team-shaped* pipeline.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ============================================================================
# Phase 1 — BusinessUnderstander
# ============================================================================


class BusinessEntity(ContractModel):
    """A noun the business cares about (customer, product, order, campaign…)."""

    name: str  # singular, lowercase: "customer", "product"
    plural: str
    description: str
    primary_asset: str  # qualified_name of the asset that primarily holds it
    related_assets: list[str] = Field(default_factory=list)


class BusinessKpi(ContractModel):
    """A KPI the business should watch, named in the business's own words."""

    name: str  # e.g., "revenue", "stock cover", "repeat rate"
    description: str
    measure_column: str | None = None  # qualified_name.column when single-source
    derived_from: list[str] = Field(default_factory=list)  # qualified_names involved


class BusinessAssumption(ContractModel):
    """An assumption the agent made that the user should be able to correct."""

    text: str
    confidence: float = Field(ge=0.0, le=1.0)
    impact_if_wrong: str  # one sentence on what would be wrong if this were wrong


class BusinessModel(ContractModel):
    """The system's mental model of *this* business. The Phase 1 keystone."""

    agent: Literal["BusinessUnderstander"] = "BusinessUnderstander"
    paragraph: str  # plain-English narration; the user reads this directly
    business_kind: str  # "apparel ecommerce on Shopify", "B2B SaaS billing", etc.
    primary_currency: str | None = None  # "INR", "USD"…
    entities: list[BusinessEntity]
    primary_kpis: list[BusinessKpi]
    interesting_perspectives: list[str] = Field(default_factory=list)  # which teams matter most
    assumptions: list[BusinessAssumption] = Field(default_factory=list)
    missing_or_failed_sources: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)


# ============================================================================
# Phase 3 — RelationshipGraphBuilder
# ============================================================================


class GraphNode(ContractModel):
    entity: str  # business entity name
    asset_qualified_name: str
    label: str  # human-readable
    why: str


class GraphEdge(ContractModel):
    left_entity: str
    left_table: str
    left_key: str
    right_entity: str
    right_table: str
    right_key: str
    cardinality: Literal["one_to_one", "one_to_many", "many_to_one", "many_to_many"]
    meaning: str  # one-sentence business explanation
    confidence: float = Field(ge=0.0, le=1.0)
    validated: bool = False  # GraphValidator stamps this true after sample-join check


class EntityGraph(ContractModel):
    agent: Literal["RelationshipGraphBuilder"] = "RelationshipGraphBuilder"
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    notes: list[str] = Field(default_factory=list)


# ============================================================================
# Phase 5 — Formula planners propose FormulaSpec
# ============================================================================


TeamId = Literal["sales", "marketing", "ops", "growth", "product", "biz_analyst"]


class FormulaJoin(ContractModel):
    """One join hop the formula needs. References EntityGraph edges."""

    left_entity: str
    right_entity: str
    # When the team agent already knows the keys, fill them. Otherwise the
    # FormulaCompiler resolves them from the validated EntityGraph.
    left_key: str | None = None
    right_key: str | None = None


class FormulaFieldRef(ContractModel):
    """A business-scoped field reference.

    Agents name the entity and the field they want. The deterministic
    FormulaCompiler resolves this to a concrete table column and stable runtime
    alias. This keeps team agents from guessing joined column names.
    """

    entity: str
    field: str
    surface_table: str | None = None


class FormulaFilter(ContractModel):
    field: FormulaFieldRef
    operator: Literal["=", "!=", ">", ">=", "<", "<=", "is_null", "is_not_null"]
    value: str | float | int | bool | None = None


class FormulaMeasure(ContractModel):
    field: FormulaFieldRef | None = None  # None only for count(*).
    aggregate: Literal["sum", "avg", "count", "min", "max"]
    alias: str  # snake_case identifier safe for SQL


class FormulaSpec(ContractModel):
    """A typed analysis the team agent wants run. NOT SQL.

    The FormulaCompiler reads this together with the EntityGraph and the
    BusinessModel, then emits an AnalysisGraph the runtime can execute.
    """

    agent: Literal["FormulaPlanner"] = "FormulaPlanner"
    team_id: TeamId
    formula_id: str  # snake_case identifier, unique within the team's batch
    why: str  # one sentence on why this team wants to look at this
    title: str  # short, in team voice
    target_entity: str  # the business entity in focus
    joins: list[FormulaJoin] = Field(default_factory=list)  # optional hints; compiler plans paths
    filters: list[FormulaFilter] = Field(default_factory=list)
    group_by_field: FormulaFieldRef
    measures: list[FormulaMeasure]
    order_by_alias: str | None = None  # alias of a measure to order by
    direction: Literal["asc", "desc"] = "desc"
    limit: int = Field(default=10, ge=1, le=100)
    expected_shape: str  # one sentence on what this returns


# ============================================================================
# Phase 5 — Team output (formula plans + planning asks)
# ============================================================================


class TeamAsk(ContractModel):
    """Something this team wants from another team to act on the finding."""

    from_team: TeamId
    to_team: TeamId
    request: str  # short sentence


class TeamPlan(ContractModel):
    """Per-team output of Phase 5 — what the formula planner emits in one call."""

    agent: Literal["FormulaPlanner"] = "FormulaPlanner"
    team_id: TeamId
    standup_summary: str  # 1–2 sentences in this team's voice
    formulas: list[FormulaSpec]
    open_asks: list[TeamAsk] = Field(default_factory=list)


# ============================================================================
# Phase 9 — CrossTeamSynthesizer
# ============================================================================


class AlignmentNote(ContractModel):
    """Two or more teams pulling the same direction."""

    teams: list[TeamId]
    insight_ids: list[str]  # references to persisted Insight rows by id
    claim: str  # plain sentence describing the alignment


class ConflictNote(ContractModel):
    """Two teams contradicting each other on the same underlying data."""

    teams: list[TeamId]
    insight_ids: list[str]
    claim: str  # plain sentence describing the conflict
    resolution_hint: str  # one sentence on how the founder could resolve it


class GapNote(ContractModel):
    """A finding no team flagged that the founder should see."""

    related_entities: list[str]
    claim: str
    why_missed: str  # why no team caught it


class HandoffAction(ContractModel):
    """A cross-team action that needs at least two teams to execute."""

    from_team: TeamId
    to_team: TeamId
    title: str
    summary: str
    why: str
    payload_hint: dict[str, Any] = Field(default_factory=dict)


class CrossTeamReport(ContractModel):
    agent: Literal["CrossTeamSynthesizer"] = "CrossTeamSynthesizer"
    alignments: list[AlignmentNote] = Field(default_factory=list)
    conflicts: list[ConflictNote] = Field(default_factory=list)
    gaps: list[GapNote] = Field(default_factory=list)
    handoffs: list[HandoffAction] = Field(default_factory=list)
    standup_summary: str  # one paragraph the founder reads first


# ============================================================================
# Phase 10 — BriefSynthesizer
# ============================================================================


class BriefSignal(ContractModel):
    label: str
    value: str
    detail: str = ""
    tone: Literal["good", "warn", "neutral"] = "neutral"
    source_insight_id: str | None = None  # so the user can drill in


class TeamByline(ContractModel):
    """One team's section in the founder brief."""

    team_id: TeamId
    standup_summary: str
    insight_ids: list[str]


class FounderBrief(ContractModel):
    agent: Literal["BriefSynthesizer"] = "BriefSynthesizer"
    headline: str
    dek: str
    signals: list[BriefSignal] = Field(default_factory=list)
    team_bylines: list[TeamByline] = Field(default_factory=list)
    cross_team_summary: str  # one paragraph drawing the alignment/conflict picture
    questions: list[str] = Field(default_factory=list)
