"""Connection picker + data sources."""

from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from connectors.errors import ConnectorError
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.auth.dependencies import require_auth
from app.connector_runtime import (
    DataSourceRecord,
    get_source_instance,
    load_connection,
    update_connection_credentials,
)
from app.connector_runtime import (
    list_data_sources as list_data_source_records,
)
from app.connector_runtime import (
    load_data_source as load_data_source_record,
)
from app.core.context import TenantCtx
from app.core.enums import ConnectionStatus, DataSourceStatus
from app.core.errors import AppError, AuthError, NotFoundError
from app.data_onboarding import DataSourceOnboardingService

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


def _ds_dto(ds: DataSourceRecord) -> DataSourceDTO:
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


# ---------- Routes ----------


@router.get(
    "/connections/{connection_id}/resources",
    response_model=ResourcesResponse,
)
async def list_connection_resources(
    connection_id: UUID,
    tenant: Annotated[TenantCtx, Depends(require_auth)],
) -> ResourcesResponse:
    conn = await load_connection(connection_id, organization_id=tenant.organization_id)
    if conn is None:
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
        await update_connection_credentials(connection_id, new_credentials)

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
    try:
        result = await DataSourceOnboardingService().create_sources(
            organization_id=tenant.organization_id,
            user_id=tenant.user_id,
            connection_id=connection_id,
            resources=body.resources,
        )
    except ConnectorError as exc:
        raise AppError(
            message=exc.message,
            code=exc.code,
            status_hint=exc.status_hint,
            details={"connection_id": str(connection_id)},
        ) from exc

    return DataSourcesResponse(data_sources=[_ds_dto(s) for s in result.data_sources])


@router.get("/data-sources", response_model=DataSourcesResponse)
async def list_data_sources(
    tenant: Annotated[TenantCtx, Depends(require_auth)],
) -> DataSourcesResponse:
    sources = await list_data_source_records(tenant.organization_id)
    return DataSourcesResponse(data_sources=[_ds_dto(s) for s in sources])


@router.get("/data-sources/{source_id}", response_model=DataSourceDTO)
async def get_data_source(
    source_id: UUID,
    tenant: Annotated[TenantCtx, Depends(require_auth)],
) -> DataSourceDTO:
    ds = await load_data_source_record(source_id, organization_id=tenant.organization_id)
    if ds is None:
        raise NotFoundError(
            message="Data source not found",
            code="DATA_SOURCE_NOT_FOUND",
            status_hint=404,
        )
    return _ds_dto(ds)
