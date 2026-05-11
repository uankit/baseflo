"""Auth routes — magic link + JWT."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select

from app.auth.dependencies import require_auth
from app.auth.service import (
    create_access_token,
    generate_magic_link_token,
    hash_token,
    verify_token_hash,
    MAGIC_LINK_EXPIRE_MINUTES,
)
from app.core.context import TenantCtx
from app.core.errors import BasefloError
from app.db.models import MagicLinkToken, Organization, User
from app.db.session import open_session

router = APIRouter()


class MagicLinkRequest(BaseModel):
    email: EmailStr


class MagicLinkResponse(BaseModel):
    message: str
    # For MVP we return the token directly since we don't have email sending set up.
    # In production this would be sent via email and not returned.
    dev_token: str | None = Field(
        default=None,
        description="Token for development/testing. In production this is sent via email.",
    )


class MagicLinkVerifyRequest(BaseModel):
    email: EmailStr
    token: str


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


class UserResponse(BaseModel):
    id: str
    email: str
    organization: dict


@router.post("/magic-link", response_model=MagicLinkResponse)
async def request_magic_link(body: MagicLinkRequest) -> MagicLinkResponse:
    """Request a magic link. Returns token directly for MVP (no email service)."""
    raw_token = generate_magic_link_token()
    token_hash = hash_token(raw_token)

    async with open_session() as session:
        mlt = MagicLinkToken(
            email=body.email.lower().strip(),
            token_hash=token_hash,
            expires_at=datetime.now(UTC) + timedelta(minutes=MAGIC_LINK_EXPIRE_MINUTES),
        )
        session.add(mlt)

    return MagicLinkResponse(
        message="Magic link generated. Use the token to verify.",
        dev_token=raw_token,
    )


@router.post("/magic-link/verify", response_model=AuthResponse)
async def verify_magic_link(body: MagicLinkVerifyRequest, response: Response) -> AuthResponse:
    """Verify magic link token and issue JWT access token."""
    email = body.email.lower().strip()

    async with open_session() as session:
        # Find the most recent unused token for this email
        result = await session.execute(
            select(MagicLinkToken)
            .where(
                MagicLinkToken.email == email,
                MagicLinkToken.consumed_at.is_(None),
                MagicLinkToken.expires_at > datetime.now(UTC),
            )
            .order_by(MagicLinkToken.created_at.desc())
            .limit(1)
        )
        mlt = result.scalar_one_or_none()

        if mlt is None:
            raise BasefloError(
                message="Invalid or expired magic link",
                error_code="BF-AUTH-002",
                status_code=400,
            )

        if not verify_token_hash(body.token, mlt.token_hash):
            raise BasefloError(
                message="Invalid magic link token",
                error_code="BF-AUTH-003",
                status_code=400,
            )

        # Mark as consumed
        mlt.consumed_at = datetime.now(UTC)

        # Find or create user + organization
        result = await session.execute(
            select(User).where(User.email == email)
        )
        user = result.scalar_one_or_none()

        if user is None:
            # Create organization first
            org_slug = email.split("@")[0].replace(".", "-").lower()[:50] + "-" + str(uuid4())[:8]
            org = Organization(
                name=email.split("@")[0].title() + "'s Organization",
                slug=org_slug,
            )
            session.add(org)
            await session.flush()

            # Create user
            user = User(
                organization_id=org.id,
                email=email,
                is_active=True,
            )
            session.add(user)
            await session.flush()

        org = await session.get(Organization, user.organization_id)
        if org is None:
            raise BasefloError(
                message="Organization not found",
                error_code="BF-AUTH-004",
                status_code=500,
            )

    # Issue JWT
    access_token = create_access_token(
        user_id=str(user.id),
        organization_id=str(org.id),
        email=user.email,
    )

    # Set cookie for web clients
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=False,  # Set True in production with HTTPS
        samesite="lax",
        max_age=60 * 60 * 24 * 7,  # 7 days
    )

    return AuthResponse(
        access_token=access_token,
        user={
            "id": str(user.id),
            "email": user.email,
            "organization_id": str(org.id),
        },
    )


@router.get("/me", response_model=UserResponse)
async def get_me(tenant: Annotated[TenantCtx, Depends(require_auth)]) -> UserResponse:
    """Get current authenticated user."""
    async with open_session() as session:
        result = await session.execute(
            select(User, Organization)
            .join(Organization, User.organization_id == Organization.id)
            .where(User.id == tenant.user_id)
        )
        row = result.one_or_none()
        if row is None:
            raise BasefloError(
                message="User not found",
                error_code="BF-AUTH-005",
                status_code=404,
            )
        user, org = row

    return UserResponse(
        id=str(user.id),
        email=user.email,
        organization={
            "id": str(org.id),
            "name": org.name,
            "slug": org.slug,
        },
    )


@router.post("/logout")
async def logout(response: Response) -> dict[str, str]:
    """Clear auth cookie."""
    response.delete_cookie("access_token")
    return {"message": "Logged out successfully"}
