"""End-to-end orchestration for Baseflo operating runs."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import UUID

from app.action_plane.contracts import ActionPlaneRunResult
from app.action_plane.service import sync_actions_from_artifacts
from app.agent_plane.contracts import BriefPackage
from app.agent_plane.graph import AgentPlane, AgentPlaneMaterializedArtifacts, AgentPlaneRunResult
from app.analysis_contracts import AnalysisGraphPlan, AnalysisResultRef
from app.artifact_plane.contracts import ArtifactPlaneRunResult
from app.artifact_plane.service import materialize_operating_artifacts
from app.business_surface_plane import BusinessSurfacePackage, mine_business_surfaces
from app.business_view_plane import BusinessViewPackage, assemble_business_view
from app.chart_grammar_plane import ChartGrammarPackage, build_chart_grammar
from app.communication import RunEventPublisher
from app.data_profiler.contracts import ProfilerRunResult
from app.data_profiler.service import profile_organization
from app.entity_resolution_plane import (
    EntityResolutionRunResult,
    run_entity_resolution_from_surfaces,
)
from app.execution_plane.runtime import execute_analysis_plan
from app.insight_ranking_plane import InsightRankingPackage, rank_operating_insights
from app.knowledge_graph_plane import KnowledgeGraphMaterialization, materialize_knowledge_graph
from app.lineage_plane import LineagePackage, build_lineage_package
from app.memory_plane.contracts import MemoryPlaneRunResult
from app.memory_plane.service import remember_agent_artifacts
from app.operating_pipeline.contracts import (
    OperatingContextSummary,
    OperatingRunError,
    OperatingRunRequest,
    OperatingRunResult,
    OperatingRunStatus,
    PlanExecution,
)
from app.semantic_layer import SemanticLayerPackage, build_semantic_layer


class AgentPlaneLike(Protocol):
    async def run(
        self,
        organization_id: UUID,
        *,
        snapshot_ids: list[UUID] | None = None,
        mode: str = "scan",
        question: str | None = None,
    ) -> AgentPlaneRunResult: ...

    async def run_result_agents(
        self,
        *,
        context: Any,
        business_model: Any,
        patterns: Any,
        analysis_plans: list[AnalysisGraphPlan],
        results: list[AnalysisResultRef],
        mode: str = "scan",
        question: str | None = None,
    ) -> AgentPlaneMaterializedArtifacts: ...


class PlanExecutorLike(Protocol):
    async def __call__(
        self,
        organization_id: UUID,
        plan: AnalysisGraphPlan,
        *,
        max_preview_rows: int,
    ) -> AnalysisResultRef: ...


class ProfilerLike(Protocol):
    async def __call__(
        self,
        organization_id: UUID,
        *,
        snapshot_ids: list[UUID] | None = None,
    ) -> ProfilerRunResult: ...


class MemoryRecorderLike(Protocol):
    async def __call__(
        self,
        organization_id: UUID,
        *,
        business_model: Any,
        asset_roles: list[Any],
        field_roles: list[Any],
        business_graph: Any,
        patterns: Any | None = None,
    ) -> MemoryPlaneRunResult: ...


class ArtifactRecorderLike(Protocol):
    async def __call__(
        self,
        organization_id: UUID,
        *,
        run: OperatingRunResult,
    ) -> ArtifactPlaneRunResult: ...


class BusinessViewBuilderLike(Protocol):
    def __call__(self, run: OperatingRunResult) -> BusinessViewPackage: ...


class BusinessSurfaceMinerLike(Protocol):
    def __call__(self, run: OperatingRunResult) -> BusinessSurfacePackage: ...


class SemanticLayerBuilderLike(Protocol):
    def __call__(self, run: OperatingRunResult) -> SemanticLayerPackage: ...


class ChartGrammarBuilderLike(Protocol):
    def __call__(self, run: OperatingRunResult) -> ChartGrammarPackage: ...


class InsightRankerLike(Protocol):
    def __call__(self, run: OperatingRunResult) -> InsightRankingPackage: ...


class EntityResolutionRunnerLike(Protocol):
    async def __call__(
        self,
        organization_id: UUID,
        package: BusinessSurfacePackage | None,
    ) -> EntityResolutionRunResult: ...


class KnowledgeGraphRecorderLike(Protocol):
    def __call__(
        self,
        organization_id: UUID,
        *,
        business_surfaces: BusinessSurfacePackage | None,
        run_id: UUID | None = None,
    ) -> KnowledgeGraphMaterialization: ...


class LineageBuilderLike(Protocol):
    def __call__(self, run: OperatingRunResult) -> LineagePackage: ...


class ActionRecorderLike(Protocol):
    async def __call__(
        self,
        organization_id: UUID,
        *,
        artifacts: ArtifactPlaneRunResult,
    ) -> ActionPlaneRunResult: ...


class OperatingPipeline:
    """Coordinate profiler, agents, and execution into one run result."""

    def __init__(
        self,
        *,
        agent_plane: AgentPlaneLike | None = None,
        plan_executor: PlanExecutorLike | None = None,
        profiler: ProfilerLike | None = None,
        memory_recorder: MemoryRecorderLike | None = None,
        business_view_builder: BusinessViewBuilderLike | None = None,
        business_surface_miner: BusinessSurfaceMinerLike | None = None,
        semantic_layer_builder: SemanticLayerBuilderLike | None = None,
        chart_grammar_builder: ChartGrammarBuilderLike | None = None,
        insight_ranker: InsightRankerLike | None = None,
        entity_resolution_runner: EntityResolutionRunnerLike | None = None,
        knowledge_graph_recorder: KnowledgeGraphRecorderLike | None = None,
        lineage_builder: LineageBuilderLike | None = None,
        artifact_recorder: ArtifactRecorderLike | None = None,
        action_recorder: ActionRecorderLike | None = None,
    ) -> None:
        self.agent_plane = agent_plane or AgentPlane()
        self.plan_executor = plan_executor or self._default_plan_executor
        self.profiler = profiler or profile_organization
        self.memory_recorder = memory_recorder or remember_agent_artifacts
        self.business_view_builder = business_view_builder or assemble_business_view
        self.business_surface_miner = business_surface_miner or mine_business_surfaces
        self.semantic_layer_builder = semantic_layer_builder or build_semantic_layer
        self.chart_grammar_builder = chart_grammar_builder or build_chart_grammar
        self.insight_ranker = insight_ranker or rank_operating_insights
        self.entity_resolution_runner = entity_resolution_runner or run_entity_resolution_from_surfaces
        self.knowledge_graph_recorder = knowledge_graph_recorder or materialize_knowledge_graph
        self.lineage_builder = lineage_builder or build_lineage_package
        self.artifact_recorder = artifact_recorder or materialize_operating_artifacts
        self.action_recorder = action_recorder or sync_actions_from_artifacts

    async def run(
        self,
        organization_id: UUID,
        request: OperatingRunRequest | None = None,
        event_publisher: RunEventPublisher | None = None,
    ) -> OperatingRunResult:
        req = request or OperatingRunRequest()
        started_at = datetime.now(UTC)
        errors: list[OperatingRunError] = []
        profile: ProfilerRunResult | None = None
        publish = event_publisher or _noop_event_publisher

        await publish(
            type="operating.started",
            stage="operating_pipeline",
            message=f"Operating {req.mode} run started",
            progress=0.02,
            payload={"mode": req.mode, "question": req.question},
        )

        if req.refresh_profile:
            try:
                await publish(
                    type="profiler.started",
                    stage="data_profiler",
                    message="Profiling canonical data",
                    progress=0.08,
                )
                profile = await self.profiler(
                    organization_id,
                    snapshot_ids=req.snapshot_ids,
                )
                await publish(
                    type="profiler.completed",
                    stage="data_profiler",
                    message="Data profile ready",
                    progress=0.18,
                    payload=profile.model_dump(mode="json"),
                )
                if profile.asset_count == 0:
                    no_data_error = OperatingRunError(
                        stage="data_plane",
                        message=(
                            "No canonical business data is ready yet. Connect and sync a source "
                            "before building Business Live."
                        ),
                        details={
                            "code": "NO_CANONICAL_DATA",
                            "action": "connect_source",
                            "snapshot_count": len(profile.snapshot_ids),
                            "quality_flags": profile.quality_flags,
                        },
                    )
                    result = OperatingRunResult(
                        mode=req.mode,
                        organization_id=organization_id,
                        question=req.question,
                        status="failed",
                        started_at=started_at,
                        completed_at=datetime.now(UTC),
                        profile=profile,
                        context_summary=OperatingContextSummary(),
                        errors=[no_data_error],
                    )
                    await publish(
                        type="data_plane.no_canonical_data",
                        stage="data_plane",
                        message=no_data_error.message,
                        progress=0.2,
                        payload=no_data_error.model_dump(mode="json"),
                    )
                    await _publish_operating_terminal(publish, result)
                    return result
            except Exception as exc:
                errors.append(_error("data_profiler", exc))
                await publish(
                    type="profiler.failed",
                    stage="data_profiler",
                    message=str(exc),
                    progress=1,
                )
                result = OperatingRunResult(
                    mode=req.mode,
                    organization_id=organization_id,
                    question=req.question,
                    status="failed",
                    started_at=started_at,
                    completed_at=datetime.now(UTC),
                    errors=errors,
                )
                await _publish_operating_terminal(publish, result)
                return result

        try:
            await publish(
                type="agent_plane.planning_started",
                stage="agent_plane",
                message="Planning analyses from canonical context",
                progress=0.24,
            )
            planning = await self.agent_plane.run(
                organization_id,
                snapshot_ids=req.snapshot_ids,
                mode=req.mode,
                question=req.question,
            )
            await publish(
                type="agent_plane.planning_completed",
                stage="agent_plane",
                message=f"Planned {len(planning.analysis_plans)} analyses",
                progress=0.42,
                payload={
                    "analysis_plan_count": len(planning.analysis_plans),
                    "asset_role_count": len(planning.asset_roles),
                    "field_role_count": len(planning.field_roles),
                },
            )
        except Exception as exc:
            errors.append(_error("agent_plane.planning", exc))
            await publish(
                type="agent_plane.planning_failed",
                stage="agent_plane",
                message=str(exc),
                progress=1,
            )
            result = OperatingRunResult(
                mode=req.mode,
                organization_id=organization_id,
                question=req.question,
                status="failed",
                started_at=started_at,
                completed_at=datetime.now(UTC),
                profile=profile,
                errors=errors,
            )
            await _publish_operating_terminal(publish, result)
            return result

        if not planning.analysis_plans:
            no_plan_error = OperatingRunError(
                stage="agent_plane.planning",
                message=(
                    "No executable analysis plans were proposed from the current "
                    "canonical context."
                ),
                details={
                    "severity": "warning",
                    "mode": req.mode,
                    "question": req.question,
                    "asset_count": len(planning.context.assets),
                    "field_count": sum(len(asset.fields) for asset in planning.context.assets),
                },
            )
            errors.append(no_plan_error)
            await publish(
                type="agent_plane.no_analysis_plans",
                stage="agent_plane",
                message=no_plan_error.message,
                progress=0.43,
                payload=no_plan_error.model_dump(mode="json"),
            )

        memory_writes = []
        try:
            await publish(
                type="memory.started",
                stage="memory_plane",
                message="Recording durable business memory",
                progress=0.48,
            )
            memory_result = await self.memory_recorder(
                organization_id,
                business_model=planning.business_model,
                asset_roles=planning.asset_roles,
                field_roles=planning.field_roles,
                business_graph=planning.business_graph,
                patterns=planning.patterns,
            )
            memory_writes = memory_result.writes
            await publish(
                type="memory.completed",
                stage="memory_plane",
                message=f"Recorded {len(memory_writes)} memory writes",
                progress=0.55,
                payload={"memory_write_count": len(memory_writes)},
            )
        except Exception as exc:
            errors.append(_error("memory_plane", exc))
            await publish(
                type="memory.failed",
                stage="memory_plane",
                message=str(exc),
                progress=0.55,
            )

        await publish(
            type="execution.started",
            stage="execution_plane",
            message=f"Executing {len(planning.analysis_plans)} analysis plans",
            progress=0.6,
        )
        executions = await self._execute_plans(
            organization_id,
            planning.analysis_plans,
            max_preview_rows=req.max_preview_rows,
            max_parallel_plans=req.max_parallel_plans,
            event_publisher=publish,
        )
        await publish(
            type="execution.completed",
            stage="execution_plane",
            message="Analysis execution finished",
            progress=0.76,
            payload={
                "completed": len([execution for execution in executions if execution.status == "completed"]),
                "failed": len([execution for execution in executions if execution.status == "failed"]),
            },
        )
        errors.extend(
            execution.error
            for execution in executions
            if execution.error is not None
        )

        successful_results = [
            execution.result
            for execution in executions
            if execution.result is not None
        ]
        materialized: AgentPlaneMaterializedArtifacts | None = None
        if successful_results:
            try:
                await publish(
                    type="agent_plane.materialization_started",
                    stage="agent_plane",
                    message="Materializing interpretations, charts, actions, and narratives",
                    progress=0.82,
                )
                materialized = await self.agent_plane.run_result_agents(
                    context=planning.context,
                    business_model=planning.business_model,
                    patterns=planning.patterns,
                    analysis_plans=planning.analysis_plans,
                    results=successful_results,
                    mode=req.mode,
                    question=req.question,
                )
                await publish(
                    type="agent_plane.materialization_completed",
                    stage="agent_plane",
                    message="Operating artifacts are ready",
                    progress=0.95,
                    payload={
                        "interpretation_count": len(materialized.interpretations),
                        "chart_count": len(materialized.chart_specs),
                        "action_batch_count": len(materialized.action_batches),
                        "narrative_count": len(materialized.narratives),
                    },
                )
            except Exception as exc:
                errors.append(_error("agent_plane.result_agents", exc))
                await publish(
                    type="agent_plane.materialization_failed",
                    stage="agent_plane",
                    message=str(exc),
                    progress=0.95,
                )

        status: OperatingRunStatus = "completed" if not errors else "partial"
        if not successful_results and planning.analysis_plans:
            status = "failed"

        result = OperatingRunResult(
            mode=req.mode,
            organization_id=organization_id,
            question=req.question,
            status=status,
            started_at=started_at,
            completed_at=datetime.now(UTC),
            profile=profile,
            context_summary=_context_summary(planning),
            business_model=planning.business_model,
            asset_roles=planning.asset_roles,
            field_roles=planning.field_roles,
            business_graph=planning.business_graph,
            patterns=planning.patterns,
            analysis_plans=planning.analysis_plans,
            executions=executions,
            memory_writes=memory_writes,
            interpretations=materialized.interpretations if materialized else [],
            chart_specs=materialized.chart_specs if materialized else [],
            action_batches=materialized.action_batches if materialized else [],
            narratives=materialized.narratives if materialized else [],
            brief=(
                materialized.brief
                if materialized
                else _coverage_brief(planning, req=req, errors=errors)
            ),
            errors=errors,
        )
        if result.status == "failed":
            await _publish_operating_terminal(publish, result)
            return result
        try:
            await publish(
                type="business_view.started",
                stage="business_view_plane",
                message="Generating operating-room business view",
                progress=0.96,
            )
            business_view = self.business_view_builder(result)
            result = result.model_copy(update={"business_view": business_view})
            await publish(
                type="business_view.completed",
                stage="business_view_plane",
                message=f"Generated {len(business_view.sections)} business sections",
                progress=0.965,
                payload={
                    "section_count": len(business_view.sections),
                    "entity_view_count": len(business_view.entity_views),
                },
            )
        except Exception as exc:
            errors.append(_error("business_view_plane", exc))
            result = result.model_copy(
                update={
                    "status": "partial" if result.status == "completed" else result.status,
                    "errors": errors,
                }
            )
            await publish(
                type="business_view.failed",
                stage="business_view_plane",
                message=str(exc),
                progress=0.965,
            )
        try:
            await publish(
                type="business_surfaces.started",
                stage="business_surface_plane",
                message="Mining generated operating surfaces",
                progress=0.967,
            )
            business_surfaces = self.business_surface_miner(result)
            result = result.model_copy(update={"business_surfaces": business_surfaces})
            await publish(
                type="business_surfaces.completed",
                stage="business_surface_plane",
                message=f"Mined {len(business_surfaces.surfaces)} operating surfaces",
                progress=0.969,
                payload={
                    "surface_count": len(business_surfaces.surfaces),
                    "candidate_view_count": sum(
                        len(surface.candidate_views) for surface in business_surfaces.surfaces
                    ),
                    "cohort_count": sum(
                        len(surface.cohorts) for surface in business_surfaces.surfaces
                    ),
                    "action_pack_count": sum(
                        len(surface.action_packs) for surface in business_surfaces.surfaces
                    ),
                },
            )
        except Exception as exc:
            errors.append(_error("business_surface_plane", exc))
            result = result.model_copy(
                update={
                    "status": "partial" if result.status == "completed" else result.status,
                    "errors": errors,
                }
            )
            await publish(
                type="business_surfaces.failed",
                stage="business_surface_plane",
                message=str(exc),
                progress=0.969,
            )
        try:
            await publish(
                type="semantic_layer.started",
                stage="semantic_layer",
                message="Building governed semantic layer",
                progress=0.97,
            )
            semantic_layer = self.semantic_layer_builder(result)
            result = result.model_copy(update={"semantic_layer": semantic_layer})
            await publish(
                type="semantic_layer.completed",
                stage="semantic_layer",
                message=(
                    f"Semantic layer ready: {len(semantic_layer.entities)} entities, "
                    f"{len(semantic_layer.metrics)} metrics"
                ),
                progress=0.971,
                payload={
                    "entity_count": len(semantic_layer.entities),
                    "dimension_count": len(semantic_layer.dimensions),
                    "measure_count": len(semantic_layer.measures),
                    "metric_count": len(semantic_layer.metrics),
                },
            )
        except Exception as exc:
            errors.append(_error("semantic_layer", exc))
            result = result.model_copy(
                update={
                    "status": "partial" if result.status == "completed" else result.status,
                    "errors": errors,
                }
            )
            await publish(
                type="semantic_layer.failed",
                stage="semantic_layer",
                message=str(exc),
                progress=0.971,
            )
        try:
            await publish(
                type="chart_grammar.started",
                stage="chart_grammar_plane",
                message="Generating Vega-Lite chart grammar",
                progress=0.972,
            )
            chart_grammar = self.chart_grammar_builder(result)
            result = result.model_copy(update={"chart_grammar": chart_grammar})
            await publish(
                type="chart_grammar.completed",
                stage="chart_grammar_plane",
                message=f"Generated {len(chart_grammar.charts)} Vega-Lite charts",
                progress=0.973,
                payload={"chart_count": len(chart_grammar.charts)},
            )
        except Exception as exc:
            errors.append(_error("chart_grammar_plane", exc))
            result = result.model_copy(
                update={
                    "status": "partial" if result.status == "completed" else result.status,
                    "errors": errors,
                }
            )
            await publish(
                type="chart_grammar.failed",
                stage="chart_grammar_plane",
                message=str(exc),
                progress=0.973,
            )
        try:
            await publish(
                type="insight_ranking.started",
                stage="insight_ranking_plane",
                message="Ranking insights, cohorts, and action packs",
                progress=0.974,
            )
            insight_ranking = self.insight_ranker(result)
            result = result.model_copy(update={"insight_ranking": insight_ranking})
            await publish(
                type="insight_ranking.completed",
                stage="insight_ranking_plane",
                message=f"Ranked {len(insight_ranking.ranked)} operating items",
                progress=0.975,
                payload={"ranked_count": len(insight_ranking.ranked)},
            )
        except Exception as exc:
            errors.append(_error("insight_ranking_plane", exc))
            result = result.model_copy(
                update={
                    "status": "partial" if result.status == "completed" else result.status,
                    "errors": errors,
                }
            )
            await publish(
                type="insight_ranking.failed",
                stage="insight_ranking_plane",
                message=str(exc),
                progress=0.975,
            )
        try:
            await publish(
                type="entity_resolution.started",
                stage="entity_resolution_plane",
                message="Executing Splink-backed entity resolution",
                progress=0.976,
            )
            entity_resolution = await self.entity_resolution_runner(
                organization_id,
                result.business_surfaces,
            )
            result = result.model_copy(update={"entity_resolution": entity_resolution})
            await publish(
                type="entity_resolution.completed",
                stage="entity_resolution_plane",
                message=f"Resolved {len(entity_resolution.executions)} entity-resolution jobs",
                progress=0.977,
                payload={
                    "plan_count": len(entity_resolution.plans),
                    "completed_count": len(
                        [
                            execution
                            for execution in entity_resolution.executions
                            if execution.status == "completed"
                        ]
                    ),
                    "engine": "splink",
                },
            )
        except Exception as exc:
            errors.append(_error("entity_resolution_plane", exc))
            result = result.model_copy(
                update={
                    "status": "partial" if result.status == "completed" else result.status,
                    "errors": errors,
                }
            )
            await publish(
                type="entity_resolution.failed",
                stage="entity_resolution_plane",
                message=str(exc),
                progress=0.977,
            )
        try:
            await publish(
                type="knowledge_graph.started",
                stage="knowledge_graph_plane",
                message="Materializing Kuzu insight graph",
                progress=0.978,
            )
            knowledge_graph = self.knowledge_graph_recorder(
                organization_id,
                business_surfaces=result.business_surfaces,
                run_id=result.run_id,
            )
            result = result.model_copy(update={"knowledge_graph": knowledge_graph})
            await publish(
                type="knowledge_graph.completed",
                stage="knowledge_graph_plane",
                message=(
                    f"Kuzu graph {knowledge_graph.status}: "
                    f"{knowledge_graph.node_count} nodes, {knowledge_graph.edge_count} edges"
                ),
                progress=0.979,
                payload=knowledge_graph.model_dump(mode="json"),
            )
        except Exception as exc:
            errors.append(_error("knowledge_graph_plane", exc))
            result = result.model_copy(
                update={
                    "status": "partial" if result.status == "completed" else result.status,
                    "errors": errors,
                }
            )
            await publish(
                type="knowledge_graph.failed",
                stage="knowledge_graph_plane",
                message=str(exc),
                progress=0.979,
            )
        try:
            await publish(
                type="lineage.started",
                stage="lineage_plane",
                message="Building OpenLineage-style lineage",
                progress=0.98,
            )
            lineage = self.lineage_builder(result)
            result = result.model_copy(update={"lineage": lineage})
            await publish(
                type="lineage.completed",
                stage="lineage_plane",
                message=f"Built {len(lineage.runs)} lineage runs",
                progress=0.981,
                payload={
                    "run_count": len(lineage.runs),
                    "dataset_count": len(lineage.datasets),
                },
            )
        except Exception as exc:
            errors.append(_error("lineage_plane", exc))
            result = result.model_copy(
                update={
                    "status": "partial" if result.status == "completed" else result.status,
                    "errors": errors,
                }
            )
            await publish(
                type="lineage.failed",
                stage="lineage_plane",
                message=str(exc),
                progress=0.981,
            )
        try:
            await publish(
                type="artifact_plane.started",
                stage="artifact_plane",
                message="Materializing durable product artifacts",
                progress=0.982,
            )
            artifacts = await self.artifact_recorder(organization_id, run=result)
            result = result.model_copy(update={"artifacts": artifacts})
            await publish(
                type="artifact_plane.completed",
                stage="artifact_plane",
                message=f"Materialized {len(artifacts.artifacts)} artifacts",
                progress=0.99,
                payload={
                    "artifact_count": len(artifacts.artifacts),
                    "created_count": artifacts.created_count,
                    "updated_count": artifacts.updated_count,
                    "unchanged_count": artifacts.unchanged_count,
                },
            )
        except Exception as exc:
            errors.append(_error("artifact_plane", exc))
            result = result.model_copy(
                update={
                    "status": "partial" if result.status == "completed" else result.status,
                    "errors": errors,
                }
            )
            await publish(
                type="artifact_plane.failed",
                stage="artifact_plane",
                message=str(exc),
                progress=0.99,
            )
        if result.artifacts is not None:
            try:
                await publish(
                    type="action_plane.started",
                    stage="action_plane",
                    message="Syncing supported action artifacts",
                    progress=0.995,
                )
                action_plane = await self.action_recorder(
                    organization_id,
                    artifacts=result.artifacts,
                )
                result = result.model_copy(update={"action_plane": action_plane})
                await publish(
                    type="action_plane.completed",
                    stage="action_plane",
                    message=f"Synced {len(action_plane.actions)} actions",
                    progress=0.998,
                    payload={
                        "action_count": len(action_plane.actions),
                        "created_count": action_plane.created_count,
                        "updated_count": action_plane.updated_count,
                        "skipped_count": action_plane.skipped_count,
                    },
                )
            except Exception as exc:
                errors.append(_error("action_plane", exc))
                result = result.model_copy(
                    update={
                        "status": "partial" if result.status == "completed" else result.status,
                        "errors": errors,
                    }
                )
                await publish(
                    type="action_plane.failed",
                    stage="action_plane",
                    message=str(exc),
                    progress=0.998,
                )
        await _publish_operating_terminal(publish, result)
        return result

    async def _execute_plans(
        self,
        organization_id: UUID,
        plans: list[AnalysisGraphPlan],
        *,
        max_preview_rows: int,
        max_parallel_plans: int,
        event_publisher: RunEventPublisher,
    ) -> list[PlanExecution]:
        semaphore = asyncio.Semaphore(max_parallel_plans)

        async def _one(plan: AnalysisGraphPlan) -> PlanExecution:
            try:
                async with semaphore:
                    await event_publisher(
                        type="execution.plan_started",
                        stage="execution_plane",
                        message=f"Executing {plan.graph_id}",
                        payload={"graph_id": plan.graph_id, "hypothesis_id": plan.hypothesis_id},
                    )
                    result = await self.plan_executor(
                        organization_id,
                        plan,
                        max_preview_rows=max_preview_rows,
                    )
                await event_publisher(
                    type="execution.plan_completed",
                    stage="execution_plane",
                    message=f"Executed {plan.graph_id}",
                    payload={
                        "graph_id": plan.graph_id,
                        "hypothesis_id": plan.hypothesis_id,
                        "row_count": result.row_count,
                    },
                )
                return PlanExecution(
                    graph_id=plan.graph_id,
                    hypothesis_id=plan.hypothesis_id,
                    plan=plan,
                    status="completed",
                    result=result,
                )
            except Exception as exc:
                await event_publisher(
                    type="execution.plan_failed",
                    stage="execution_plane",
                    message=f"{plan.graph_id} failed: {exc}",
                    payload={"graph_id": plan.graph_id, "hypothesis_id": plan.hypothesis_id},
                )
                return PlanExecution(
                    graph_id=plan.graph_id,
                    hypothesis_id=plan.hypothesis_id,
                    plan=plan,
                    status="failed",
                    error=_error("execution_plane", exc, graph_id=plan.graph_id),
                )

        return list(await asyncio.gather(*[_one(plan) for plan in plans]))

    async def _default_plan_executor(
        self,
        organization_id: UUID,
        plan: AnalysisGraphPlan,
        *,
        max_preview_rows: int,
    ) -> AnalysisResultRef:
        return await execute_analysis_plan(
            organization_id,
            plan,
            max_preview_rows=max_preview_rows,
        )


async def run_operating_pipeline(
    organization_id: UUID,
    request: OperatingRunRequest | None = None,
    event_publisher: RunEventPublisher | None = None,
) -> OperatingRunResult:
    return await OperatingPipeline().run(organization_id, request, event_publisher=event_publisher)


def _context_summary(planning: AgentPlaneRunResult) -> OperatingContextSummary:
    return OperatingContextSummary(
        snapshot_count=len(planning.context.snapshots),
        asset_count=len(planning.context.assets),
        field_count=sum(len(asset.fields) for asset in planning.context.assets),
        graph_edge_count=len(planning.context.graph_edges),
        row_count=sum(asset.row_count for asset in planning.context.assets),
    )


def _error(stage: str, exc: Exception, **details: Any) -> OperatingRunError:
    error_details = dict(details)
    maybe_details = getattr(exc, "details", None)
    if isinstance(maybe_details, dict):
        error_details.update(maybe_details)
    return OperatingRunError(
        stage=stage,
        message=str(exc),
        details=error_details,
    )


def _coverage_brief(
    planning: AgentPlaneRunResult,
    *,
    req: OperatingRunRequest,
    errors: list[OperatingRunError],
) -> BriefPackage | None:
    if planning.analysis_plans:
        return None
    asset_count = len(planning.context.assets)
    field_count = sum(len(asset.fields) for asset in planning.context.assets)
    row_count = sum(asset.row_count for asset in planning.context.assets)
    mode_label = "Ask" if req.mode == "ask" else "Operating"
    return BriefPackage(
        headline=f"{mode_label} coverage is ready, but no executable findings were produced",
        summary_points=[
            f"Baseflo understood {asset_count} assets, {field_count} fields, and {row_count} rows.",
            "It built the business view and source coverage surfaces from the connected data.",
            "No analysis graph was safe enough to execute, so no insight or action was fabricated.",
        ],
        urgent_artifact_ids=[],
        why=(
            "This brief is a coverage note: Baseflo had semantic context but no "
            "validated executable analysis plan for this run."
        ),
    )


async def _publish_operating_terminal(
    publish: RunEventPublisher,
    result: OperatingRunResult,
) -> None:
    event_type = {
        "completed": "operating.completed",
        "partial": "operating.partial",
        "failed": "operating.failed",
    }[result.status]
    await publish(
        type=event_type,
        stage="operating_pipeline",
        message=f"Operating run {result.status}",
        progress=1,
        payload={"status": result.status, "run_id": str(result.run_id)},
    )


async def _noop_event_publisher(
    *,
    type: str,
    stage: str,
    message: str,
    progress: float | None = None,
    payload: dict[str, Any] | None = None,
) -> None:
    _ = (type, stage, message, progress, payload)
