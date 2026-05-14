"""Connection picker + data sources."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.auth.dependencies import require_auth
from app.core.context import TenantCtx
from app.core.enums import ConnectionStatus, DataSourceStatus
from app.core.errors import AppError, AuthError, NotFoundError
from app.db.models import Connection, DataSource
from app.db.session import open_session
from app.sources import get_source_instance
from connectors.errors import ConnectorError

router = APIRouter(tags=["data"])


# ---------- DTOs ----------


class ConnectionDTO(BaseModel):
    id: str
    kind: str
    external_account_label: str
    status: ConnectionStatus


class AvailableResourceDTO(BaseModel):
    external_id: str
    name: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class ResourcesResponse(BaseModel):
    connection: ConnectionDTO
    resources: list[AvailableResourceDTO]


class CreateSourcesRequest(BaseModel):
    resources: list[AvailableResourceDTO] = Field(min_length=1)


class DataSourceDTO(BaseModel):
    id: str
    kind: str
    name: str
    status: DataSourceStatus
    discovered_schema: dict[str, Any] | None = None
    last_synced_at: str | None = None
    last_error: str | None = None
    created_at: str


class DataSourcesResponse(BaseModel):
    data_sources: list[DataSourceDTO]


# ---------- Helpers ----------


def _ds_dto(ds: DataSource) -> DataSourceDTO:
    return DataSourceDTO(
        id=str(ds.id),
        kind=ds.kind,
        name=ds.name,
        status=ds.status,
        discovered_schema=ds.discovered_schema,
        last_synced_at=ds.last_synced_at.isoformat() if ds.last_synced_at else None,
        last_error=ds.last_error,
        created_at=ds.created_at.isoformat(),
    )


def _schema_to_dict(schema: Any) -> dict[str, Any]:
    """Convert connectors.SourceSchema dataclass tree → JSONable dict."""
    return {
        "tables": [
            {
                "name": t.name,
                "label": t.label,
                "row_count": t.row_count,
                "metadata": jsonable_encoder(t.metadata),
                "columns": [
                    {
                        "name": c.name,
                        "data_type": c.data_type.value,
                        "sample_values": jsonable_encoder(list(c.sample_values)),
                        "nullable": c.nullable,
                    }
                    for c in t.columns
                ],
            }
            for t in schema.tables
        ]
    }


def _resource_config(kind: str, resource: AvailableResourceDTO) -> dict[str, Any]:
    if kind == "google_sheets":
        return {"spreadsheet_id": resource.external_id}
    if kind == "shopify":
        return {"resource": resource.external_id}
    return {"resource": resource.external_id}


# ---------- Routes ----------


@router.get(
    "/connections/{connection_id}/resources",
    response_model=ResourcesResponse,
)
async def list_connection_resources(
    connection_id: UUID,
    tenant: Annotated[TenantCtx, Depends(require_auth)],
) -> ResourcesResponse:
    async with open_session() as session:
        conn = await session.get(Connection, connection_id)
        if conn is None or conn.organization_id != tenant.organization_id:
            raise NotFoundError(
                message="Connection not found",
                code="CONNECTION_NOT_FOUND",
                status_hint=404,
            )
        if conn.status != ConnectionStatus.ACTIVE:
            raise AuthError(
                message=f"Connection is {conn.status.value}",
                code="CONNECTION_INACTIVE",
                status_hint=400,
            )
        kind = conn.kind
        credentials = dict(conn.credentials)
        conn_dto = ConnectionDTO(
            id=str(conn.id),
            kind=conn.kind,
            external_account_label=conn.external_account_label,
            status=conn.status,
        )

    source = get_source_instance(kind)
    try:
        refreshed = await source.authenticate({"credentials": credentials})
        new_credentials = refreshed["credentials"]
        resources = await source.list_resources(new_credentials)
    except ConnectorError as exc:
        raise AppError(
            message=exc.message,
            code=exc.code,
            status_hint=exc.status_hint,
            details={"connector_kind": kind},
        ) from exc

    if new_credentials != credentials:
        async with open_session() as session:
            persistent = await session.get(Connection, connection_id)
            if persistent is not None:
                persistent.credentials = new_credentials

    return ResourcesResponse(
        connection=conn_dto,
        resources=[
            AvailableResourceDTO(
                external_id=r.external_id,
                name=r.name,
                metadata=r.metadata,
            )
            for r in resources
        ],
    )


@router.post(
    "/connections/{connection_id}/sources",
    response_model=DataSourcesResponse,
)
async def create_data_sources(
    connection_id: UUID,
    body: CreateSourcesRequest,
    tenant: Annotated[TenantCtx, Depends(require_auth)],
) -> DataSourcesResponse:
    async with open_session() as session:
        conn = await session.get(Connection, connection_id)
        if conn is None or conn.organization_id != tenant.organization_id:
            raise NotFoundError(
                message="Connection not found",
                code="CONNECTION_NOT_FOUND",
                status_hint=404,
            )
        kind = conn.kind
        credentials = dict(conn.credentials)

    source = get_source_instance(kind)
    refreshed = await source.authenticate({"credentials": credentials})
    new_credentials = refreshed["credentials"]
    now = datetime.now(UTC)

    created_ids: list[UUID] = []
    async with open_session() as session:
        persistent_conn = await session.get(Connection, connection_id)
        if persistent_conn is not None and new_credentials != credentials:
            persistent_conn.credentials = new_credentials

        for resource in body.resources:
            ds = DataSource(
                organization_id=tenant.organization_id,
                connection_id=connection_id,
                kind=kind,
                name=resource.name,
                config=_resource_config(kind, resource),
                status=DataSourceStatus.ACTIVE,
                created_by_user_id=tenant.user_id,
            )
            session.add(ds)
            await session.flush()

            try:
                full_config = {**ds.config, "credentials": new_credentials}
                schema = await source.introspect(full_config)
                ds.discovered_schema = _schema_to_dict(schema)
            except Exception as exc:
                ds.status = DataSourceStatus.ERROR
                ds.last_error = f"introspect failed: {exc}"

            created_ids.append(ds.id)

    # Sync each ACTIVE data source into the analytical substrate (DuckDB).
    # Synchronous within the request for v1; promote to background worker later.
    from app.substrate import sync_data_source as _substrate_sync

    async with open_session() as session:
        for ds_id in created_ids:
            ds = await session.get(DataSource, ds_id)
            if ds is None or ds.status != DataSourceStatus.ACTIVE:
                continue
            connection = await session.get(Connection, connection_id)
            if connection is None:
                continue
            try:
                await _substrate_sync(ds, connection)
                ds.last_synced_at = now
            except Exception as exc:
                ds.status = DataSourceStatus.ERROR
                ds.last_error = f"substrate sync failed: {exc}"

    async with open_session() as session:
        result = await session.execute(
            select(DataSource).where(DataSource.id.in_(created_ids))
        )
        sources = list(result.scalars().all())

    return DataSourcesResponse(data_sources=[_ds_dto(s) for s in sources])


@router.get("/data-sources", response_model=DataSourcesResponse)
async def list_data_sources(
    tenant: Annotated[TenantCtx, Depends(require_auth)],
) -> DataSourcesResponse:
    async with open_session() as session:
        result = await session.execute(
            select(DataSource)
            .where(DataSource.organization_id == tenant.organization_id)
            .order_by(DataSource.created_at.desc())
        )
        sources = list(result.scalars().all())
    return DataSourcesResponse(data_sources=[_ds_dto(s) for s in sources])


@router.get("/data-sources/{source_id}", response_model=DataSourceDTO)
async def get_data_source(
    source_id: UUID,
    tenant: Annotated[TenantCtx, Depends(require_auth)],
) -> DataSourceDTO:
    async with open_session() as session:
        ds = await session.get(DataSource, source_id)
        if ds is None or ds.organization_id != tenant.organization_id:
            raise NotFoundError(
                message="Data source not found",
                code="DATA_SOURCE_NOT_FOUND",
                status_hint=404,
            )
    return _ds_dto(ds)
