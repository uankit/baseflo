"""OAuth callback. Provider-named route to match registered redirect URIs."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from urllib.parse import urlencode
from uuid import UUID

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from app.auth.service import decode_oauth_state
from app.config import get_settings
from app.connector_runtime import (
    OAuthCallbackError,
    credentials_from_callback,
    get_source_instance,
    upsert_oauth_connection,
)
from app.core.errors import AuthError

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

    try:
        credentials_result = await credentials_from_callback(
            kind=kind,
            query_params=request.query_params,
            state_payload=payload,
            code=code,
            now=now,
        )
    except OAuthCallbackError as exc:
        logger.warning("OAuth callback validation failed for %s: %s", kind, exc.reason)
        return RedirectResponse(
            url=_frontend_redirect(path="/connections/error", reason=exc.reason),
            status_code=302,
        )
    except Exception as exc:
        logger.error("OAuth token exchange failed: %s", exc, exc_info=True)
        return RedirectResponse(
            url=_frontend_redirect(
                path="/connections/error", reason="token_exchange_failed",
            ),
            status_code=302,
        )
    credentials = credentials_result.credentials

    try:
        source = get_source_instance(kind)
        account = await source.get_account_info(credentials)
    except Exception as exc:
        logger.error("get_account_info failed: %s", exc, exc_info=True)
        return RedirectResponse(
            url=_frontend_redirect(
                path="/connections/error", reason="account_info_failed",
            ),
            status_code=302,
        )

    conn_id = await upsert_oauth_connection(
        organization_id=org_id,
        user_id=user_id,
        kind=kind,
        external_account_id=account.external_id,
        external_account_label=account.label,
        credentials=credentials,
    )

    return RedirectResponse(
        url=_frontend_redirect(path=f"/connections/{conn_id}/pick"),
        status_code=302,
    )
