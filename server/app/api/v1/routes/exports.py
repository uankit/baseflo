"""Project data export endpoint.

Per docs/30-features.md SEC-EXPORT. The alpha response is a gzip archive
streamed directly back to the caller.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import Response

from app.auth.dependencies import require_tenant
from app.core.context import TenantCtx
from app.core.errors import BasefloError
from app.db.session import open_session
from app.engines.schema.ir import SchemaIR
from app.observability.logging import get_logger
from app.repositories.projects import ProjectRepository
from app.services.exports import compose_export_archive
from app.services.exports.canonical_reader import CanonicalRowReader


router = APIRouter(prefix="/projects", tags=["exports"])
logger = get_logger("api.exports")


@router.post(
    "/{project_id}/exports",
    summary="Compose a full project export (CSV + DDL + IR + .env)",
    response_class=Response,
)
async def create_export(
    project_id: UUID,
    tenant: Annotated[TenantCtx, Depends(require_tenant)],
) -> Response:
    """Build the tarball synchronously and stream it back.

    This endpoint is intentionally synchronous for alpha-scale exports.
    """
    async with open_session() as session:
        repo = ProjectRepository(session)
        project = await repo.get(project_id)
        version = await repo.get_current_version(project_id)
        if version is None or not version.schema_ir:
            raise BasefloError(
                error_code="BF-API-005",
                message=(
                    "Project has no current schema version; nothing to export. "
                    "Generate a project first, then retry."
                ),
                status_code=400,
            )
        schema_ir = SchemaIR.model_validate(version.schema_ir)
        slug = project.slug
        schema_name = project.tenant_data_schema_name

        # Read canonical rows from the per-tenant schema if it has been
        # provisioned. Projects without a finalized data plane still get
        # a usable export (IR + DDL + KPIs + empty CSVs).
        if schema_name is None:
            rows_by_table: dict[str, list[dict[str, object]]] = {}
        else:
            reader = CanonicalRowReader(
                session=session, schema_name=schema_name,
            )
            rows_by_table = await reader.collect_rows_by_table(ir=schema_ir)

    archive = compose_export_archive(
        project_slug=slug,
        project_version_id=version.id,
        schema_ir=schema_ir,
        kpi_definitions=list(version.kpi_definitions or []),
        rows_by_table=rows_by_table,
    )

    logger.info(
        "project_export_created",
        project_id=str(project_id),
        project_version_id=str(version.id),
        bytes=len(archive.bytes_),
        tenant=str(tenant.organization_id),
    )
    return Response(
        content=archive.bytes_,
        media_type="application/gzip",
        headers={
            "Content-Disposition": f'attachment; filename="{archive.filename}"',
            "X-Baseflo-Export-Tables": str(archive.table_count),
        },
    )
