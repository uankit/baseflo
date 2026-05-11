"""FastAPI auth dependencies."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select

from app.auth.service import decode_access_token
from app.core.context import TenantCtx, set_tenant_ctx
from app.core.errors import BasefloError
from app.db.models import User
from app.db.session import AsyncSessionLocal

security = HTTPBearer(auto_error=False)


async def require_auth(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)] = None,
) -> TenantCtx:
    """Extract and validate JWT from Authorization header."""
    token = None

    # Try header first
    if credentials is not None:
        token = credentials.credentials
    else:
        # Fallback to cookie
        token = request.cookies.get("access_token")

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = decode_access_token(token)
    except BasefloError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")
    org_id = payload.get("org")
    email = payload.get("email")

    if not user_id or not org_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Verify user still exists and is active
    async with AsyncSessionLocal() as session:
        async with session.begin():
            result = await session.execute(
                select(User).where(User.id == UUID(user_id), User.is_active == True)
            )
            user = result.scalar_one_or_none()
            if user is None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="User not found or inactive",
                    headers={"WWW-Authenticate": "Bearer"},
                )

    ctx = TenantCtx(
        organization_id=UUID(org_id),
        user_id=UUID(user_id),
    )
    set_tenant_ctx(ctx)
    return ctx


async def optional_auth(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)] = None,
) -> TenantCtx | None:
    """Optional auth — returns None if no valid token."""
    try:
        return await require_auth(request, credentials)
    except HTTPException:
        return None
