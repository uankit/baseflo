"""RefinementSaga — v1 artifact-centric refinement.

Steps:
  1. Load parent project_version → SchemaIR + KPIs.
  2. Load latest EntityGraph artifact.
  3. Run SchemaAgent with user request + EntityGraph → new SchemaIR.
  4. Validate with deterministic ir_validate.
  5. Persist child as new project_versions row.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.agents.runtime import AgentRuntime
from app.agents.schema_agent.agent import SPEC as SCHEMA_AGENT_SPEC
from app.agents.schema_agent.types import SchemaAgentInput, SchemaAgentOutput
from app.agents.specialists.kpi_planner.types import KPIDefinition
from app.artifacts import ArtifactStore
from app.artifacts.types import EntityGraph
from app.core.context import get_tenant_ctx
from app.core.errors import BasefloError
from app.core.ids import new_uuid7
from app.db.session import open_session
from app.engines.schema.compatibility import validate as ir_validate
from app.engines.schema.ir import SchemaIR
from app.observability.logging import get_logger

__all__ = ["RefinementResult", "RefinementSaga"]

logger = get_logger("orchestration.sagas.refinement")


class RefinementResult(BaseModel):
    """One refinement run's outcome."""

    model_config = ConfigDict(extra="forbid")
    project_id: UUID
    parent_version_id: UUID | None
    new_version_id: UUID | None = None
    diff_summary: str | None = None
    requires_user_confirmation: bool = False


@dataclass(frozen=True, slots=True)
class _RefinementContext:
    parent_ir: SchemaIR
    parent_kpis: list[KPIDefinition]
    parent_version_id: UUID
    entity_graph: EntityGraph


class RefinementSaga:
    """One-shot saga for a refinement request using the artifact-centric pipeline."""

    async def run(
        self,
        *,
        project_id: UUID,
        organization_id: UUID,
        request: str,
    ) -> RefinementResult:
        ctx = await self._load_parent(project_id=project_id)
        if ctx is None:
            raise BasefloError(
                error_code="BF-API-005",
                message=(
                    "Project has no current version yet; refinement requires "
                    "an initial generation first."
                ),
                status_code=400,
            )

        runtime = AgentRuntime()

        # Run SchemaAgent with user request as the business description
        schema_input = SchemaAgentInput(
            business_description=f"{request}\n\nExisting business: derived from current schema.",
            entity_graph=ctx.entity_graph.model_dump(mode="json"),
        )

        schema_result = await runtime.run(
            spec=SCHEMA_AGENT_SPEC,
            input_payload=schema_input,
            tenant_id=organization_id,
        )
        child_ir = schema_result.output.schema_ir

        # Deterministic validation (no LLM)
        ir_validate(child_ir)

        # Persist child version
        diff_summary = f"Refinement requested: {request}"
        new_version_id = await self._persist_child_version(
            project_id=project_id,
            parent_ir_version=ctx.parent_version_id,
            child_ir=child_ir,
            parent_kpis=ctx.parent_kpis,
            diff_summary=diff_summary,
        )

        return RefinementResult(
            project_id=project_id,
            parent_version_id=ctx.parent_version_id,
            new_version_id=new_version_id,
            diff_summary=diff_summary,
            requires_user_confirmation=True,
        )

    # ---------- internal ----------

    async def _load_parent(
        self, *, project_id: UUID
    ) -> _RefinementContext | None:
        from app.repositories.projects import ProjectRepository  # noqa: PLC0415

        async with open_session() as session:
            repo = ProjectRepository(session)
            current = await repo.get_current_version(project_id)
            if current is None:
                return None
            schema_ir_raw = current.schema_ir or {}
            if not schema_ir_raw:
                return None
            parent_ir = SchemaIR.model_validate(schema_ir_raw)
            kpis = [KPIDefinition.model_validate(k) for k in (current.kpi_definitions or [])]

            store = ArtifactStore(session)
            artifact = await store.get_latest(project_id, "entity_graph", EntityGraph)
            entity_graph = artifact.payload if artifact else EntityGraph(entities=[], unresolved=[])

            return _RefinementContext(
                parent_ir=parent_ir,
                parent_kpis=kpis,
                parent_version_id=current.id,
                entity_graph=entity_graph,
            )

    async def _persist_child_version(
        self,
        *,
        project_id: UUID,
        parent_ir_version: UUID,
        child_ir: SchemaIR,
        parent_kpis: list[KPIDefinition],
        diff_summary: str,
    ) -> UUID:
        from sqlalchemy import func, select  # noqa: PLC0415

        from app.db.models.project import ProjectVersion  # noqa: PLC0415
        from app.engines.analytics.taxonomy import build_event_taxonomy  # noqa: PLC0415
        from app.repositories.projects import ProjectRepository  # noqa: PLC0415
        from app.services.admin_ui.generator import build_admin_ui_spec  # noqa: PLC0415

        ctx = get_tenant_ctx()
        _ = ctx

        new_version_id = new_uuid7()
        admin_ui = build_admin_ui_spec(
            schema_ir=child_ir,
            kpis=parent_kpis,
            project_id=project_id,
            project_version_id=new_version_id,
        )
        taxonomy = build_event_taxonomy(child_ir)

        async with open_session() as session:
            repo = ProjectRepository(session)
            project = await repo.get(project_id)
            existing_max = (
                await session.execute(
                    select(func.coalesce(func.max(ProjectVersion.version_number), 0)).where(
                        ProjectVersion.project_id == project.id
                    )
                )
            ).scalar_one()

            new_version = ProjectVersion(
                id=new_version_id,
                project_id=project.id,
                parent_version_id=parent_ir_version,
                version_number=int(existing_max) + 1,
                schema_ir=child_ir.model_dump(mode="json"),
                kpi_definitions=[k.model_dump(mode="json") for k in parent_kpis],
                dashboard_spec=admin_ui.model_dump(mode="json"),
                intelligence_taxonomy=taxonomy.model_dump(mode="json"),
                assumptions=[a.model_dump(mode="json") for a in child_ir.assumptions],
                validation_status="passed",
                validation_report={"refinement_diff": diff_summary},
            )
            session.add(new_version)
            await session.flush()
            project.current_version_id = new_version.id
            return new_version.id
