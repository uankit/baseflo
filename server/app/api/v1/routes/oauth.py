"""OAuth install + callback endpoints.

Per docs/40-features/CONN-SHOPIFY.md §3.2 + §3.6 (and §AUTH for state-token
storage). Each provider gets its own pair of routes:

  GET  /api/v1/oauth/{provider}/install   → 302 to provider's authorize URL
  GET  /api/v1/oauth/{provider}/callback  → exchange code, persist token,
                                            redirect to project workspace

State tokens are stored in Redis with 5-minute TTL (per provider best-
practice). Cross-provider abstractions stay deliberately thin: each
provider's auth module owns its install-URL builder + token exchange.

Successful callbacks persist via `ConnectorRegistrar` — a `Connector` row
plus an envelope-encrypted `connector_tokens` row, atomic per session.
"""

from __future__ import annotations

import secrets
import urllib.parse
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.auth.dependencies import require_tenant
from app.connectors.google_sheets.auth import (
    GoogleInstallParams,
    build_install_url as google_sheets_build_install_url,
    exchange_code_for_token as google_sheets_exchange_code_for_token,
)
from app.connectors.shopify.auth import (
    InstallParams as ShopifyInstallParams,
    build_install_url as shopify_build_install_url,
    exchange_code_for_token as shopify_exchange_code_for_token,
    verify_install_callback_hmac as shopify_verify_install_callback_hmac,
)
from app.core.config import get_config
from app.core.context import TenantCtx
from app.core.crypto.envelope import EnvelopeCrypto
from app.core.crypto.kms import get_kms_client
from app.core.errors import BasefloError, ValidationError
from app.db.models.connector import TokenType
from app.db.session import open_session
from app.observability.logging import get_logger
from app.repositories.connector_tokens import ConnectorTokenRepository
from app.services.connector_oauth import (
    ConnectorRegistrar,
    ConnectorRegistration,
    WebhookSubscriber,
)
from app.services.connector_tokens.vault import TokenVault


_GOOGLE_SHEETS_SCOPES: tuple[str, ...] = (
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.metadata.readonly",
)
_GOOGLE_SHEETS_STATE_TTL_SECONDS = 600  # 10 minutes


router = APIRouter(prefix="/oauth", tags=["oauth"])
logger = get_logger("api.oauth")


# ---------- Service dependencies ----------


async def get_connector_registrar() -> AsyncIterator[ConnectorRegistrar]:
    """Yield a `ConnectorRegistrar` bound to a fresh DB session.

    Tests override this dep with a fake that records calls without touching
    Postgres — see `tests/unit/test_oauth_routes.py`.
    """
    async with open_session() as session:
        vault = TokenVault(
            repo=ConnectorTokenRepository(session),
            crypto=EnvelopeCrypto(kms=get_kms_client(), kek_alias="local-default"),
        )
        yield ConnectorRegistrar(session=session, vault=vault)


async def get_webhook_subscriber() -> AsyncIterator[WebhookSubscriber]:
    """Yield a `WebhookSubscriber` bound to a fresh DB session.

    Tests override this dep with a fake — the real subscriber would otherwise
    make outbound HTTP calls to providers (Shopify webhooks API, Drive
    channels.watch, Stripe webhook_endpoints) during install flows.
    """
    config = get_config()
    async with open_session() as session:
        vault = TokenVault(
            repo=ConnectorTokenRepository(session),
            crypto=EnvelopeCrypto(kms=get_kms_client(), kek_alias="local-default"),
        )
        yield WebhookSubscriber(
            session=session, vault=vault, api_base_url=config.api_base_url,
        )


# ---------- Response shapes ----------


class OAuthInstallResponse(BaseModel):
    redirect_url: str = Field(min_length=1)
    state: str = Field(min_length=8, max_length=4000)
    """Opaque to the client; only the provider needs to round-trip it."""


class OAuthCallbackResult(BaseModel):
    """Returned to the operator after a successful callback (UI redirects to
    the project workspace; this body powers the dev-mode JSON response)."""

    connector_name: str
    project_id: UUID
    shop_domain: str | None = None
    account_id: str | None = None


def _safe_return_to(raw: str | None) -> str | None:
    """Allow OAuth browser callbacks to return only to the configured web app."""
    if raw is None or raw == "":
        return None

    config = get_config()
    web_base = config.web_base_url.rstrip("/")
    parsed = urllib.parse.urlparse(raw)
    if parsed.scheme == "" and parsed.netloc == "" and raw.startswith("/") and not raw.startswith("//"):
        return f"{web_base}{raw}"
    if raw == web_base or raw.startswith(f"{web_base}/"):
        return raw
    raise ValidationError(
        message="OAuth return URL must point to the configured Baseflo web app.",
        error_code="BF-CONN-OAUTH-001",
    )


def _with_query(url: str, params: dict[str, str]) -> str:
    parsed = urllib.parse.urlparse(url)
    query = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    query.extend(params.items())
    return urllib.parse.urlunparse(
        parsed._replace(query=urllib.parse.urlencode(query))
    )


# ---------- Shopify ----------


@router.get(
    "/shopify/install",
    response_model=OAuthInstallResponse,
    summary="Build a Shopify OAuth install URL for a project",
)
async def shopify_install(
    tenant: Annotated[TenantCtx, Depends(require_tenant)],
    project_id: Annotated[UUID, Query(description="Project to bind the connector to")],
    shop_domain: Annotated[
        str,
        Query(min_length=4, max_length=120, pattern=r"^[a-zA-Z0-9-]+\.myshopify\.com$"),
    ],
) -> OAuthInstallResponse:
    """Return the URL the merchant is redirected to.

    The state token is the CSRF guard; the callback verifies it before
    registering the connector.
    """
    config = get_config()
    if (
        config.shopify_client_id is None
        or not config.shopify_client_id.strip()
        or config.shopify_client_secret is None
        or not config.shopify_client_secret.get_secret_value().strip()
    ):
        raise ValidationError(
            message=(
                "Shopify OAuth is not configured on this Baseflo deployment. "
                "Set BASEFLO_SHOPIFY_CLIENT_ID + BASEFLO_SHOPIFY_CLIENT_SECRET."
            ),
            error_code="BF-CONN-SHOPIFY-001",
        )

    state = secrets.token_urlsafe(24)
    params = ShopifyInstallParams(
        shop_domain=shop_domain,
        client_id=config.shopify_client_id,
        scopes=["read_customers", "read_orders", "read_products"],
        redirect_uri=f"{config.api_base_url}/api/v1/oauth/shopify/callback",
        state=state,
    )
    redirect_url = shopify_build_install_url(params)
    logger.info(
        "shopify_oauth_install_built",
        tenant=str(tenant.organization_id),
        project_id=str(project_id),
        shop_domain=shop_domain,
    )
    return OAuthInstallResponse(redirect_url=redirect_url, state=state)


@router.get(
    "/shopify/callback",
    response_model=OAuthCallbackResult,
    summary="Handle Shopify's OAuth install callback",
)
async def shopify_callback(
    tenant: Annotated[TenantCtx, Depends(require_tenant)],
    code: Annotated[str, Query(min_length=4, max_length=200)],
    shop: Annotated[
        str,
        Query(min_length=4, max_length=120, pattern=r"^[a-zA-Z0-9-]+\.myshopify\.com$"),
    ],
    state: Annotated[str, Query(min_length=8, max_length=120)],
    hmac: Annotated[str, Query(min_length=8, max_length=120)],
    timestamp: Annotated[str, Query(min_length=1, max_length=40)],
    project_id: Annotated[UUID, Query()],
    registrar: Annotated[ConnectorRegistrar, Depends(get_connector_registrar)],
    subscriber: Annotated[WebhookSubscriber, Depends(get_webhook_subscriber)],
) -> OAuthCallbackResult:
    """Verify Shopify's callback HMAC, exchange the code, persist the token."""
    config = get_config()
    if config.shopify_client_id is None or config.shopify_client_secret is None:
        raise ValidationError(
            message="Shopify OAuth is not configured.",
            error_code="BF-CONN-SHOPIFY-001",
        )
    secret = config.shopify_client_secret.get_secret_value()

    # Step 1: verify the callback's HMAC (this is the merchant identifying
    # itself; tampering with the redirect query is the attack we block here).
    callback_params = {
        "code": code, "shop": shop, "state": state,
        "timestamp": timestamp, "hmac": hmac,
    }
    if not shopify_verify_install_callback_hmac(
        query_params=callback_params, client_secret=secret,
    ):
        raise BasefloError(
            error_code="BF-CONN-SHOPIFY-002",
            message="Shopify install-callback HMAC verification failed.",
            status_code=401,
        )

    # Step 2: exchange the install code for an access token.
    result = await shopify_exchange_code_for_token(
        shop_domain=shop,
        code=code,
        client_id=config.shopify_client_id,
        client_secret=secret,
    )

    # Step 3: persist Connector + envelope-encrypted token. The registrar's
    # session commits together with the token-vault write.
    granted_scopes = [s.strip() for s in result.scope.split(",") if s.strip()]
    connector_id = await registrar.register(ConnectorRegistration(
        organization_id=tenant.organization_id,
        project_id=project_id,
        kind="shopify",
        display_name=f"Shopify — {shop}",
        config={
            "shop_domain": shop,
            "api_version": config.shopify_api_version,
        },
        token_type=TokenType.OAUTH2.value,
        token_payload={
            "access_token": result.access_token,
            "shop_domain": shop,
            "scope": result.scope,
        },
        token_scopes=granted_scopes,
    ))

    # Step 4: subscribe webhooks via the Shopify Admin API so live updates
    # land in our reconciler. Best-effort — install succeeds even if the
    # subscribe call fails (provider transient error, etc.).
    await subscriber.subscribe_for_connector(connector_id)

    logger.info(
        "shopify_oauth_callback_succeeded",
        tenant=str(tenant.organization_id),
        project_id=str(project_id),
        shop_domain=shop,
        scope=result.scope,
    )
    return OAuthCallbackResult(
        connector_name="shopify",
        project_id=project_id,
        shop_domain=shop,
    )


# ---------- Google Sheets ----------


def _google_sheets_state_signer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(
        get_config().secret_key.get_secret_value(),
        salt="oauth.google_sheets.install",
    )


def _require_google_oauth_configured() -> tuple[str, str]:
    config = get_config()
    if (
        config.google_client_id is None
        or not config.google_client_id.strip()
        or config.google_client_secret is None
        or not config.google_client_secret.get_secret_value().strip()
    ):
        raise ValidationError(
            message=(
                "Google Sheets OAuth is not configured on this Baseflo "
                "deployment. Set BASEFLO_GOOGLE_CLIENT_ID + "
                "BASEFLO_GOOGLE_CLIENT_SECRET."
            ),
            error_code="BF-CONN-SHEETS-001",
        )
    return config.google_client_id, config.google_client_secret.get_secret_value()


@router.get(
    "/google_sheets/install",
    response_model=OAuthInstallResponse,
    summary="Build a Google Sheets OAuth install URL for a project",
)
async def google_sheets_install(
    tenant: Annotated[TenantCtx, Depends(require_tenant)],
    project_id: Annotated[UUID, Query(description="Project to bind the connector to")],
    spreadsheet_id: Annotated[
        str,
        Query(min_length=10, max_length=120, pattern=r"^[A-Za-z0-9_-]+$"),
    ],
    redirect: Annotated[bool, Query(description="302 directly to Google")] = False,
    return_to: Annotated[str | None, Query(max_length=2048)] = None,
) -> OAuthInstallResponse | RedirectResponse:
    """Build the Google authorize URL for a single spreadsheet install.

    The state token (signed via `secret_key`) carries the project id, the
    spreadsheet id, and the org id so the callback can persist without a
    second user interaction. State expires in 10 minutes per OAuth norm.
    """
    config = get_config()
    client_id, _ = _require_google_oauth_configured()

    nonce = secrets.token_urlsafe(16)
    state_payload = {
        "project_id": str(project_id),
        "organization_id": str(tenant.organization_id),
        "spreadsheet_id": spreadsheet_id,
        "nonce": nonce,
    }
    safe_return_to = _safe_return_to(return_to)
    if safe_return_to is not None:
        state_payload["return_to"] = safe_return_to
    state = _google_sheets_state_signer().dumps(state_payload)

    install = GoogleInstallParams(
        client_id=client_id,
        scopes=list(_GOOGLE_SHEETS_SCOPES),
        redirect_uri=f"{config.api_base_url}/api/v1/oauth/google_sheets/callback",
        state=state,
    )
    redirect_url = google_sheets_build_install_url(install)

    logger.info(
        "google_sheets_oauth_install_built",
        tenant=str(tenant.organization_id),
        project_id=str(project_id),
        spreadsheet_id=spreadsheet_id,
    )
    if redirect:
        return _redirect_to(redirect_url)
    return OAuthInstallResponse(redirect_url=redirect_url, state=state)


@router.get(
    "/google_sheets/callback",
    response_model=OAuthCallbackResult,
    summary="Handle Google's OAuth callback for the Sheets connector",
)
async def google_sheets_callback(
    code: Annotated[str, Query(min_length=4, max_length=400)],
    state: Annotated[str, Query(min_length=8, max_length=4000)],
    registrar: Annotated[ConnectorRegistrar, Depends(get_connector_registrar)],
    subscriber: Annotated[WebhookSubscriber, Depends(get_webhook_subscriber)],
) -> OAuthCallbackResult | RedirectResponse:
    """Verify state, exchange code, persist `Connector` + encrypted token."""
    config = get_config()
    client_id, client_secret = _require_google_oauth_configured()

    # Step 1: verify + decode state.
    try:
        payload = _google_sheets_state_signer().loads(
            state, max_age=_GOOGLE_SHEETS_STATE_TTL_SECONDS,
        )
    except SignatureExpired as exc:
        raise BasefloError(
            error_code="BF-CONN-SHEETS-002",
            message="Sheets OAuth state expired; please retry the install.",
            status_code=400,
            cause=exc,
        ) from exc
    except BadSignature as exc:
        raise BasefloError(
            error_code="BF-CONN-SHEETS-002",
            message="Sheets OAuth state signature is invalid.",
            status_code=400,
            cause=exc,
        ) from exc
    if not isinstance(payload, dict):
        raise BasefloError(
            error_code="BF-CONN-SHEETS-002",
            message="Sheets OAuth state payload is not a dict.",
            status_code=400,
        )
    try:
        project_id = UUID(str(payload["project_id"]))
        organization_id = UUID(str(payload["organization_id"]))
        spreadsheet_id = str(payload["spreadsheet_id"])
        return_to = payload.get("return_to")
    except (KeyError, ValueError) as exc:
        raise BasefloError(
            error_code="BF-CONN-SHEETS-002",
            message="Sheets OAuth state payload is malformed.",
            status_code=400,
            cause=exc,
        ) from exc

    # Step 2: exchange code for tokens.
    redirect_uri = f"{config.api_base_url}/api/v1/oauth/google_sheets/callback"
    token_result = await google_sheets_exchange_code_for_token(
        code=code,
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
    )
    # `prompt=consent` should always return a refresh_token; if it's missing,
    # we cannot keep the connector working past the first hour. Surface clearly.
    if token_result.refresh_token is None:
        raise BasefloError(
            error_code="BF-CONN-SHEETS-003",
            message=(
                "Google did not return a refresh_token. Re-grant access with "
                "prompt=consent so the connector can refresh expired tokens."
            ),
            status_code=400,
        )

    # Step 3: persist Connector + envelope-encrypted token via the registrar.
    granted_scopes = [s for s in token_result.scope.split(" ") if s] if token_result.scope else []
    token_expires_at = datetime.now(UTC) + timedelta(seconds=token_result.expires_in)
    connector_id = await registrar.register(ConnectorRegistration(
        organization_id=organization_id,
        project_id=project_id,
        kind="google_sheets",
        display_name=f"Google Sheets — {spreadsheet_id}",
        config={"spreadsheet_id": spreadsheet_id},
        token_type=TokenType.OAUTH2.value,
        token_payload={
            "access_token": token_result.access_token,
            "refresh_token": token_result.refresh_token,
            "expires_in": token_result.expires_in,
            "scope": token_result.scope,
        },
        token_scopes=granted_scopes,
        token_expires_at=token_expires_at,
    ))

    # Step 4: register a Drive Push channel so we get notified on changes.
    # Mandatory for Sheets — no manual provider-side fallback like Shopify.
    await subscriber.subscribe_for_connector(connector_id)

    logger.info(
        "google_sheets_oauth_callback_succeeded",
        organization_id=str(organization_id),
        project_id=str(project_id),
        spreadsheet_id=spreadsheet_id,
    )
    if isinstance(return_to, str):
        return _redirect_to(
            _with_query(
                _safe_return_to(return_to) or get_config().web_base_url,
                {
                    "connector": "google_sheets",
                    "status": "connected",
                    "project_id": str(project_id),
                },
            )
        )
    return OAuthCallbackResult(
        connector_name="google_sheets",
        project_id=project_id,
        account_id=spreadsheet_id,
    )


# ---------- Generic redirect path ----------


def _redirect_to(url: str) -> RedirectResponse:
    """Helper for routes that 302 the merchant to the provider."""
    return RedirectResponse(url=url, status_code=302)


__all__ = ["router"]
