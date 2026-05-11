"""Real auth middleware.

Per docs/40-features/AUTH.md §3.3. Resolves a request to `TenantCtx` using
the cookie + dev-header chain in `app.auth.resolver`. The DB session is
opened *lazily* — only when a session cookie is present. Requests that go
through the dev-header fallback (LOCAL env only) never touch the DB, which
preserves the unit-test path that does not stand up Postgres.

Replaces the M0 `DevAuthMiddleware`. Honors session cookies in every
environment; honors `X-Baseflo-Org-Id` headers only when `BASEFLO_ENV=local`.
"""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.errors import request_id_var
from app.auth.cookies import read_session_cookie
from app.auth.resolver import AuthResolver, parse_dev_headers
from app.auth.sessions import SessionService
from app.core.config import Environment, get_config
from app.core.context import (
    TenantCtx,
    clear_tenant_ctx,
    set_tenant_ctx,
)
from app.db.session import open_session
from app.repositories.memberships import MembershipRepository
from app.repositories.sessions import SessionRecordRepository

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from starlette.responses import Response


__all__ = ["AuthMiddleware", "install_auth_middleware"]


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        request_id = request_id_var.get() or "req_unknown"
        ctx = await self._resolve(request, request_id)
        if ctx is not None:
            set_tenant_ctx(ctx)
        try:
            return await call_next(request)
        finally:
            if ctx is not None:
                clear_tenant_ctx()

    async def _resolve(
        self, request: Request, request_id: str,
    ) -> TenantCtx | None:
        config = get_config()
        raw_cookie = read_session_cookie(request)
        if raw_cookie is not None:
            ctx = await _resolve_via_cookie(
                request=request, request_id=request_id,
            )
            if ctx is not None:
                return ctx
        if config.env == Environment.LOCAL:
            return parse_dev_headers(request=request, request_id=request_id)
        return None


async def _resolve_via_cookie(
    *, request: Request, request_id: str,
) -> TenantCtx | None:
    config = get_config()
    async with open_session() as session:
        resolver = AuthResolver(
            sessions=SessionService(
                repo=SessionRecordRepository(session),
                ttl=timedelta(days=config.session_ttl_days),
            ),
            memberships=MembershipRepository(session),
            env=config.env,
        )
        return await resolver.resolve(request=request, request_id=request_id)


def install_auth_middleware(app: object) -> None:
    """Install the auth middleware on a FastAPI app."""
    from fastapi import FastAPI

    if not isinstance(app, FastAPI):
        raise TypeError("install_auth_middleware expects a FastAPI app.")
    app.add_middleware(AuthMiddleware)
