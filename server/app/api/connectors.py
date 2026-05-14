"""Available-connector listing + OAuth connect-start."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.auth.dependencies import require_auth
from app.auth.service import encode_oauth_state
from app.core.context import TenantCtx
from app.core.errors import NotFoundError, ValidationError
from app.sources import get_source_instance, oauth_callback_url
from connectors import AuthMethod, get_spec, list_specs

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
    try:
        spec = get_spec(kind)
    except Exception as exc:
        raise NotFoundError(
            message=f"Unknown connector kind: {kind}",
            code="UNKNOWN_CONNECTOR",
            status_hint=404,
        ) from exc

    if spec.auth_method != AuthMethod.OAUTH2:
        raise ValidationError(
            message=f"Non-OAuth connectors not supported yet (auth_method={spec.auth_method.value})",
            code="AUTH_METHOD_UNSUPPORTED",
            status_hint=400,
        )

    source = get_source_instance(kind)
    extra_state: dict[str, str] = {}
    authorize_kwargs: dict[str, str] = {
        "redirect_uri": oauth_callback_url(kind),
    }

    if kind == "shopify":
        shop_domain = (body.shop_domain if body else None) or ""
        try:
            normalized_shop = source.normalize_shop_domain(shop_domain)  # type: ignore[attr-defined]
        except Exception as exc:
            raise ValidationError(
                message="Enter a valid Shopify myshopify.com shop domain",
                code="SHOPIFY_SHOP_INVALID",
                status_hint=400,
            ) from exc
        extra_state["shop_domain"] = normalized_shop
        authorize_kwargs["shop_domain"] = normalized_shop

    state = encode_oauth_state(
        user_id=str(tenant.user_id),
        organization_id=str(tenant.organization_id),
        kind=kind,
        extra=extra_state,
    )
    authorize_url = source.authorize_url(state=state, **authorize_kwargs)
    return StartConnectResponse(authorize_url=authorize_url)
