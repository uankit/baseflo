"""Server-side runtime adapters for connector implementations.

The `connectors` package owns the source contract and source-specific API code.
This module owns the server wiring around those sources: settings injection,
OAuth edge cases, and resource-to-DataSource config mapping.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Protocol

from connectors import Source, get_source_class

from app.config import Settings
from app.core.errors import ValidationError


@dataclass(frozen=True, slots=True)
class OAuthStartPlan:
    authorize_kwargs: dict[str, str]
    extra_state: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class OAuthCredentialsResult:
    credentials: dict[str, Any]


class OAuthCallbackError(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class ResourceLike(Protocol):
    external_id: str
    name: str
    metadata: dict[str, Any]


class ConnectorRuntimeAdapter:
    """Source-neutral adapter contract used by server routes and data plane."""

    kind: str

    def create_source(self, settings: Settings) -> Source:
        raise NotImplementedError

    def resource_config(self, resource: ResourceLike) -> dict[str, Any]:
        return {"resource": resource.external_id}

    def oauth_start_plan(
        self,
        *,
        source: Source,
        payload: Mapping[str, Any],
        redirect_uri: str,
    ) -> OAuthStartPlan:
        return OAuthStartPlan(authorize_kwargs={"redirect_uri": redirect_uri})

    async def oauth_credentials_from_callback(
        self,
        *,
        source: Source,
        query_params: Mapping[str, Any],
        state_payload: Mapping[str, Any],
        code: str,
        redirect_uri: str,
        now: datetime,
    ) -> OAuthCredentialsResult:
        tokens = await source.exchange_code(code=code, redirect_uri=redirect_uri)  # type: ignore[attr-defined]
        expires_in = int(tokens.get("expires_in", 3600))
        return OAuthCredentialsResult(
            credentials={
                "access_token": tokens["access_token"],
                "refresh_token": tokens.get("refresh_token"),
                "expires_at": (now + timedelta(seconds=expires_in)).isoformat(),
            }
        )


class DefaultConnectorRuntimeAdapter(ConnectorRuntimeAdapter):
    """Default runtime for connectors that need no server-specific settings."""

    def __init__(self, kind: str) -> None:
        self.kind = kind

    def create_source(self, settings: Settings) -> Source:
        source_cls: Any = get_source_class(self.kind)
        try:
            return source_cls()
        except TypeError as exc:
            raise ValidationError(
                message=f"Connector '{self.kind}' needs a server runtime adapter",
                code="CONNECTOR_RUNTIME_REQUIRED",
                status_hint=501,
            ) from exc


class GoogleSheetsRuntimeAdapter(ConnectorRuntimeAdapter):
    kind = "google_sheets"

    def create_source(self, settings: Settings) -> Source:
        if not settings.google_client_id or not settings.google_client_secret:
            raise ValidationError(
                message="Google OAuth is not configured (set BASEFLO_GOOGLE_CLIENT_ID and BASEFLO_GOOGLE_CLIENT_SECRET)",
                code="GOOGLE_OAUTH_NOT_CONFIGURED",
                status_hint=503,
            )
        source_cls: Any = get_source_class(self.kind)
        return source_cls(
            client_id=settings.google_client_id,
            client_secret=settings.google_client_secret.get_secret_value(),
        )

    def resource_config(self, resource: ResourceLike) -> dict[str, Any]:
        return {"spreadsheet_id": resource.external_id}


class ShopifyRuntimeAdapter(ConnectorRuntimeAdapter):
    kind = "shopify"

    def create_source(self, settings: Settings) -> Source:
        if not settings.shopify_client_id or not settings.shopify_client_secret:
            raise ValidationError(
                message="Shopify OAuth is not configured (set BASEFLO_SHOPIFY_CLIENT_ID and BASEFLO_SHOPIFY_CLIENT_SECRET)",
                code="SHOPIFY_OAUTH_NOT_CONFIGURED",
                status_hint=503,
            )
        scopes = [
            scope.strip()
            for scope in settings.shopify_scopes.replace(" ", ",").split(",")
            if scope.strip()
        ]
        source_cls: Any = get_source_class(self.kind)
        return source_cls(
            client_id=settings.shopify_client_id,
            client_secret=settings.shopify_client_secret.get_secret_value(),
            api_version=settings.shopify_api_version,
            scopes=scopes,
            max_rows_per_resource=settings.shopify_max_rows_per_resource,
        )

    def oauth_start_plan(
        self,
        *,
        source: Source,
        payload: Mapping[str, Any],
        redirect_uri: str,
    ) -> OAuthStartPlan:
        shop_domain = str(payload.get("shop_domain") or "")
        try:
            normalized_shop = source.normalize_shop_domain(shop_domain)  # type: ignore[attr-defined]
        except Exception as exc:
            raise ValidationError(
                message="Enter a valid Shopify myshopify.com shop domain",
                code="SHOPIFY_SHOP_INVALID",
                status_hint=400,
            ) from exc
        return OAuthStartPlan(
            authorize_kwargs={
                "redirect_uri": redirect_uri,
                "shop_domain": normalized_shop,
            },
            extra_state={"shop_domain": normalized_shop},
        )

    async def oauth_credentials_from_callback(
        self,
        *,
        source: Source,
        query_params: Mapping[str, Any],
        state_payload: Mapping[str, Any],
        code: str,
        redirect_uri: str,
        now: datetime,
    ) -> OAuthCredentialsResult:
        callback_shop = query_params.get("shop")
        state_shop = state_payload.get("shop_domain")
        if not callback_shop or not state_shop:
            raise OAuthCallbackError("missing_shop")
        try:
            normalized_callback_shop = source.normalize_shop_domain(str(callback_shop))  # type: ignore[attr-defined]
            normalized_state_shop = source.normalize_shop_domain(str(state_shop))  # type: ignore[attr-defined]
        except Exception as exc:
            raise OAuthCallbackError("invalid_shop") from exc
        if normalized_callback_shop != normalized_state_shop:
            raise OAuthCallbackError("shop_mismatch")
        if not source.verify_callback_hmac(query_params):  # type: ignore[attr-defined]
            raise OAuthCallbackError("invalid_signature")

        tokens = await source.exchange_code(  # type: ignore[attr-defined]
            code=code,
            redirect_uri=redirect_uri,
            shop_domain=normalized_callback_shop,
        )
        return OAuthCredentialsResult(
            credentials={
                "access_token": tokens["access_token"],
                "shop_domain": tokens["shop_domain"],
                "scope": tokens.get("scope"),
            }
        )
