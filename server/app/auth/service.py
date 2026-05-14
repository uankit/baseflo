"""Pure helpers for tokens. No DB or framework dependencies."""

from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

from jose import JWTError, jwt

from app.config import get_settings
from app.core.enums import TokenType
from app.core.errors import AuthError

_settings = get_settings()

ALGORITHM = "HS256"
ACCESS_TOKEN_TTL = timedelta(minutes=15)
REFRESH_TOKEN_TTL = timedelta(days=30)
MAGIC_LINK_TTL = timedelta(minutes=15)
INVITATION_TTL = timedelta(days=7)
OAUTH_STATE_TTL = timedelta(minutes=15)


def generate_token(nbytes: int = 32) -> str:
    """URL-safe random token. ~43 chars at default size."""
    return secrets.token_urlsafe(nbytes)


def hash_token(plaintext: str) -> str:
    """SHA-256 hex of a token. Storage form; we never need to recover the plaintext."""
    return hashlib.sha256(plaintext.encode("utf-8")).hexdigest()


def verify_token(plaintext: str, expected_hash: str) -> bool:
    """Constant-time compare against a stored hash."""
    return hmac.compare_digest(hash_token(plaintext), expected_hash)


def create_access_token(*, user_id: str, organization_id: str, email: str) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": user_id,
        "org": organization_id,
        "email": email,
        "type": TokenType.ACCESS.value,
        "iat": int(now.timestamp()),
        "exp": int((now + ACCESS_TOKEN_TTL).timestamp()),
    }
    return jwt.encode(
        payload,
        _settings.secret_key.get_secret_value(),
        algorithm=ALGORITHM,
    )


def decode_access_token(token: str) -> dict[str, Any]:
    try:
        payload = jwt.decode(
            token,
            _settings.secret_key.get_secret_value(),
            algorithms=[ALGORITHM],
        )
    except JWTError as exc:
        raise AuthError(
            message="Invalid or expired token",
            code="AUTH_TOKEN_INVALID",
            status_hint=401,
        ) from exc
    if payload.get("type") != TokenType.ACCESS.value:
        raise AuthError(
            message="Wrong token type",
            code="AUTH_TOKEN_TYPE_MISMATCH",
            status_hint=401,
        )
    return payload


def issue_refresh_token() -> tuple[str, str]:
    """Returns (plaintext, hash). Plaintext goes to the client; hash is stored."""
    plaintext = generate_token(48)
    return plaintext, hash_token(plaintext)


def encode_oauth_state(
    *,
    user_id: str,
    organization_id: str,
    kind: str,
    extra: dict[str, Any] | None = None,
) -> str:
    """Signed state for OAuth round-trip. Carries user/org/kind without DB hits."""
    now = datetime.now(UTC)
    payload = {
        "sub": user_id,
        "org": organization_id,
        "kind": kind,
        "type": "oauth_state",
        "iat": int(now.timestamp()),
        "exp": int((now + OAUTH_STATE_TTL).timestamp()),
    }
    for key, value in (extra or {}).items():
        if key in payload:
            raise ValueError(f"OAuth state extra field cannot override '{key}'")
        payload[key] = value
    return jwt.encode(
        payload,
        _settings.secret_key.get_secret_value(),
        algorithm=ALGORITHM,
    )


def decode_oauth_state(state: str) -> dict[str, Any]:
    try:
        payload = jwt.decode(
            state,
            _settings.secret_key.get_secret_value(),
            algorithms=[ALGORITHM],
        )
    except JWTError as exc:
        raise AuthError(
            message="Invalid or expired OAuth state",
            code="OAUTH_STATE_INVALID",
            status_hint=400,
        ) from exc
    if payload.get("type") != "oauth_state":
        raise AuthError(
            message="Wrong state type",
            code="OAUTH_STATE_TYPE_MISMATCH",
            status_hint=400,
        )
    return payload
