"""SchemaApplier — runs compiled DDL against a per-tenant Postgres schema.

Per docs/01-architecture.md §4. The DDL compiler emits unqualified DDL
(e.g. `CREATE TABLE "customers" (…)`); the applier creates a per-tenant
schema, sets `search_path` for the duration of the transaction, splits the
compiled SQL into statements via SQLGlot, and runs them in order.

Idempotency: each run is recorded in `tenant_data_applications` with the
`ir_hash` from `EmissionResult`. A re-apply of the same (project, ir_hash)
pair short-circuits without touching Postgres.

v1 scope:
  - Hosted Cloud only — tenant schemas live inside the control-plane DB.
  - `apply_initial` only — first DDL application for a project version.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

import sqlglot
from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import BasefloError
from app.db.models.project import DeploymentMode, Project
from app.db.models.tenant_data_application import (
    TenantDataApplication,
    TenantDataApplicationKind,
    TenantDataApplicationStatus,
)
from app.engines.schema.ddl.compiler import EmissionResult, compile_ir
from app.engines.schema.ddl.identifiers import is_safe_identifier, quote_identifier
from app.engines.schema.ir import SchemaIR
from app.observability.logging import get_logger


__all__ = [
    "ApplicationResult",
    "SchemaApplier",
    "split_ddl",
]


logger = get_logger("data_plane.schema_applier")


@dataclass(frozen=True, slots=True)
class ApplicationResult:
    """Returned by `SchemaApplier.apply_initial`."""

    application_id: UUID
    project_id: UUID
    schema_name: str
    ir_hash: str
    statements_count: int
    was_idempotent_skip: bool
    """True when the (project_id, ir_hash) pair was already applied successfully."""


def split_ddl(sql: str) -> list[str]:
    """Split compiled DDL into individual statements via SQLGlot parse.

    Robust against embedded `;` (none in the M1 emitter's output, but we
    don't want to inherit a string-split fragility).
    """
    parsed = sqlglot.parse(sql, read="postgres")
    statements: list[str] = []
    for stmt in parsed:
        if stmt is None:
            continue
        rendered = stmt.sql(dialect="postgres")
        if rendered.strip():
            statements.append(rendered)
    return statements


class SchemaApplier:
    """Applies a finalized `SchemaIR` to a per-tenant Postgres schema."""

    def __init__(self, *, control_session: AsyncSession) -> None:
        """`control_session` is the AsyncSession bound to the control-plane DB.

        For Hosted Cloud the same session also runs the tenant DDL because
        tenant schemas live inside the control-plane database. BYO-DB will
        accept a separate engine.
        """
        self._session = control_session

    async def apply_initial(
        self, *, project: Project, ir: SchemaIR,
    ) -> ApplicationResult:
        """Compile, validate, and apply the IR to the project's tenant schema.

        Idempotent: returns the prior application unchanged if the same
        `ir_hash` has already succeeded for the project.
        """
        if project.deployment_mode != DeploymentMode.HOSTED.value:
            raise BasefloError(
                error_code="BF-DATAPLANE-001",
                message=(
                    "SchemaApplier supports the hosted deployment mode only "
                    f"in M0; got {project.deployment_mode!r}."
                ),
                status_code=501,
            )
        schema_name = project.tenant_data_schema_name
        if schema_name is None or not is_safe_identifier(schema_name):
            raise BasefloError(
                error_code="BF-DATAPLANE-002",
                message=(
                    "Project is missing a valid `tenant_data_schema_name`. "
                    "Bootstrap routes must populate it on creation."
                ),
                status_code=500,
            )

        emission = compile_ir(ir)
        ir_hash = emission.ast_hash

        # Idempotency check.
        existing = await self._find_succeeded_application(
            project_id=project.id, ir_hash=ir_hash,
        )
        if existing is not None:
            return ApplicationResult(
                application_id=existing.id,
                project_id=existing.project_id,
                schema_name=existing.schema_name,
                ir_hash=existing.ir_hash,
                statements_count=existing.statements_count,
                was_idempotent_skip=True,
            )

        statements = split_ddl(emission.sql)
        application = TenantDataApplication(
            organization_id=project.organization_id,
            project_id=project.id,
            schema_name=schema_name,
            ir_hash=ir_hash,
            parent_ir_hash=None,
            kind=TenantDataApplicationKind.INITIAL.value,
            statements_count=len(statements),
            status=TenantDataApplicationStatus.SUCCEEDED.value,
        )

        try:
            await self._run_ddl(schema_name=schema_name, statements=statements)
        except SQLAlchemyError as exc:
            # Record the failure on a fresh transaction so the caller's
            # in-flight session can be rolled back without losing forensics.
            application.status = TenantDataApplicationStatus.FAILED.value
            application.error_text = repr(exc)[:2000]
            self._session.add(application)
            try:
                await self._session.flush()
            except SQLAlchemyError:
                pass
            raise BasefloError(
                error_code="BF-DATAPLANE-003",
                message=f"Failed to apply tenant schema DDL: {exc!r}",
                status_code=500,
                cause=exc,
            ) from exc

        self._session.add(application)
        await self._session.flush()

        logger.info(
            "tenant_schema_applied",
            project_id=str(project.id),
            schema_name=schema_name,
            ir_hash=ir_hash,
            statements_count=len(statements),
            tables=emission.table_count,
            relationships=emission.relationship_count,
            indexes=emission.index_count,
        )
        return ApplicationResult(
            application_id=application.id,
            project_id=project.id,
            schema_name=schema_name,
            ir_hash=ir_hash,
            statements_count=len(statements),
            was_idempotent_skip=False,
        )

    # ---------- internal ----------

    async def _find_succeeded_application(
        self, *, project_id: UUID, ir_hash: str,
    ) -> TenantDataApplication | None:
        stmt = select(TenantDataApplication).where(
            TenantDataApplication.project_id == project_id,
            TenantDataApplication.ir_hash == ir_hash,
            TenantDataApplication.status == TenantDataApplicationStatus.SUCCEEDED.value,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def _run_ddl(
        self, *, schema_name: str, statements: list[str],
    ) -> None:
        # Schema creation is idempotent on its own.
        await self._session.execute(
            text(f"CREATE SCHEMA IF NOT EXISTS {quote_identifier(schema_name)}"),
        )
        # `SET LOCAL search_path` is transaction-scoped; it resets at COMMIT
        # so the control-plane reads in the same request aren't mis-routed.
        # The schema name is identifier-safe (validated above) so this f-string
        # cannot be injected.
        await self._session.execute(
            text(
                f"SET LOCAL search_path TO {quote_identifier(schema_name)}, public",
            ),
        )
        for stmt in statements:
            await self._session.execute(text(stmt))


# Re-export for callers that want both the class and the type.
_ = EmissionResult
