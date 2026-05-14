"""OAuth callback. Provider-named route to match registered redirect URIs."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode
from uuid import UUID

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select

from app.auth.service import decode_oauth_state
from app.config import get_settings
from app.core.enums import ConnectionStatus
from app.core.errors import AuthError
from app.db.models import Connection
from app.db.session import open_session
from app.sources import get_source_instance, oauth_callback_url

logger = logging.getLogger("baseflo.oauth")
router = APIRouter(tags=["oauth"])

_settings = get_settings()


def _frontend_redirect(*, path: str, **qs: str) -> str:
    url = f"{_settings.frontend_url.rstrip('/')}{path}"
    if qs:
        url = f"{url}?{urlencode(qs)}"
    return url


@router.get("/{kind}/callback")
async def oauth_callback(
    kind: str,
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
) -> RedirectResponse:
    """OAuth callback. The {kind} segment matches the registered redirect URI."""
    if error:
        logger.warning("OAuth provider returned error for %s: %s", kind, error)
        return RedirectResponse(
            url=_frontend_redirect(path="/connections/error", reason=error),
            status_code=302,
        )

    if not code or not state:
        return RedirectResponse(
            url=_frontend_redirect(
                path="/connections/error", reason="missing_code_or_state",
            ),
            status_code=302,
        )

    try:
        payload = decode_oauth_state(state)
    except AuthError as exc:
        logger.warning("Bad OAuth state: %s", exc)
        return RedirectResponse(
            url=_frontend_redirect(path="/connections/error", reason="invalid_state"),
            status_code=302,
        )

    if payload.get("kind") != kind:
        logger.warning(
            "OAuth state kind mismatch: url=%s state=%s", kind, payload.get("kind"),
        )
        return RedirectResponse(
            url=_frontend_redirect(path="/connections/error", reason="kind_mismatch"),
            status_code=302,
        )

    user_id = UUID(payload["sub"])
    org_id = UUID(payload["org"])
    now = datetime.now(UTC)

    source = get_source_instance(kind)
    token_kwargs: dict[str, str] = {
        "code": code,
        "redirect_uri": oauth_callback_url(kind),
    }

    if kind == "shopify":
        callback_shop = request.query_params.get("shop")
        state_shop = payload.get("shop_domain")
        if not callback_shop or not state_shop:
            return RedirectResponse(
                url=_frontend_redirect(
                    path="/connections/error", reason="missing_shop",
                ),
                status_code=302,
            )
        try:
            normalized_callback_shop = source.normalize_shop_domain(callback_shop)  # type: ignore[attr-defined]
            normalized_state_shop = source.normalize_shop_domain(state_shop)  # type: ignore[attr-defined]
        except Exception:
            return RedirectResponse(
                url=_frontend_redirect(
                    path="/connections/error", reason="invalid_shop",
                ),
                status_code=302,
            )
        if normalized_callback_shop != normalized_state_shop:
            logger.warning(
                "Shopify OAuth shop mismatch: callback=%s state=%s",
                normalized_callback_shop,
                normalized_state_shop,
            )
            return RedirectResponse(
                url=_frontend_redirect(
                    path="/connections/error", reason="shop_mismatch",
                ),
                status_code=302,
            )
        if not source.verify_callback_hmac(request.query_params):  # type: ignore[attr-defined]
            logger.warning("Shopify OAuth callback HMAC verification failed")
            return RedirectResponse(
                url=_frontend_redirect(
                    path="/connections/error", reason="invalid_signature",
                ),
                status_code=302,
            )
        token_kwargs["shop_domain"] = normalized_callback_shop

    try:
        tokens = await source.exchange_code(**token_kwargs)
    except Exception as exc:
        logger.error("OAuth token exchange failed: %s", exc, exc_info=True)
        return RedirectResponse(
            url=_frontend_redirect(
                path="/connections/error", reason="token_exchange_failed",
            ),
            status_code=302,
        )

    if kind == "shopify":
        credentials = {
            "access_token": tokens["access_token"],
            "shop_domain": tokens["shop_domain"],
            "scope": tokens.get("scope"),
        }
    else:
        expires_in = int(tokens.get("expires_in", 3600))
        credentials = {
            "access_token": tokens["access_token"],
            "refresh_token": tokens.get("refresh_token"),
            "expires_at": (now + timedelta(seconds=expires_in)).isoformat(),
        }

    try:
        account = await source.get_account_info(credentials)
    except Exception as exc:
        logger.error("get_account_info failed: %s", exc, exc_info=True)
        return RedirectResponse(
            url=_frontend_redirect(
                path="/connections/error", reason="account_info_failed",
            ),
            status_code=302,
        )

    async with open_session() as session:
        result = await session.execute(
            select(Connection).where(
                Connection.organization_id == org_id,
                Connection.kind == kind,
                Connection.external_account_id == account.external_id,
            )
        )
        conn = result.scalar_one_or_none()
        if conn is not None:
            conn.credentials = credentials
            conn.status = ConnectionStatus.ACTIVE
            conn.last_error = None
            conn.external_account_label = account.label
        else:
            conn = Connection(
                organization_id=org_id,
                kind=kind,
                external_account_id=account.external_id,
                external_account_label=account.label,
                credentials=credentials,
                status=ConnectionStatus.ACTIVE,
                created_by_user_id=user_id,
            )
            session.add(conn)
            await session.flush()
        conn_id = conn.id

    return RedirectResponse(
        url=_frontend_redirect(path=f"/connections/{conn_id}/pick"),
        status_code=302,
    )
