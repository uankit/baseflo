"""Available-connector listing + OAuth connect-start."""

from __future__ import annotations

from typing import Annotated

from connectors import list_specs
from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field

from app.auth.dependencies import require_auth
from app.connector_runtime import build_authorize_url
from app.core.context import TenantCtx

router = APIRouter(tags=["connectors"])


class ConnectorDTO(BaseModel):
    kind: str
    display_name: str
    description: str
    auth_method: str
    capabilities: list[str]


class ConnectorsResponse(BaseModel):
    connectors: list[ConnectorDTO]


class StartConnectResponse(BaseModel):
    authorize_url: str


class StartConnectRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    shop_domain: str | None = Field(default=None)


@router.get("", response_model=ConnectorsResponse)
async def list_connectors(
    _: Annotated[TenantCtx, Depends(require_auth)],
) -> ConnectorsResponse:
    return ConnectorsResponse(
        connectors=[
            ConnectorDTO(
                kind=s.kind,
                display_name=s.display_name,
                description=s.description,
                auth_method=s.auth_method.value,
                capabilities=sorted(c.value for c in s.capabilities),
            )
            for s in list_specs()
        ]
    )


@router.post("/{kind}/connect", response_model=StartConnectResponse)
async def start_connect(
    kind: str,
    tenant: Annotated[TenantCtx, Depends(require_auth)],
    body: StartConnectRequest | None = None,
) -> StartConnectResponse:
    authorize_url = build_authorize_url(
        kind=kind,
        user_id=tenant.user_id,
        organization_id=tenant.organization_id,
        payload=body.model_dump(exclude_none=True) if body else {},
    )
    return StartConnectResponse(authorize_url=authorize_url)
