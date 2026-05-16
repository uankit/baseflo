"""Fresh Agent Plane DAG.

This module defines the order, parallelism, and typed payload flow. It does not
persist product artifacts yet; it returns an in-memory run result that downstream
Brief/Inbox/Ask surfaces can later persist or render.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from pydantic import BaseModel

from app.agent_plane.context import context_payload, load_canonical_context
from app.agent_plane.contracts import (
    ActionBatch,
    AssetEvidence,
    AssetRole,
    BriefPackage,
    BusinessGraph,
    BusinessModel,
    CanonicalContextPack,
    ChartSpec,
    FieldRole,
    FieldRoleBatch,
    Interpretation,
    NarrativeSpec,
    PatternBatch,
    PatternHypothesis,
)
from app.agent_plane.registry import get_agent_spec
from app.agent_plane.runner import AgentRunner
from app.analysis_contracts import AnalysisGraphPlan, AnalysisResultRef


@dataclass(frozen=True, slots=True)
class AgentPlaneRunResult:
    context: CanonicalContextPack
    business_model: BusinessModel
    asset_roles: list[AssetRole]
    field_roles: list[FieldRole]
    business_graph: BusinessGraph
    patterns: PatternBatch
    analysis_plans: list[AnalysisGraphPlan]
    interpretations: list[Interpretation]
    chart_specs: list[ChartSpec]
    action_batches: list[ActionBatch]
    narratives: list[NarrativeSpec]
    brief: BriefPackage | None
    mode: str = "scan"
    question: str | None = None


@dataclass(frozen=True, slots=True)
class AgentPlaneMaterializedArtifacts:
    interpretations: list[Interpretation]
    chart_specs: list[ChartSpec]
    action_batches: list[ActionBatch]
    narratives: list[NarrativeSpec]
    brief: BriefPackage | None


class AgentPlane:
    def __init__(self, *, runner: AgentRunner | None = None) -> None:
        self.runner = runner or AgentRunner()

    async def run(
        self,
        organization_id: UUID,
        *,
        snapshot_ids: list[UUID] | None = None,
        mode: str = "scan",
        question: str | None = None,
    ) -> AgentPlaneRunResult:
        context = await load_canonical_context(organization_id, snapshot_ids=snapshot_ids)
        if not context.assets:
            raise ValueError("Agent Plane requires at least one canonical asset")

        run_focus = {"mode": mode, "question": question}
        business_model = await self._business_understanding(context)
        asset_roles = await self._asset_roles(context, business_model)
        field_roles = await self._field_roles(context, business_model, asset_roles)
        business_graph = await self._business_graph(context, business_model, asset_roles, field_roles)
        patterns = await self._patterns(context, business_model, asset_roles, field_roles, business_graph, run_focus)
        analysis_plans = await self._analysis_plans(context, business_model, business_graph, patterns, run_focus)

        # Execution is deterministic and intentionally outside this package.
        # Until the AnalysisGraphPlan validator/executor is wired, downstream
        # result-dependent agents receive no fabricated data.
        interpretations: list[Interpretation] = []
        chart_specs: list[ChartSpec] = []
        action_batches: list[ActionBatch] = []
        narratives: list[NarrativeSpec] = []
        brief: BriefPackage | None = None

        return AgentPlaneRunResult(
            context=context,
            business_model=business_model,
            asset_roles=asset_roles,
            field_roles=field_roles,
            business_graph=business_graph,
            patterns=patterns,
            analysis_plans=analysis_plans,
            interpretations=interpretations,
            chart_specs=chart_specs,
            action_batches=action_batches,
            narratives=narratives,
            brief=brief,
            mode=mode,
            question=question,
        )

    async def _business_understanding(self, context: CanonicalContextPack) -> BusinessModel:
        output = await self.runner.run(
            get_agent_spec("business_understander"),
            {"canonical_context": context_payload(context)},
        )
        return _typed(output, BusinessModel)

    async def _asset_roles(
        self,
        context: CanonicalContextPack,
        business_model: BusinessModel,
    ) -> list[AssetRole]:
        async def _run(asset: AssetEvidence) -> AssetRole:
            output = await self.runner.run(
                get_agent_spec("asset_semanticist"),
                {
                    "business_model": business_model.model_dump(mode="json"),
                    "asset": asset.model_dump(mode="json"),
                },
            )
            return _typed(output, AssetRole)

        return list(await asyncio.gather(*[_run(asset) for asset in context.assets]))

    async def _field_roles(
        self,
        context: CanonicalContextPack,
        business_model: BusinessModel,
        asset_roles: list[AssetRole],
    ) -> list[FieldRole]:
        role_by_asset = {role.asset_id: role for role in asset_roles}

        async def _run(asset: AssetEvidence) -> FieldRoleBatch:
            output = await self.runner.run(
                get_agent_spec("field_semanticist"),
                {
                    "business_model": business_model.model_dump(mode="json"),
                    "asset_role": role_by_asset[asset.asset_id].model_dump(mode="json"),
                    "asset": asset.model_dump(mode="json"),
                },
            )
            return _typed(output, FieldRoleBatch)

        batches = await asyncio.gather(*[_run(asset) for asset in context.assets])
        return [field for batch in batches for field in batch.fields]

    async def _business_graph(
        self,
        context: CanonicalContextPack,
        business_model: BusinessModel,
        asset_roles: list[AssetRole],
        field_roles: list[FieldRole],
    ) -> BusinessGraph:
        output = await self.runner.run(
            get_agent_spec("relationship_mapper"),
            {
                "business_model": business_model.model_dump(mode="json"),
                "asset_roles": [role.model_dump(mode="json") for role in asset_roles],
                "field_roles": [role.model_dump(mode="json") for role in field_roles],
                "graph_edges": [edge.model_dump(mode="json") for edge in context.graph_edges],
            },
        )
        return _typed(output, BusinessGraph)

    async def _patterns(
        self,
        context: CanonicalContextPack,
        business_model: BusinessModel,
        asset_roles: list[AssetRole],
        field_roles: list[FieldRole],
        business_graph: BusinessGraph,
        run_focus: dict[str, Any],
    ) -> PatternBatch:
        output = await self.runner.run(
            get_agent_spec("pattern_proposer"),
            {
                "run_focus": run_focus,
                "business_model": business_model.model_dump(mode="json"),
                "asset_roles": [role.model_dump(mode="json") for role in asset_roles],
                "field_roles": [role.model_dump(mode="json") for role in field_roles],
                "business_graph": business_graph.model_dump(mode="json"),
                "memories": context.memories,
            },
        )
        return _typed(output, PatternBatch)

    async def _analysis_plans(
        self,
        context: CanonicalContextPack,
        business_model: BusinessModel,
        business_graph: BusinessGraph,
        patterns: PatternBatch,
        run_focus: dict[str, Any],
    ) -> list[AnalysisGraphPlan]:
        field_catalog = [
            field.model_dump(mode="json")
            for asset in context.assets
            for field in asset.fields
        ]

        async def _run(hypothesis: PatternHypothesis) -> AnalysisGraphPlan:
            output = await self.runner.run(
                get_agent_spec("instantiator"),
                {
                    "run_focus": run_focus,
                    "business_model": business_model.model_dump(mode="json"),
                    "business_graph": business_graph.model_dump(mode="json"),
                    "field_catalog": field_catalog,
                    "hypothesis": hypothesis.model_dump(mode="json"),
                },
            )
            return _typed(output, AnalysisGraphPlan)

        return list(await asyncio.gather(*[_run(h) for h in patterns.hypotheses]))

    async def run_result_agents(
        self,
        *,
        context: CanonicalContextPack,
        business_model: BusinessModel,
        patterns: PatternBatch,
        analysis_plans: list[AnalysisGraphPlan],
        results: list[AnalysisResultRef],
        mode: str = "scan",
        question: str | None = None,
    ) -> AgentPlaneMaterializedArtifacts:
        """Run the result-dependent half after deterministic execution.

        The Agent Plane does not fabricate results. The deterministic Analysis
        Runtime must provide AnalysisResultRef objects, then these agents can
        interpret, visualize, draft actions, narrate, and synthesize a brief.
        """
        hypothesis_by_id = {hypothesis.hypothesis_id: hypothesis for hypothesis in patterns.hypotheses}
        plan_by_graph = {plan.graph_id: plan for plan in analysis_plans}
        run_focus = {"mode": mode, "question": question}

        async def _one(result: AnalysisResultRef) -> tuple[Interpretation, ChartSpec, ActionBatch, NarrativeSpec]:
            plan = plan_by_graph[result.graph_id]
            hypothesis = hypothesis_by_id[plan.hypothesis_id]
            shared_payload = {
                "run_focus": run_focus,
                "business_model": business_model.model_dump(mode="json"),
                "hypothesis": hypothesis.model_dump(mode="json"),
                "analysis_plan": plan.model_dump(mode="json"),
                "analysis_result": result.model_dump(mode="json"),
            }
            interpretation_output = await self.runner.run(
                get_agent_spec("hypothesizer"),
                shared_payload,
            )
            interpretation = _typed(interpretation_output, Interpretation)

            chart_output, action_output, narrative_output = await asyncio.gather(
                self.runner.run(get_agent_spec("chart_spec_agent"), shared_payload),
                self.runner.run(
                    get_agent_spec("action_drafter"),
                    {
                        **shared_payload,
                        "interpretation": interpretation.model_dump(mode="json"),
                        "available_capabilities": [],
                    },
                ),
                self.runner.run(
                    get_agent_spec("narrator"),
                    {
                        **shared_payload,
                        "interpretation": interpretation.model_dump(mode="json"),
                    },
                ),
            )
            return (
                interpretation,
                _typed(chart_output, ChartSpec),
                _typed(action_output, ActionBatch),
                _typed(narrative_output, NarrativeSpec),
            )

        tuples = await asyncio.gather(*[_one(result) for result in results])
        interpretations = [entry[0] for entry in tuples]
        chart_specs = [entry[1] for entry in tuples]
        action_batches = [entry[2] for entry in tuples]
        narratives = [entry[3] for entry in tuples]

        brief: BriefPackage | None = None
        if narratives or action_batches:
            brief_output = await self.runner.run(
                get_agent_spec("brief_synthesizer"),
                {
                    "run_focus": run_focus,
                    "business_model": business_model.model_dump(mode="json"),
                    "narratives": [narrative.model_dump(mode="json") for narrative in narratives],
                    "actions": [
                        action.model_dump(mode="json")
                        for batch in action_batches
                        for action in batch.actions
                    ],
                    "context_summary": {
                        "asset_count": len(context.assets),
                        "snapshot_count": len(context.snapshots),
                    },
                },
            )
            brief = _typed(brief_output, BriefPackage)

        return AgentPlaneMaterializedArtifacts(
            interpretations=interpretations,
            chart_specs=chart_specs,
            action_batches=action_batches,
            narratives=narratives,
            brief=brief,
        )


def agent_plane_dag() -> list[dict[str, Any]]:
    """Human- and test-readable DAG description."""
    return [
        {"node": "load_canonical_context", "kind": "runtime", "after": []},
        {"node": "business_understander", "kind": "agent", "after": ["load_canonical_context"]},
        {"node": "asset_semanticist", "kind": "agent_parallel_by_asset", "after": ["business_understander"]},
        {"node": "field_semanticist", "kind": "agent_parallel_by_asset", "after": ["asset_semanticist"]},
        {"node": "relationship_mapper", "kind": "agent", "after": ["field_semanticist"]},
        {"node": "relationship_validator", "kind": "runtime", "after": ["relationship_mapper"]},
        {"node": "pattern_proposer", "kind": "agent", "after": ["relationship_validator"]},
        {"node": "instantiator", "kind": "agent_parallel_by_pattern", "after": ["pattern_proposer"]},
        {"node": "plan_validator", "kind": "runtime", "after": ["instantiator"]},
        {"node": "analysis_runtime", "kind": "runtime_parallel_by_plan", "after": ["plan_validator"]},
        {"node": "hypothesizer", "kind": "agent_parallel_by_result", "after": ["analysis_runtime"]},
        {"node": "chart_spec_agent", "kind": "agent_parallel_by_result", "after": ["analysis_runtime"]},
        {"node": "action_drafter", "kind": "agent_parallel_by_result", "after": ["hypothesizer"]},
        {"node": "narrator", "kind": "agent_parallel_by_result", "after": ["hypothesizer"]},
        {"node": "brief_synthesizer", "kind": "agent", "after": ["narrator", "action_drafter"]},
    ]


def _typed(value: BaseModel, expected: type[Any]) -> Any:
    if isinstance(value, expected):
        return value
    return expected.model_validate(value.model_dump(mode="json"))
