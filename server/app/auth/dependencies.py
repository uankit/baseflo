"""FastAPI dependencies for tenant + user context."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID

from fastapi import Request

from app.auth.cookies import read_session_cookie
from app.auth.magic_link import UserHandle
from app.auth.sessions import SessionService
from app.core.config import get_config
from app.core.context import TenantCtx, try_get_tenant_ctx
from app.core.errors import UnauthorizedError
from app.db.models.user import User
from app.db.session import open_session
from app.repositories.sessions import SessionRecordRepository


__all__ = [
    "AuthenticatedSession",
    "require_authenticated_session",
    "require_tenant",
    "require_user",
]


@dataclass(frozen=True, slots=True)
class AuthenticatedSession:
    """A validated browser/API session before an active org is required."""

    user: UserHandle
    session_id: UUID
    expires_at: datetime


def require_tenant() -> TenantCtx:
    """Use as `tenant: TenantCtx = Depends(require_tenant)` on protected routes.

    Raises 401 (BF-AUTH-001) when no tenant context is set on the request.
    """
    ctx = try_get_tenant_ctx()
    if ctx is None:
        raise UnauthorizedError(
            message=(
                "Authentication required. In M0 dev mode, set X-Baseflo-Org-Id "
                "(and optionally X-Baseflo-User-Id) on every request."
            )
        )
    return ctx


async def require_authenticated_session(request: Request) -> AuthenticatedSession:
    """Resolve the session cookie without requiring an active org.

    Used by bootstrap routes (`POST /api/v1/orgs`) where a freshly-signed-in
    user has no memberships yet. Routes that need tenant scope should use
    `require_tenant` — RLS isolation is keyed on the org, not the user.

    Raises 401 (BF-AUTH-001) when the cookie is missing, expired, or revoked.
    """
    raw_token = read_session_cookie(request)
    if raw_token is None:
        raise UnauthorizedError(
            "Authentication required. Sign in via magic link or Google.",
        )
    config = get_config()
    async with open_session() as session:
        service = SessionService(
            repo=SessionRecordRepository(session),
            ttl=timedelta(days=config.session_ttl_days),
        )
        resolved = await service.validate(raw_token)
        if resolved is None:
            raise UnauthorizedError("Session has expired or been revoked.")
        user = await session.get(User, resolved.user_id)
        if user is None:
            raise UnauthorizedError("User not found.")
        return AuthenticatedSession(
            user=UserHandle(id=user.id, email=user.email),
            session_id=resolved.session_id,
            expires_at=resolved.expires_at,
        )


async def require_user(request: Request) -> UserHandle:
    """Resolve the session cookie to a user without requiring an active org."""
    return (await require_authenticated_session(request)).user
