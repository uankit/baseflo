"""Session-cookie helpers.

Per docs/40-features/AUTH.md §3.3 — httponly + secure (in non-local envs) +
sameSite=lax. Cookie attributes come from `AppConfig`; tests can override via
the standard pydantic-settings env-var path.
"""

from __future__ import annotations

from fastapi import Request, Response

from app.core.config import get_config

__all__ = ["clear_session_cookie", "read_session_cookie", "set_session_cookie"]


def set_session_cookie(response: Response, *, raw_token: str) -> None:
    config = get_config()
    response.set_cookie(
        key=config.session_cookie_name,
        value=raw_token,
        max_age=config.session_ttl_days * 86_400,
        httponly=True,
        secure=config.session_cookie_secure,
        samesite="lax",
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    config = get_config()
    response.delete_cookie(
        key=config.session_cookie_name,
        path="/",
        httponly=True,
        secure=config.session_cookie_secure,
        samesite="lax",
    )


def read_session_cookie(request: Request) -> str | None:
    config = get_config()
    return request.cookies.get(config.session_cookie_name)
