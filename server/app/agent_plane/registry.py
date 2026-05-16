"""Registry of Agent Plane capability agents."""

from __future__ import annotations

from app.agent_plane.contracts import (
    ActionBatch,
    AssetRole,
    BriefPackage,
    BusinessGraph,
    BusinessModel,
    ChartSpec,
    FieldRoleBatch,
    Interpretation,
    NarrativeSpec,
    PatternBatch,
)
from app.agent_plane.specs import AgentName, AgentSpec, ModelProfile
from app.analysis_contracts import AnalysisGraphPlan

AGENT_SPECS: dict[AgentName, AgentSpec] = {
    "business_understander": AgentSpec(
        name="business_understander",
        display_name="BusinessUnderstander",
        responsibility="Understand the connected business shape from canonical evidence.",
        output_type=BusinessModel,
        prompt_path="business_understander.md",
    ),
    "asset_semanticist": AgentSpec(
        name="asset_semanticist",
        display_name="AssetSemanticist",
        responsibility="Classify one canonical asset into an open business role.",
        output_type=AssetRole,
        prompt_path="asset_semanticist.md",
        model_profile=ModelProfile(max_parallelism=4),
        batchable=True,
    ),
    "field_semanticist": AgentSpec(
        name="field_semanticist",
        display_name="FieldSemanticist",
        responsibility="Classify fields within one asset into key/label/measure/time roles.",
        output_type=FieldRoleBatch,
        prompt_path="field_semanticist.md",
        model_profile=ModelProfile(max_parallelism=4),
        batchable=True,
    ),
    "relationship_mapper": AgentSpec(
        name="relationship_mapper",
        display_name="RelationshipMapper",
        responsibility="Promote evidence-backed asset/field relationships into a business graph.",
        output_type=BusinessGraph,
        prompt_path="relationship_mapper.md",
    ),
    "pattern_proposer": AgentSpec(
        name="pattern_proposer",
        display_name="PatternProposer",
        responsibility="Invent useful investigation hypotheses from the business graph and memory.",
        output_type=PatternBatch,
        prompt_path="pattern_proposer.md",
    ),
    "instantiator": AgentSpec(
        name="instantiator",
        display_name="Instantiator",
        responsibility="Convert one hypothesis into a safe generic AnalysisGraphPlan.",
        output_type=AnalysisGraphPlan,
        prompt_path="instantiator.md",
        model_profile=ModelProfile(max_parallelism=3),
        batchable=True,
    ),
    "hypothesizer": AgentSpec(
        name="hypothesizer",
        display_name="Hypothesizer",
        responsibility="Interpret materialized result facts into claims and causal candidates.",
        output_type=Interpretation,
        prompt_path="hypothesizer.md",
        model_profile=ModelProfile(max_parallelism=3),
        batchable=True,
    ),
    "chart_spec_agent": AgentSpec(
        name="chart_spec_agent",
        display_name="ChartSpecAgent",
        responsibility="Choose the best artifact visualization for materialized facts.",
        output_type=ChartSpec,
        prompt_path="chart_spec_agent.md",
        model_profile=ModelProfile(max_parallelism=3),
        batchable=True,
    ),
    "action_drafter": AgentSpec(
        name="action_drafter",
        display_name="ActionDrafter",
        responsibility="Draft approval-gated actions from evidence and available capabilities.",
        output_type=ActionBatch,
        prompt_path="action_drafter.md",
        model_profile=ModelProfile(max_parallelism=3),
        batchable=True,
    ),
    "narrator": AgentSpec(
        name="narrator",
        display_name="Narrator",
        responsibility="Turn structured findings into user-facing prose without inventing numbers.",
        output_type=NarrativeSpec,
        prompt_path="narrator.md",
        model_profile=ModelProfile(max_parallelism=4),
        batchable=True,
    ),
    "brief_synthesizer": AgentSpec(
        name="brief_synthesizer",
        display_name="BriefSynthesizer",
        responsibility="Compose already-created findings into a daily operating brief.",
        output_type=BriefPackage,
        prompt_path="brief_synthesizer.md",
    ),
}


def get_agent_spec(name: AgentName) -> AgentSpec:
    return AGENT_SPECS[name]


def list_agent_specs() -> list[AgentSpec]:
    return list(AGENT_SPECS.values())
