"""Google OAuth user sign-in.

Per docs/40-features/AUTH.md §3.4. Distinct from the connector-data Google
OAuth flow (Sheets / Drive scopes). This is purely for user identity:
`openid email profile`.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from typing import Any, Protocol
from urllib.parse import urlencode

import httpx
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.auth.magic_link import UserHandle
from app.core.errors import BasefloError
from app.observability.logging import get_logger

__all__ = ["GoogleAuthResult", "GoogleOAuthService", "IdentityDirectory"]


logger = get_logger("auth.oauth.google")


_AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
_TOKEN_URL = "https://oauth2.googleapis.com/token"
_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"
_SCOPES = "openid email profile"
_STATE_TTL_SECONDS = 600  # 10 minutes


# ---------- Identity directory ----------


class IdentityDirectory(Protocol):
    """Service-shaped slice of OAuthIdentityRepository + UserRepository."""

    async def find_user_by_provider_subject(
        self, *, provider: str, subject: str,
    ) -> UserHandle | None: ...

    async def link_or_create(
        self,
        *,
        provider: str,
        subject: str,
        email: str,
        display_name: str | None = None,
    ) -> UserHandle: ...


# ---------- Service-facing types ----------


@dataclass(frozen=True, slots=True)
class GoogleAuthResult:
    user: UserHandle
    is_new_user: bool
    redirect_to: str | None


# ---------- Service ----------


def _bad_oauth(message: str, *, cause: BaseException | None = None) -> BasefloError:
    return BasefloError(
        error_code="BF-AUTH-004",
        message=message,
        status_code=400,
        cause=cause,
    )


class GoogleOAuthService:
    def __init__(
        self,
        *,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
        identities: IdentityDirectory,
        signer: URLSafeTimedSerializer,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._redirect_uri = redirect_uri
        self._identities = identities
        self._signer = signer
        self._transport = transport

    # ---------- Authorize URL ----------

    def authorize_url(self, *, redirect_to: str | None) -> str:
        nonce = secrets.token_urlsafe(16)
        state = self._signer.dumps({"redirect_to": redirect_to, "nonce": nonce})
        params = {
            "response_type": "code",
            "client_id": self._client_id,
            "redirect_uri": self._redirect_uri,
            "scope": _SCOPES,
            "state": state,
            "access_type": "online",
            "prompt": "select_account",
        }
        return f"{_AUTHORIZE_URL}?{urlencode(params)}"

    def unsafe_decode_state(self, state: str) -> dict[str, Any]:
        """Decode without enforcing TTL; for tests only."""
        result = self._signer.loads(state, max_age=None)
        if not isinstance(result, dict):
            raise _bad_oauth("State payload is not a dict.")
        return result

    # ---------- Callback consumer ----------

    async def consume_callback(
        self, *, code: str, state: str,
    ) -> GoogleAuthResult:
        # 1. Verify + decode state.
        try:
            payload = self._signer.loads(state, max_age=_STATE_TTL_SECONDS)
        except SignatureExpired as exc:
            raise _bad_oauth(
                "OAuth state has expired; please retry sign-in.", cause=exc,
            ) from exc
        except BadSignature as exc:
            raise _bad_oauth("OAuth state is invalid.", cause=exc) from exc
        if not isinstance(payload, dict):
            raise _bad_oauth("OAuth state payload is not a dict.")
        redirect_to = payload.get("redirect_to")
        if redirect_to is not None and not isinstance(redirect_to, str):
            raise _bad_oauth("OAuth state redirect_to is not a string.")

        # 2. Exchange code for tokens.
        client_kwargs: dict[str, object] = {"timeout": 10.0}
        if self._transport is not None:
            client_kwargs["transport"] = self._transport
        async with httpx.AsyncClient(**client_kwargs) as client:  # type: ignore[arg-type]
            try:
                token_resp = await client.post(
                    _TOKEN_URL,
                    data={
                        "code": code,
                        "client_id": self._client_id,
                        "client_secret": self._client_secret,
                        "redirect_uri": self._redirect_uri,
                        "grant_type": "authorization_code",
                    },
                )
            except httpx.HTTPError as exc:
                raise _bad_oauth(
                    f"Google token endpoint unreachable: {exc!r}", cause=exc,
                ) from exc
        if token_resp.status_code >= 400:
            raise _bad_oauth(
                f"Google rejected token exchange (status={token_resp.status_code}).",
            )
        try:
            token_body = token_resp.json()
        except ValueError as exc:
            raise _bad_oauth(
                "Google token response was not JSON.", cause=exc,
            ) from exc
        access_token = token_body.get("access_token") if isinstance(token_body, dict) else None
        if not isinstance(access_token, str):
            raise _bad_oauth("Google token response missing access_token.")

        # 3. Fetch userinfo.
        async with httpx.AsyncClient(**client_kwargs) as client:  # type: ignore[arg-type]
            try:
                info_resp = await client.get(
                    _USERINFO_URL,
                    headers={"Authorization": f"Bearer {access_token}"},
                )
            except httpx.HTTPError as exc:
                raise _bad_oauth(
                    f"Google userinfo unreachable: {exc!r}", cause=exc,
                ) from exc
        if info_resp.status_code >= 400:
            raise _bad_oauth(
                f"Google userinfo rejected (status={info_resp.status_code}).",
            )
        try:
            info = info_resp.json()
        except ValueError as exc:
            raise _bad_oauth("Google userinfo not JSON.", cause=exc) from exc
        if not isinstance(info, dict):
            raise _bad_oauth("Google userinfo not a dict.")
        sub = info.get("sub")
        email = info.get("email")
        verified = info.get("email_verified")
        name = info.get("name")
        if not isinstance(sub, str) or not isinstance(email, str):
            raise _bad_oauth("Google userinfo missing sub/email.")
        if not bool(verified):
            raise _bad_oauth(
                "Google account email is not verified; cannot sign in.",
            )

        # 4. Link/create user.
        normalized_email = email.strip().lower()
        prior = await self._identities.find_user_by_provider_subject(
            provider="google", subject=sub,
        )
        user = await self._identities.link_or_create(
            provider="google",
            subject=sub,
            email=normalized_email,
            display_name=name if isinstance(name, str) else None,
        )
        is_new = prior is None
        logger.info(
            "google_oauth_signed_in",
            user_id=str(user.id),
            email=normalized_email,
            is_new_user=is_new,
        )
        return GoogleAuthResult(user=user, is_new_user=is_new, redirect_to=redirect_to)


