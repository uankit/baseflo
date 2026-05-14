"""FastAPI dependencies for authentication and role enforcement."""

from __future__ import annotations

from typing import Annotated, Callable
from uuid import UUID

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select

from app.auth.service import decode_access_token
from app.core.context import TenantCtx, set_tenant_ctx
from app.core.enums import MembershipStatus, Role
from app.core.errors import AuthError
from app.db.models import Membership
from app.db.session import open_session

_security = HTTPBearer(auto_error=False)


async def require_auth(
    request: Request,
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(_security)
    ] = None,
) -> TenantCtx:
    """Validate access JWT and confirm an active membership exists."""
    token = (
        credentials.credentials if credentials else None
    ) or request.cookies.get("access_token")
    if not token:
        raise AuthError(
            message="Authentication required",
            code="AUTH_MISSING_CREDENTIALS",
            status_hint=401,
        )

    payload = decode_access_token(token)
    user_id_str = payload.get("sub")
    org_id_str = payload.get("org")
    if not user_id_str or not org_id_str:
        raise AuthError(
            message="Malformed token payload",
            code="AUTH_TOKEN_MALFORMED",
            status_hint=401,
        )

    user_id = UUID(user_id_str)
    org_id = UUID(org_id_str)

    async with open_session() as session:
        result = await session.execute(
            select(Membership.id).where(
                Membership.user_id == user_id,
                Membership.organization_id == org_id,
                Membership.status == MembershipStatus.ACTIVE,
            )
        )
        if result.scalar_one_or_none() is None:
            raise AuthError(
                message="No active membership for this organization",
                code="AUTH_MEMBERSHIP_INACTIVE",
                status_hint=403,
            )

    ctx = TenantCtx(organization_id=org_id, user_id=user_id)
    set_tenant_ctx(ctx)
    return ctx


def require_role(*allowed: Role) -> Callable[..., Any]:
    """Dependency factory: require the caller's role to be one of `allowed`.

    Usage:
        @router.post("/invitations", dependencies=[Depends(require_role(Role.OWNER, Role.ADMIN))])
    """

    async def _check(
        ctx: Annotated[TenantCtx, Depends(require_auth)],
    ) -> TenantCtx:
        async with open_session() as session:
            result = await session.execute(
                select(Membership.role).where(
                    Membership.user_id == ctx.user_id,
                    Membership.organization_id == ctx.organization_id,
                    Membership.status == MembershipStatus.ACTIVE,
                )
            )
            role = result.scalar_one_or_none()
        if role not in allowed:
            raise AuthError(
                message=f"Required role: one of {[r.value for r in allowed]}",
                code="AUTH_INSUFFICIENT_ROLE",
                status_hint=403,
            )
        return ctx

    return _check
