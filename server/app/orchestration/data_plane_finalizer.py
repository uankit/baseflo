"""DataPlaneFinalizer — apply DDL + backfill canonical store after a build.

Per docs/01-architecture.md §4. Once a workspace build or refinement flow
persists a new `ProjectVersion`, this orchestrator:

  1. Applies the version's `SchemaIR` to the per-tenant Postgres schema via
     `SchemaApplier`. Idempotent on re-run.
  2. Walks the IR + the build's already-loaded connectors and runs
     `BackfillRunner.backfill_ir(...)` so each canonical table fills with
     rows from the source of truth.

The finalizer is synchronous for the alpha build — the user's
`baseflo ask "..."` waits until rows have landed before getting
`workspace.ready`. Backfill for very large
imports; the typed `FinalizationResult` shape is unchanged.

Failure semantics: if `SchemaApplier` raises (DDL syntax, RLS violation,
KMS unreachable), the finalizer propagates — the build fails as a unit so
the design partner doesn't see a "ready" state with an empty store. Future releases
splits this into an arq retry loop.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.observability.logging import get_logger
from app.services.data_plane.schema_applier import (
    ApplicationResult,
)

if TYPE_CHECKING:
    from app.connectors.base import ConnectorToken
    from app.db.models.project import Project
    from app.engines.schema.ir import SchemaIR
    from app.orchestration.connectors import LoadedConnector
    from app.services.data_plane.backfill_runner import (
        BackfillRunner,
        BackfillTableResult,
        ConnectorReader,
    )
    from app.services.data_plane.schema_applier import SchemaApplier

__all__ = ["DataPlaneFinalizer", "FinalizationResult"]


logger = get_logger("orchestration.data_plane_finalizer")


@dataclass(frozen=True, slots=True)
class FinalizationResult:
    schema: ApplicationResult
    backfills: list[BackfillTableResult]
    skipped: bool
    """True when the project has no IR tables (description-only flow)."""


class DataPlaneFinalizer:
    """Composes SchemaApplier + BackfillRunner for one project version."""

    def __init__(
        self,
        *,
        schema_applier: SchemaApplier,
        backfill_runner: BackfillRunner,
    ) -> None:
        self._schema_applier = schema_applier
        self._backfill_runner = backfill_runner

    async def finalize(
        self,
        *,
        project: Project,
        ir: SchemaIR,
        connectors: list[LoadedConnector],
    ) -> FinalizationResult:
        if not ir.tables:
            logger.info(
                "data_plane_finalize_skipped_empty_ir",
                project_id=str(project.id),
            )
            return FinalizationResult(
                schema=ApplicationResult(
                    application_id=project.id,
                    project_id=project.id,
                    schema_name=project.tenant_data_schema_name or "",
                    ir_hash="",
                    statements_count=0,
                    was_idempotent_skip=True,
                ),
                backfills=[],
                skipped=True,
            )

        schema_result = await self._schema_applier.apply_initial(
            project=project, ir=ir,
        )
        logger.info(
            "data_plane_schema_applied",
            project_id=str(project.id),
            schema_name=schema_result.schema_name,
            ir_hash=schema_result.ir_hash,
            idempotent_skip=schema_result.was_idempotent_skip,
        )

        connectors_map: dict[str, tuple[ConnectorReader, ConnectorToken]] = {
            loaded.token.connector_name: (loaded.instance, loaded.token)
            for loaded in connectors
        }
        backfill_results = await self._backfill_runner.backfill_ir(
            organization_id=project.organization_id,
            project_id=project.id,
            ir=ir,
            connectors=connectors_map,
        )

        total_rows = sum(r.rows_upserted for r in backfill_results)
        logger.info(
            "data_plane_backfill_complete",
            project_id=str(project.id),
            tables=len(backfill_results),
            rows_upserted=total_rows,
            rows_skipped=sum(r.rows_skipped for r in backfill_results),
        )
        return FinalizationResult(
            schema=schema_result,
            backfills=backfill_results,
            skipped=False,
        )
