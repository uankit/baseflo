"""Google OAuth2 helpers — install URL + token exchange + refresh.

Per docs/40-features/CONN-SHEETS.md §4. Google's OAuth2 flow is:

  1. Redirect merchant to https://accounts.google.com/o/oauth2/v2/auth with
     client_id, scope, redirect_uri, state, access_type=offline, prompt=consent.
  2. Google redirects back with `code`.
  3. Exchange code → access_token + refresh_token via oauth2.googleapis.com/token.
  4. Refresh access tokens via the same endpoint with grant_type=refresh_token.

`access_type=offline` + `prompt=consent` is required to get a refresh_token
on every consent (Google omits it on subsequent grants otherwise).
"""

from __future__ import annotations

import urllib.parse

import httpx
from pydantic import BaseModel, ConfigDict, Field

from app.core.errors import BasefloError
from app.observability.logging import get_logger


__all__ = [
    "GoogleInstallParams",
    "GoogleTokenResult",
    "build_install_url",
    "exchange_code_for_token",
    "refresh_access_token",
]


logger = get_logger("connectors.google_sheets.auth")


_AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
_TOKEN_URL = "https://oauth2.googleapis.com/token"


class GoogleInstallParams(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    client_id: str = Field(min_length=4, max_length=200)
    scopes: list[str] = Field(min_length=1, max_length=20)
    redirect_uri: str = Field(min_length=8, max_length=500)
    state: str = Field(min_length=8, max_length=4000)
    """Opaque to the provider. Sized to fit signed tokens (itsdangerous + JSON
    payload runs ~200-400 chars; cap is generous to absorb additional fields)."""


class GoogleTokenResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    access_token: str = Field(min_length=1)
    refresh_token: str | None = None
    """Returned only on first consent (or when prompt=consent forces re-issue)."""
    expires_in: int = Field(ge=1)
    scope: str = ""


def build_install_url(params: GoogleInstallParams) -> str:
    """Build the Google OAuth authorize URL.

    `access_type=offline` + `prompt=consent` ensures we get a refresh_token
    every time the merchant grants consent (Google's default omits it on
    subsequent grants).
    """
    query = urllib.parse.urlencode({
        "client_id": params.client_id,
        "scope": " ".join(params.scopes),
        "redirect_uri": params.redirect_uri,
        "state": params.state,
        "response_type": "code",
        "access_type": "offline",
        "prompt": "consent",
        "include_granted_scopes": "true",
    })
    return f"{_AUTHORIZE_URL}?{query}"


async def exchange_code_for_token(
    *,
    code: str,
    client_id: str,
    client_secret: str,
    redirect_uri: str,
    transport: httpx.BaseTransport | None = None,
    timeout: float = 10.0,
) -> GoogleTokenResult:
    """Swap an OAuth `code` for access + refresh tokens."""
    return await _post_token({
        "code": code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
    }, transport=transport, timeout=timeout, error_code="BF-CONN-SHEETS-001")


async def refresh_access_token(
    *,
    refresh_token: str,
    client_id: str,
    client_secret: str,
    transport: httpx.BaseTransport | None = None,
    timeout: float = 10.0,
) -> GoogleTokenResult:
    """Refresh an expired access_token via the refresh_token grant.

    Google may or may not return a fresh `refresh_token` (typically only on
    first issue); the caller keeps the old one if absent.
    """
    return await _post_token({
        "refresh_token": refresh_token,
        "client_id": client_id,
        "client_secret": client_secret,
        "grant_type": "refresh_token",
    }, transport=transport, timeout=timeout, error_code="BF-CONN-SHEETS-002")


async def _post_token(
    body: dict[str, str],
    *,
    transport: httpx.BaseTransport | None,
    timeout: float,
    error_code: str,
) -> GoogleTokenResult:
    client_kwargs: dict[str, object] = {"timeout": timeout}
    if transport is not None:
        client_kwargs["transport"] = transport
    try:
        async with httpx.AsyncClient(**client_kwargs) as client:  # type: ignore[arg-type]
            response = await client.post(
                _TOKEN_URL,
                data=body,
                headers={"Accept": "application/json"},
            )
    except httpx.HTTPError as exc:
        raise BasefloError(
            error_code=error_code,
            message=f"Google token endpoint transport error: {exc!r}",
            status_code=502,
            cause=exc,
        ) from exc

    if response.status_code >= 400:
        raise BasefloError(
            error_code=error_code,
            message=(
                f"Google token endpoint rejected request "
                f"(status={response.status_code})."
            ),
            status_code=400,
            details={"status": response.status_code, "body": response.text[:500]},
        )

    try:
        payload = response.json()
    except ValueError as exc:
        raise BasefloError(
            error_code=error_code,
            message="Google token endpoint response was not JSON.",
            status_code=502,
            cause=exc,
        ) from exc

    access_token = payload.get("access_token")
    if not isinstance(access_token, str) or not access_token:
        raise BasefloError(
            error_code=error_code,
            message="Google token endpoint response missing `access_token`.",
            status_code=502,
        )
    expires_in = int(payload.get("expires_in", 3600) or 3600)
    refresh = payload.get("refresh_token")
    scope = payload.get("scope", "")
    return GoogleTokenResult(
        access_token=access_token,
        refresh_token=refresh if isinstance(refresh, str) else None,
        expires_in=expires_in,
        scope=scope or "",
    )
