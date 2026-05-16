from __future__ import annotations

from uuid import UUID, uuid4

import pytest


def _context(org_id: UUID):
    from app.agent_plane.contracts import AssetEvidence, CanonicalContextPack, FieldEvidence

    field = FieldEvidence(
        field_id="field-total",
        asset_id="asset-orders",
        name="total",
        ordinal=1,
        storage_type="varchar",
        observed_type="number",
        nullable=False,
        sample_values=[120, 240],
    )
    asset = AssetEvidence(
        asset_id="asset-orders",
        data_source_id="source-1",
        snapshot_id="snapshot-1",
        asset_key="orders",
        qualified_name="orders",
        storage_table="orders",
        label="Orders",
        asset_type="table",
        row_count=2,
        field_count=1,
        fields=[field],
    )
    return CanonicalContextPack(
        organization_id=str(org_id),
        snapshots=[],
        assets=[asset],
        graph_edges=[],
        memories=[],
    )


def _business_model():
    from app.agent_plane.contracts import BusinessEntity, BusinessKpi, BusinessModel

    return BusinessModel(
        paragraph="This business sells through connected orders.",
        business_kind="commerce",
        entities=[
            BusinessEntity(
                name="order",
                plural="orders",
                description="Customer purchase events.",
                primary_asset_id="asset-orders",
            )
        ],
        primary_kpis=[
            BusinessKpi(
                name="Revenue",
                description="Total value of orders.",
                field_refs=["field-total"],
                source_asset_ids=["asset-orders"],
            )
        ],
        confidence=0.8,
    )


def _plan(graph_id: str, hypothesis_id: str):
    from app.analysis_contracts import AnalysisGraphPlan

    return AnalysisGraphPlan(
        graph_id=graph_id,
        hypothesis_id=hypothesis_id,
        operators=[
            {"op": "source", "id": "orders", "asset_id": "asset-orders"},
            {"op": "limit", "id": "limited", "input": "orders", "limit": 10},
        ],
        output="limited",
        why="Inspect connected orders.",
    )


def _planning(org_id: UUID, plans: list[object]):
    from app.agent_plane.contracts import (
        AssetRole,
        BusinessGraph,
        BusinessGraphNode,
        PatternBatch,
        PatternHypothesis,
    )
    from app.agent_plane.graph import AgentPlaneRunResult

    context = _context(org_id)
    business_model = _business_model()
    return AgentPlaneRunResult(
        context=context,
        business_model=business_model,
        asset_roles=[
            AssetRole(
                asset_id="asset-orders",
                role="revenue_event",
                entity_type="order",
                label="Orders",
                why="Rows look like order events.",
                confidence=0.8,
            )
        ],
        field_roles=[],
        business_graph=BusinessGraph(
            nodes=[
                BusinessGraphNode(
                    entity="order",
                    asset_id="asset-orders",
                    label="Orders",
                    why="Primary connected event asset.",
                )
            ],
            edges=[],
        ),
        patterns=PatternBatch(
            hypotheses=[
                PatternHypothesis(
                    hypothesis_id=plan.hypothesis_id,
                    pattern_type="inspect_orders",
                    target_entity="order",
                    target_asset_id="asset-orders",
                    question="What is happening in orders?",
                    why_this_matters="Orders reflect revenue movement.",
                    priority=0.8,
                )
                for plan in plans
            ]
        ),
        analysis_plans=plans,
        interpretations=[],
        chart_specs=[],
        action_batches=[],
        narratives=[],
        brief=None,
    )


class FakeAgentPlane:
    def __init__(self, org_id: UUID, plans: list[object]) -> None:
        self.org_id = org_id
        self.plans = plans
        self.mode: str | None = None
        self.question: str | None = None
        self.result_count = 0

    async def run(self, organization_id, *, snapshot_ids=None, mode="scan", question=None):
        self.mode = mode
        self.question = question
        return _planning(organization_id, self.plans)

    async def run_result_agents(
        self,
        *,
        context,
        business_model,
        patterns,
        analysis_plans,
        results,
        mode="scan",
        question=None,
    ):
        from app.agent_plane.contracts import (
            ActionBatch,
            ActionDraft,
            BriefPackage,
            ChartSpec,
            Interpretation,
            NarrativeSpec,
        )
        from app.agent_plane.graph import AgentPlaneMaterializedArtifacts

        self.result_count = len(results)
        return AgentPlaneMaterializedArtifacts(
            interpretations=[
                Interpretation(
                    claim=f"{result.graph_id} has {result.row_count} rows.",
                    why="The materialized result returned rows.",
                    confidence=0.8,
                )
                for result in results
            ],
            chart_specs=[
                ChartSpec(
                    artifact_id=f"chart-{result.graph_id}",
                    viz_type="table",
                    title="Result table",
                    why="A table preserves row-level evidence.",
                    data_ref=result.graph_id,
                )
                for result in results
            ],
            action_batches=[
                ActionBatch(
                    actions=[
                        ActionDraft(
                            action_id=f"action-{result.graph_id}",
                            action_type="investigation",
                            title="Review this cohort",
                            why="The result is worth inspecting.",
                            why_now="The run just found it.",
                            capability_required="baseflo.task",
                            execution_mode="prepare_for_user",
                            approval_scope={"requires_user_approval": True},
                            risk="Low risk; review only.",
                        )
                    ]
                )
                for result in results
            ],
            narratives=[
                NarrativeSpec(
                    headline="Orders need a look",
                    summary="The materialized result is ready to inspect.",
                    why="The summary is based on the result rows.",
                    style="ask" if mode == "ask" else "brief",
                )
                for _result in results
            ],
            brief=BriefPackage(
                headline="Operating run complete",
                summary_points=["One grounded result is ready."],
                urgent_artifact_ids=[],
                why="The brief summarizes completed result artifacts.",
            ),
        )


async def _profiler(organization_id: UUID, *, snapshot_ids=None):
    from app.data_profiler.contracts import ProfilerRunResult

    return ProfilerRunResult(
        organization_id=str(organization_id),
        snapshot_ids=[str(snapshot_id) for snapshot_id in snapshot_ids or []],
        asset_count=1,
        field_count=1,
        relationship_count=0,
    )


async def _empty_profiler(organization_id: UUID, *, snapshot_ids=None):
    from app.data_profiler.contracts import ProfilerRunResult

    return ProfilerRunResult(
        organization_id=str(organization_id),
        snapshot_ids=[],
        asset_count=0,
        field_count=0,
        relationship_count=0,
        quality_flags=["no_completed_snapshots"],
    )


async def _memory_recorder(
    organization_id: UUID,
    *,
    business_model,
    asset_roles,
    field_roles,
    business_graph,
    patterns=None,
):
    from app.memory_plane.contracts import MemoryPlaneRunResult

    return MemoryPlaneRunResult(candidates=[], writes=[])


async def _artifact_recorder(organization_id: UUID, *, run):
    from app.artifact_plane import ArtifactPlaneRunResult

    return ArtifactPlaneRunResult(organization_id=organization_id, run_id=run.run_id)


async def _action_recorder(organization_id: UUID, *, artifacts):
    from app.action_plane import ActionPlaneRunResult

    return ActionPlaneRunResult(organization_id=organization_id, run_id=artifacts.run_id)


def _knowledge_graph_recorder(organization_id: UUID, *, business_surfaces, run_id=None):
    from app.knowledge_graph_plane import KnowledgeGraphMaterialization

    node_count = len(business_surfaces.insight_graph.nodes) if business_surfaces else 0
    edge_count = len(business_surfaces.insight_graph.edges) if business_surfaces else 0
    return KnowledgeGraphMaterialization(
        status="completed",
        graph_path=f"/tmp/{organization_id}.kuzu",
        node_count=node_count,
        edge_count=edge_count,
    )


async def _entity_resolution_recorder(organization_id: UUID, business_surfaces):
    from app.entity_resolution_plane import (
        EntityResolutionRunResult,
        plan_entity_resolution_from_surfaces,
    )

    _ = organization_id
    planned = plan_entity_resolution_from_surfaces(business_surfaces)
    return EntityResolutionRunResult(
        plans=planned.plans,
        executions=planned.executions,
        generated_from={**planned.generated_from, "test_recorder": True},
    )


@pytest.mark.asyncio
async def test_operating_pipeline_scan_returns_completed_run() -> None:
    from app.analysis_contracts import AnalysisResultRef
    from app.operating_pipeline import OperatingPipeline, OperatingRunRequest

    org_id = uuid4()
    plans = [_plan("graph-1", "hypothesis-1")]

    async def executor(organization_id, plan, *, max_preview_rows):
        return AnalysisResultRef(
            graph_id=plan.graph_id,
            row_count=1,
            result_preview=[{"total": "120"}],
            lineage=[{"field_id": "field-total"}],
        )

    pipeline = OperatingPipeline(
        agent_plane=FakeAgentPlane(org_id, plans),
        plan_executor=executor,
        profiler=_profiler,
        memory_recorder=_memory_recorder,
        entity_resolution_runner=_entity_resolution_recorder,
        knowledge_graph_recorder=_knowledge_graph_recorder,
        artifact_recorder=_artifact_recorder,
        action_recorder=_action_recorder,
    )

    event_types: list[str] = []

    async def publish_event(**event):
        event_types.append(event["type"])

    result = await pipeline.run(
        org_id,
        OperatingRunRequest(mode="scan"),
        event_publisher=publish_event,
    )

    assert result.status == "completed"
    assert result.mode == "scan"
    assert result.profile is not None
    assert result.context_summary.asset_count == 1
    assert result.executions[0].status == "completed"
    assert result.brief is not None
    assert result.business_view is not None
    assert result.business_view.sections
    assert result.business_surfaces is not None
    assert result.business_surfaces.surfaces
    assert result.semantic_layer is not None
    assert result.chart_grammar is not None
    assert result.chart_grammar.charts
    assert result.insight_ranking is not None
    assert result.insight_ranking.ranked
    assert result.entity_resolution is not None
    assert result.knowledge_graph is not None
    assert result.lineage is not None
    assert result.lineage.runs
    assert result.artifacts is not None
    assert result.action_plane is not None
    assert event_types[:2] == ["operating.started", "profiler.started"]
    assert "execution.plan_completed" in event_types
    assert "business_view.completed" in event_types
    assert "business_surfaces.completed" in event_types
    assert "semantic_layer.completed" in event_types
    assert "chart_grammar.completed" in event_types
    assert "insight_ranking.completed" in event_types
    assert "entity_resolution.completed" in event_types
    assert "knowledge_graph.completed" in event_types
    assert "lineage.completed" in event_types
    assert "artifact_plane.completed" in event_types
    assert "action_plane.completed" in event_types
    assert event_types[-1] == "operating.completed"


@pytest.mark.asyncio
async def test_operating_pipeline_no_canonical_data_stops_before_agent_plane() -> None:
    from app.operating_pipeline import OperatingPipeline, OperatingRunRequest

    org_id = uuid4()

    class AgentShouldNotRun(FakeAgentPlane):
        async def run(self, organization_id, *, snapshot_ids=None, mode="scan", question=None):
            raise AssertionError("agent plane should not run without canonical data")

    pipeline = OperatingPipeline(
        agent_plane=AgentShouldNotRun(org_id, []),
        profiler=_empty_profiler,
        memory_recorder=_memory_recorder,
        entity_resolution_runner=_entity_resolution_recorder,
        knowledge_graph_recorder=_knowledge_graph_recorder,
        artifact_recorder=_artifact_recorder,
        action_recorder=_action_recorder,
    )

    event_types: list[str] = []

    async def publish_event(**event):
        event_types.append(event["type"])

    result = await pipeline.run(
        org_id,
        OperatingRunRequest(mode="scan"),
        event_publisher=publish_event,
    )

    assert result.status == "failed"
    assert result.context_summary.asset_count == 0
    assert result.profile is not None
    assert result.profile.quality_flags == ["no_completed_snapshots"]
    assert result.errors[0].stage == "data_plane"
    assert result.errors[0].details["code"] == "NO_CANONICAL_DATA"
    assert "agent_plane.planning_started" not in event_types
    assert "data_plane.no_canonical_data" in event_types
    assert event_types[-1] == "operating.failed"


@pytest.mark.asyncio
async def test_operating_pipeline_ask_passes_question_to_agent_plane() -> None:
    from app.analysis_contracts import AnalysisResultRef
    from app.operating_pipeline import OperatingPipeline, OperatingRunRequest

    org_id = uuid4()
    fake_agent = FakeAgentPlane(org_id, [_plan("graph-1", "hypothesis-1")])

    async def executor(organization_id, plan, *, max_preview_rows):
        return AnalysisResultRef(graph_id=plan.graph_id, row_count=0, result_preview=[])

    pipeline = OperatingPipeline(
        agent_plane=fake_agent,
        plan_executor=executor,
        profiler=_profiler,
        memory_recorder=_memory_recorder,
        entity_resolution_runner=_entity_resolution_recorder,
        knowledge_graph_recorder=_knowledge_graph_recorder,
        artifact_recorder=_artifact_recorder,
        action_recorder=_action_recorder,
    )

    result = await pipeline.run(
        org_id,
        OperatingRunRequest(mode="ask", question="Compare order totals by party"),
    )

    assert result.mode == "ask"
    assert result.question == "Compare order totals by party"
    assert fake_agent.mode == "ask"
    assert fake_agent.question == "Compare order totals by party"
    assert result.narratives[0].style == "ask"


@pytest.mark.asyncio
async def test_operating_pipeline_records_failed_plan_without_fake_artifacts() -> None:
    from app.analysis_contracts import AnalysisResultRef
    from app.operating_pipeline import OperatingPipeline, OperatingRunRequest

    org_id = uuid4()
    plans = [_plan("graph-ok", "hypothesis-ok"), _plan("graph-bad", "hypothesis-bad")]
    fake_agent = FakeAgentPlane(org_id, plans)

    async def executor(organization_id, plan, *, max_preview_rows):
        if plan.graph_id == "graph-bad":
            raise RuntimeError("missing relationship evidence")
        return AnalysisResultRef(
            graph_id=plan.graph_id,
            row_count=1,
            result_preview=[{"total": "240"}],
        )

    pipeline = OperatingPipeline(
        agent_plane=fake_agent,
        plan_executor=executor,
        profiler=_profiler,
        memory_recorder=_memory_recorder,
        entity_resolution_runner=_entity_resolution_recorder,
        knowledge_graph_recorder=_knowledge_graph_recorder,
        artifact_recorder=_artifact_recorder,
        action_recorder=_action_recorder,
    )

    result = await pipeline.run(org_id, OperatingRunRequest(mode="scan"))

    assert result.status == "partial"
    assert [execution.status for execution in result.executions] == ["completed", "failed"]
    assert result.errors[0].stage == "execution_plane"
    assert fake_agent.result_count == 1
    assert len(result.interpretations) == 1


@pytest.mark.asyncio
async def test_operating_pipeline_partial_run_emits_partial_terminal_event() -> None:
    from app.analysis_contracts import AnalysisResultRef
    from app.operating_pipeline import OperatingPipeline, OperatingRunRequest

    org_id = uuid4()
    fake_agent = FakeAgentPlane(
        org_id,
        [_plan("graph-ok", "hypothesis-ok"), _plan("graph-bad", "hypothesis-bad")],
    )

    async def executor(organization_id, plan, *, max_preview_rows):
        if plan.graph_id == "graph-bad":
            raise RuntimeError("missing relationship evidence")
        return AnalysisResultRef(graph_id=plan.graph_id, row_count=1, result_preview=[])

    pipeline = OperatingPipeline(
        agent_plane=fake_agent,
        plan_executor=executor,
        profiler=_profiler,
        memory_recorder=_memory_recorder,
        entity_resolution_runner=_entity_resolution_recorder,
        knowledge_graph_recorder=_knowledge_graph_recorder,
        artifact_recorder=_artifact_recorder,
        action_recorder=_action_recorder,
    )

    event_types: list[str] = []

    async def publish_event(**event):
        event_types.append(event["type"])

    result = await pipeline.run(
        org_id,
        OperatingRunRequest(mode="scan"),
        event_publisher=publish_event,
    )

    assert result.status == "partial"
    assert event_types[-1] == "operating.partial"


@pytest.mark.asyncio
async def test_operating_pipeline_all_failed_plans_stop_before_product_artifacts() -> None:
    from app.operating_pipeline import OperatingPipeline, OperatingRunRequest

    org_id = uuid4()
    fake_agent = FakeAgentPlane(org_id, [_plan("graph-fail", "hypothesis-fail")])

    async def executor(organization_id, plan, *, max_preview_rows):
        raise RuntimeError("all execution failed")

    async def artifact_recorder(organization_id, *, run):
        raise AssertionError("artifact recorder should not run for failed execution")

    async def action_recorder(organization_id, *, artifacts):
        raise AssertionError("action recorder should not run for failed execution")

    pipeline = OperatingPipeline(
        agent_plane=fake_agent,
        plan_executor=executor,
        profiler=_profiler,
        memory_recorder=_memory_recorder,
        entity_resolution_runner=_entity_resolution_recorder,
        knowledge_graph_recorder=_knowledge_graph_recorder,
        artifact_recorder=artifact_recorder,
        action_recorder=action_recorder,
    )

    event_types: list[str] = []

    async def publish_event(**event):
        event_types.append(event["type"])

    result = await pipeline.run(
        org_id,
        OperatingRunRequest(mode="scan"),
        event_publisher=publish_event,
    )

    assert result.status == "failed"
    assert [execution.status for execution in result.executions] == ["failed"]
    assert result.business_view is None
    assert result.business_surfaces is None
    assert result.semantic_layer is None
    assert result.artifacts is None
    assert result.action_plane is None
    assert result.brief is None
    assert fake_agent.result_count == 0
    assert "business_view.started" not in event_types
    assert event_types[-1] == "operating.failed"


@pytest.mark.asyncio
async def test_operating_pipeline_no_plans_returns_partial_coverage_brief() -> None:
    from app.artifact_plane import ArtifactPlaneRunResult
    from app.operating_pipeline import OperatingPipeline, OperatingRunRequest

    org_id = uuid4()
    captured_runs = []

    async def artifact_recorder(organization_id, *, run):
        captured_runs.append(run)
        return ArtifactPlaneRunResult(organization_id=organization_id, run_id=run.run_id)

    pipeline = OperatingPipeline(
        agent_plane=FakeAgentPlane(org_id, []),
        plan_executor=lambda organization_id, plan, max_preview_rows: None,
        profiler=_profiler,
        memory_recorder=_memory_recorder,
        entity_resolution_runner=_entity_resolution_recorder,
        knowledge_graph_recorder=_knowledge_graph_recorder,
        artifact_recorder=artifact_recorder,
        action_recorder=_action_recorder,
    )

    event_types: list[str] = []

    async def publish_event(**event):
        event_types.append(event["type"])

    result = await pipeline.run(
        org_id,
        OperatingRunRequest(mode="scan"),
        event_publisher=publish_event,
    )

    assert result.status == "partial"
    assert result.errors[0].stage == "agent_plane.planning"
    assert result.errors[0].details["severity"] == "warning"
    assert result.executions == []
    assert result.brief is not None
    assert "no executable findings" in result.brief.headline.lower()
    assert result.business_view is not None
    assert result.business_surfaces is not None
    assert result.semantic_layer is not None
    assert result.artifacts is not None
    assert result.action_plane is not None
    assert captured_runs and captured_runs[0].brief is not None
    assert "agent_plane.no_analysis_plans" in event_types
    assert event_types[-1] == "operating.partial"
