"""Agentic operating intelligence — capability agents.

Pipeline (DAG):

  0. Mirror + Profile (runtime)
  1. BusinessUnderstander       → BusinessModel
  2a. AssetSemanticist × N       → AssetRole per asset (parallel)
  2b. GraphSeeder (runtime)      → raw join candidates
  3. RelationshipGraphBuilder    → EntityGraph
  4. GraphValidator (runtime)    → validated EntityGraph
  5. FormulaPlanner × 3          → TeamPlan per team (FormulaSpecs)
  6. FormulaCompiler (runtime)   → AnalysisGraph per formula
  7. AnalysisRuntime × M         → rows per formula
  8a. Hypothesizer × M           → Interpretation
  8b. Narrator × M               → NarrativeSpec
  8c. ActionDrafter × M          → ActionDraft list
  9. CrossTeamSynthesizer        → CrossTeamReport
 10. BriefSynthesizer            → FounderBrief

Every node emits a typed Pydantic model. The runtime never makes a semantic
decision. Agents never touch SQL or raw data — they read schemas, samples,
semantics, and the *materialised results* of typed plans.
"""

from app.agents._contracts import (
    AlignmentNote,
    BusinessAssumption,
    BusinessEntity,
    BusinessKpi,
    BusinessModel,
    ConflictNote,
    CrossTeamReport,
    EntityGraph,
    FormulaFieldRef,
    FormulaFilter,
    FormulaJoin,
    FormulaMeasure,
    FormulaSpec,
    FounderBrief,
    GapNote,
    GraphEdge,
    GraphNode,
    HandoffAction,
    TeamAsk,
    TeamByline,
    TeamId,
    TeamPlan,
)
from app.agents._model import (
    AgentRunError,
    AgentsUnavailable,
    agent_is_configured,
    get_default_model,
    use_test_model,
)
from app.agents.action_drafter import ActionBatch, draft_actions
from app.agents.brief_synthesizer import synthesize_brief
from app.agents.business_understander import understand_business
from app.agents.cross_team import synthesize_cross_team
from app.agents.formula_compiler import FormulaCompileError, compile_formula, field_catalog_for_prompt
from app.agents.graph_validator import validate_graph
from app.agents.hypothesizer import interpret_result
from app.agents.narrator import narrate_interpretation
from app.agents.relationship_mapper import map_relationships
from app.agents.semantic_annotator import annotate_asset
from app.agents.team_agent import ACTIVE_TEAMS, run_team

__all__ = [
    "ACTIVE_TEAMS",
    "ActionBatch",
    "AgentRunError",
    "AgentsUnavailable",
    "AlignmentNote",
    "BusinessAssumption",
    "BusinessEntity",
    "BusinessKpi",
    "BusinessModel",
    "ConflictNote",
    "CrossTeamReport",
    "EntityGraph",
    "FormulaFieldRef",
    "FormulaCompileError",
    "FormulaFilter",
    "FormulaJoin",
    "FormulaMeasure",
    "FormulaSpec",
    "FounderBrief",
    "GapNote",
    "GraphEdge",
    "GraphNode",
    "HandoffAction",
    "TeamAsk",
    "TeamByline",
    "TeamId",
    "TeamPlan",
    "agent_is_configured",
    "annotate_asset",
    "compile_formula",
    "draft_actions",
    "field_catalog_for_prompt",
    "get_default_model",
    "interpret_result",
    "map_relationships",
    "narrate_interpretation",
    "run_team",
    "synthesize_brief",
    "synthesize_cross_team",
    "understand_business",
    "use_test_model",
    "validate_graph",
]
