"""Artifact-centric workspace build pipeline.

Replaces the 8-stage pydantic_graph with an explicit 4-agent DAG:
  SourceAgent(s) in parallel → ReconciliationAgent → SchemaAgent → InsightAgent
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import select

from app.agents.insight_agent.agent import SPEC as INSIGHT_AGENT_SPEC
from app.agents.insight_agent.types import InsightAgentInput
from app.agents.reconciliation_agent.agent import SPEC as RECONCILIATION_AGENT_SPEC
from app.agents.reconciliation_agent.types import ReconciliationAgentInput
from app.agents.runtime import AgentRuntime
from app.agents.schema_agent.agent import SPEC as SCHEMA_AGENT_SPEC
from app.agents.schema_agent.types import SchemaAgentInput
from app.agents.source_agent.agent import SPEC as SOURCE_AGENT_SPEC
from app.agents.source_agent.types import SourceAgentInput
from app.artifacts import ArtifactProvenance, ArtifactStore, SourceMap
from app.connectors.base import ConnectorToken
from app.connectors.registry import ConnectorRegistry
from app.core.context import get_tenant_ctx
from app.core.crypto.envelope import EnvelopeCrypto
from app.core.crypto.kms import get_kms_client
from app.core.errors import BasefloError
from app.db.models import Project
from app.db.models.connector import Connector
from app.db.session import open_session
from app.engines.schema.compatibility import validate as ir_validate
from app.observability.logging import get_logger
from app.orchestration.events.publisher import emit_event
from app.orchestration.events.types import (
    AgentCompletePayload,
    AgentStartPayload,
    ArtifactReadyPayload,
    EventType,
)
from app.repositories.connector_tokens import ConnectorTokenRepository
from app.services.connector_tokens.vault import TokenVault
from app.services.data_plane.backfill_runner import BackfillRunner
from app.services.data_plane.canonical_upserter import CanonicalUpserter
from app.services.data_plane.id_resolver import IdResolver
from app.services.data_plane.schema_applier import SchemaApplier

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession

    from app.artifacts import Artifact
    from app.artifacts.types import EntityGraph, InsightBoard
    from app.connectors.base import Connector as ConnectorRuntime
    from app.engines.schema.ir import SchemaIR
    from app.services.data_plane.backfill_runner import ConnectorReader

logger = get_logger("pipeline.build")


@dataclass(frozen=True)
class BuildRequest:
    project_id: UUID
    connector_ids: list[UUID]
    business_description: str


@dataclass(frozen=True)
class BuildResult:
    project_id: UUID
    source_map_artifact_ids: list[UUID]
    entity_graph_artifact_id: UUID
    schema_ir_artifact_id: UUID
    insight_board_artifact_id: UUID | None
    schema_applied: bool
    backfilled: bool


class BuildPipeline:
    """Explicit DAG builder. No graph framework needed."""

    def __init__(
        self,
        session: AsyncSession,
        runtime: AgentRuntime | None = None,
        conversation_id: UUID | None = None,
    ) -> None:
        self._session = session
        self._runtime = runtime or AgentRuntime()
        self._store = ArtifactStore(session)
        self._vault = TokenVault(
            repo=ConnectorTokenRepository(session),
            crypto=EnvelopeCrypto(kms=get_kms_client(), kek_alias="local-default"),
        )
        self._conversation_id = conversation_id

    async def run(self, request: BuildRequest) -> BuildResult:
        tenant_id = get_tenant_ctx().organization_id
        logger.info(
            "build_pipeline_started",
            project_id=str(request.project_id),
            connectors=len(request.connector_ids),
        )

        # ------------------------------------------------------------------
        # 1. SourceAgent — one per connector, parallel
        # ------------------------------------------------------------------
        await self._emit_agent_start("source", 0, "Discovering data sources…")
        source_tasks = [
            self._run_source_agent(request.project_id, cid, request.business_description)
            for cid in request.connector_ids
        ]
        source_results = await asyncio.gather(*source_tasks, return_exceptions=True)
        source_artifacts: list[UUID] = []
        source_maps: list[SourceMap] = []
        for i, res in enumerate(source_results):
            if isinstance(res, BaseException):
                cid = request.connector_ids[i]
                logger.error("source_agent_failed", connector_id=str(cid), error=str(res))
                raise BasefloError(
                    error_code="BF-BUILD-001",
                    message=f"SourceAgent failed for connector {cid}: {res}",
                    status_code=500,
                ) from res
            source_artifacts.append(res.header.artifact_id)
            source_maps.append(res.payload)
        await self._emit_agent_complete("source", 0)

        # ------------------------------------------------------------------
        # 2. ReconciliationAgent — all SourceMaps together
        # ------------------------------------------------------------------
        await self._emit_agent_start("reconciliation", 1, "Reconciling entities…")
        recon_artifact = await self._run_reconciliation_agent(
            request.project_id, request.business_description, source_maps
        )
        entity_graph = recon_artifact.payload
        await self._emit_agent_complete("reconciliation", 1)

        # ------------------------------------------------------------------
        # 3. SchemaAgent — EntityGraph → SchemaIR
        # ------------------------------------------------------------------
        await self._emit_agent_start("schema", 2, "Designing schema…")
        schema_artifact = await self._run_schema_agent(
            request.project_id, request.business_description, entity_graph
        )
        schema_ir = schema_artifact.payload
        await self._emit_agent_complete("schema", 2)

        # Deterministic validation (no LLM)
        report = ir_validate(schema_ir)
        if not report.passed:
            raise BasefloError(
                error_code="BF-BUILD-005",
                message=f"SchemaAgent produced invalid SchemaIR: {report.summary()}",
                status_code=500,
            )

        # ------------------------------------------------------------------
        # 4. Apply schema + backfill (deterministic, not an agent)
        # ------------------------------------------------------------------
        project = await self._session.get(Project, request.project_id)
        if project is None:
            raise BasefloError(
                error_code="BF-BUILD-002",
                message=f"Project {request.project_id} not found.",
                status_code=404,
            )

        schema_applied = False
        backfilled = False
        try:
            applier = SchemaApplier(control_session=self._session)
            await applier.apply_initial(project=project, ir=schema_ir)
            schema_applied = True

            upserter = CanonicalUpserter(
                tenant_session=self._session,
                schema_name=project.tenant_data_schema_name or "",
                id_resolver=IdResolver(session=self._session),
            )
            runner = BackfillRunner(upserter=upserter)
            connectors: dict[str, tuple[ConnectorReader, ConnectorToken]] = {}
            for cid in request.connector_ids:
                result = await self._session.execute(
                    select(Connector).where(Connector.id == cid)
                )
                connector_model = result.scalar_one_or_none()
                if connector_model is None:
                    continue
                connector_instance, token = await self._load_connector(connector_model)
                if connector_instance is None or token is None:
                    continue
                connectors[token.connector_name] = (connector_instance, token)
            await runner.backfill_ir(
                organization_id=tenant_id,
                project_id=project.id,
                ir=schema_ir,
                connectors=connectors,
            )
            backfilled = True
        except Exception as exc:  # noqa: BLE001 - data-plane failures are non-blocking here
            logger.error("data_plane_failure", error=str(exc))
            # Schema/backfill failures are logged but don't block insight generation.
            # The workspace is still usable for querying source data.

        # ------------------------------------------------------------------
        # 5. InsightAgent — initial KPIs
        # ------------------------------------------------------------------
        insight_artifact_id: UUID | None = None
        try:
            await self._emit_agent_start("insight", 3, "Generating insights…")
            insight_artifact = await self._run_insight_agent(
                request.project_id, request.business_description, schema_ir, entity_graph
            )
            insight_artifact_id = insight_artifact.header.artifact_id
            await self._emit_agent_complete("insight", 3)
        except Exception as exc:  # noqa: BLE001 - insight generation is best-effort for v1
            logger.error("insight_agent_failed", error=str(exc))
            # Insight failures are non-blocking for v1.

        logger.info("build_pipeline_finished", project_id=str(request.project_id))

        return BuildResult(
            project_id=request.project_id,
            source_map_artifact_ids=source_artifacts,
            entity_graph_artifact_id=recon_artifact.header.artifact_id,
            schema_ir_artifact_id=schema_artifact.header.artifact_id,
            insight_board_artifact_id=insight_artifact_id,
            schema_applied=schema_applied,
            backfilled=backfilled,
        )

    # ------------------------------------------------------------------
    # Connector loading — shared helper
    # ------------------------------------------------------------------

    async def _load_connector(
        self, connector_model: Connector
    ) -> tuple[ConnectorRuntime | None, ConnectorToken | None]:
        """Load a connector instance + its decrypted token."""
        try:
            connector_cls = ConnectorRegistry.get(connector_model.kind)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "connector_kind_not_registered",
                connector_id=str(connector_model.id),
                kind=connector_model.kind,
                exc=str(exc),
            )
            return (None, None)

        # Vault key is the connector id, not a non-existent token_id column.
        stored = await self._vault.get(connector_model.id)
        if stored is None:
            logger.warning(
                "connector_has_no_active_token",
                connector_id=str(connector_model.id),
                kind=connector_model.kind,
            )
            return (None, None)

        metadata: dict[str, object] = {**dict(connector_model.config), **stored.payload}
        if stored.expires_at is not None:
            metadata.setdefault("expires_at", stored.expires_at.isoformat())

        token = ConnectorToken(
            connector_name=connector_model.kind,
            token_id=stored.token_id,
            metadata=metadata,
        )
        return (connector_cls(), token)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _run_source_agent(
        self, project_id: UUID, connector_id: UUID, business_description: str
    ) -> Artifact[SourceMap]:
        result = await self._session.execute(
            select(Connector).where(Connector.id == connector_id)
        )
        connector_model = result.scalar_one_or_none()
        if connector_model is None:
            raise BasefloError(
                error_code="BF-BUILD-003",
                message=f"Connector {connector_id} not found.",
                status_code=404,
            )

        connector_instance, token = await self._load_connector(connector_model)
        if connector_instance is None or token is None:
            raise BasefloError(
                error_code="BF-BUILD-004",
                message=f"Connector {connector_id} has no active token.",
                status_code=500,
            )

        raw_schema = await connector_instance.introspect_schema(token)

        # Collect samples
        sample_rows: list[dict[str, object]] = []
        for table in raw_schema.tables:
            rows = await connector_instance.sample_rows(token, table.name, 5)
            sample_rows.extend(row.values for row in rows)

        agent_input = SourceAgentInput(
            connector_id=str(connector_id),
            connector_kind=connector_model.kind,
            business_description=business_description,
            raw_schema=raw_schema.model_dump(mode="json"),
            sample_rows=sample_rows,
        )

        tenant_id = get_tenant_ctx().organization_id
        started_at = datetime.now(UTC)
        agent_result = await self._runtime.run(
            spec=SOURCE_AGENT_SPEC,
            input_payload=agent_input,
            tenant_id=tenant_id,
        )
        finished_at = datetime.now(UTC)

        provenance = ArtifactProvenance(
            agent_name=SOURCE_AGENT_SPEC.name,
            model_name=agent_result.model_name_used,
            tokens_prompt=agent_result.usage.input_tokens + agent_result.usage.cache_read_tokens,
            tokens_completion=agent_result.usage.output_tokens,
            latency_ms=agent_result.duration_ms,
            started_at=started_at,
            finished_at=finished_at,
        )

        artifact = await self._store.save(
            project_id=project_id,
            artifact_type="source_map",
            payload=agent_result.output.source_map,
            produced_by=SOURCE_AGENT_SPEC.name,
            provenance=provenance,
        )
        await self._emit_artifact_ready("source_map", artifact.header.artifact_id)
        return artifact

    async def _run_reconciliation_agent(
        self, project_id: UUID, business_description: str, source_maps: list[SourceMap]
    ) -> Artifact[EntityGraph]:
        agent_input = ReconciliationAgentInput(
            business_description=business_description,
            source_maps=[sm.model_dump(mode="json") for sm in source_maps],
        )

        tenant_id = get_tenant_ctx().organization_id
        started_at = datetime.now(UTC)
        result = await self._runtime.run(
            spec=RECONCILIATION_AGENT_SPEC,
            input_payload=agent_input,
            tenant_id=tenant_id,
        )
        finished_at = datetime.now(UTC)

        provenance = ArtifactProvenance(
            agent_name=RECONCILIATION_AGENT_SPEC.name,
            model_name=result.model_name_used,
            tokens_prompt=result.usage.input_tokens + result.usage.cache_read_tokens,
            tokens_completion=result.usage.output_tokens,
            latency_ms=result.duration_ms,
            started_at=started_at,
            finished_at=finished_at,
        )

        artifact = await self._store.save(
            project_id=project_id,
            artifact_type="entity_graph",
            payload=result.output.entity_graph,
            produced_by=RECONCILIATION_AGENT_SPEC.name,
            provenance=provenance,
        )
        await self._emit_artifact_ready("entity_graph", artifact.header.artifact_id)
        return artifact

    async def _run_schema_agent(
        self, project_id: UUID, business_description: str, entity_graph: EntityGraph
    ) -> Artifact[SchemaIR]:
        agent_input = SchemaAgentInput(
            business_description=business_description,
            entity_graph=entity_graph.model_dump(mode="json"),
        )

        tenant_id = get_tenant_ctx().organization_id
        started_at = datetime.now(UTC)
        result = await self._runtime.run(
            spec=SCHEMA_AGENT_SPEC,
            input_payload=agent_input,
            tenant_id=tenant_id,
        )
        finished_at = datetime.now(UTC)

        provenance = ArtifactProvenance(
            agent_name=SCHEMA_AGENT_SPEC.name,
            model_name=result.model_name_used,
            tokens_prompt=result.usage.input_tokens + result.usage.cache_read_tokens,
            tokens_completion=result.usage.output_tokens,
            latency_ms=result.duration_ms,
            started_at=started_at,
            finished_at=finished_at,
        )

        artifact = await self._store.save(
            project_id=project_id,
            artifact_type="schema_ir",
            payload=result.output.schema_ir,
            produced_by=SCHEMA_AGENT_SPEC.name,
            provenance=provenance,
        )
        await self._emit_artifact_ready("schema_ir", artifact.header.artifact_id)
        return artifact

    async def _emit_agent_start(self, agent_name: str, stage_index: int, label: str) -> None:
        if self._conversation_id is None:
            return
        async with open_session() as session:
            await emit_event(
                session,
                conversation_id=self._conversation_id,
                payload=AgentStartPayload(
                    type=EventType.AGENT_START,
                    agent_name=agent_name,
                    stage_index=stage_index,
                    label=label,
                ),
            )

    async def _emit_agent_complete(self, agent_name: str, stage_index: int) -> None:
        if self._conversation_id is None:
            return
        async with open_session() as session:
            await emit_event(
                session,
                conversation_id=self._conversation_id,
                payload=AgentCompletePayload(
                    type=EventType.AGENT_COMPLETE,
                    agent_name=agent_name,
                    stage_index=stage_index,
                    duration_ms=0,
                ),
            )

    async def _emit_artifact_ready(self, artifact_kind: str, artifact_id: UUID) -> None:
        if self._conversation_id is None:
            return
        async with open_session() as session:
            await emit_event(
                session,
                conversation_id=self._conversation_id,
                payload=ArtifactReadyPayload(
                    type=EventType.ARTIFACT_READY,
                    artifact_kind=artifact_kind,
                    artifact_id=artifact_id,
                ),
            )

    async def _run_insight_agent(
        self,
        project_id: UUID,
        business_description: str,
        schema_ir: SchemaIR,
        entity_graph: EntityGraph,
    ) -> Artifact[InsightBoard]:
        agent_input = InsightAgentInput(
            business_description=business_description,
            schema_ir=schema_ir.model_dump(mode="json"),
            entity_graph=entity_graph.model_dump(mode="json"),
        )

        tenant_id = get_tenant_ctx().organization_id
        started_at = datetime.now(UTC)
        result = await self._runtime.run(
            spec=INSIGHT_AGENT_SPEC,
            input_payload=agent_input,
            tenant_id=tenant_id,
        )
        finished_at = datetime.now(UTC)

        provenance = ArtifactProvenance(
            agent_name=INSIGHT_AGENT_SPEC.name,
            model_name=result.model_name_used,
            tokens_prompt=result.usage.input_tokens + result.usage.cache_read_tokens,
            tokens_completion=result.usage.output_tokens,
            latency_ms=result.duration_ms,
            started_at=started_at,
            finished_at=finished_at,
        )

        artifact = await self._store.save(
            project_id=project_id,
            artifact_type="insight_board",
            payload=result.output.insight_board,
            produced_by=INSIGHT_AGENT_SPEC.name,
            provenance=provenance,
        )
        await self._emit_artifact_ready("insight_board", artifact.header.artifact_id)
        return artifact
