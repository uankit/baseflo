from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

import httpx

from connectors.errors import AuthError


@dataclass(frozen=True, slots=True)
class OAuth2Config:
    authorize_url: str
    token_url: str
    scopes: list[str]


class OAuth2Helper:
    """OAuth 2.0 authorization-code flow. Reusable across sources.

    Holds static URLs/scopes. Client credentials are passed at call time so this
    helper has no knowledge of how credentials are sourced.
    """

    def __init__(self, config: OAuth2Config) -> None:
        self._config = config

    @property
    def scopes(self) -> list[str]:
        return list(self._config.scopes)

    def authorize_url(
        self,
        *,
        client_id: str,
        redirect_uri: str,
        state: str,
        extra_params: dict[str, str] | None = None,
    ) -> str:
        params = {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": " ".join(self._config.scopes),
            "state": state,
        }
        if extra_params:
            params.update(extra_params)
        return f"{self._config.authorize_url}?{urlencode(params)}"

    async def exchange_code(
        self,
        *,
        code: str,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
    ) -> dict[str, Any]:
        payload = {
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(self._config.token_url, data=payload)
        if resp.status_code != 200:
            raise AuthError(
                message=f"OAuth token exchange failed: {resp.text}",
                code="OAUTH_EXCHANGE_FAILED",
                status_hint=400,
            )
        return resp.json()

    async def refresh(
        self,
        *,
        refresh_token: str,
        client_id: str,
        client_secret: str,
    ) -> dict[str, Any]:
        payload = {
            "refresh_token": refresh_token,
            "client_id": client_id,
            "client_secret": client_secret,
            "grant_type": "refresh_token",
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(self._config.token_url, data=payload)
        if resp.status_code != 200:
            raise AuthError(
                message=f"OAuth token refresh failed: {resp.text}",
                code="OAUTH_REFRESH_FAILED",
                status_hint=401,
            )
        return resp.json()
