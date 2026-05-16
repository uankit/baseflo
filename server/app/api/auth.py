"""Auth routes: magic link, refresh, /me, logout, invitations."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, Request, Response, status
from pydantic import BaseModel, EmailStr, Field

from app.auth.dependencies import require_auth, require_role
from app.auth.service import (
    INVITATION_TTL,
    MAGIC_LINK_TTL,
    REFRESH_TOKEN_TTL,
    create_access_token,
    generate_org_slug,
    generate_token,
    hash_token,
    issue_refresh_token,
    workspace_name_from_email,
)
from app.auth.store import (
    AuthRequestContext,
    AuthSessionRecord,
    InvitationRecord,
    accept_invitation_record,
    consume_magic_link_sign_in,
    create_invitation_record,
    create_magic_link_challenge,
    load_user_session,
    revoke_refresh_session,
    rotate_refresh_session,
)
from app.config import get_settings
from app.core.context import TenantCtx
from app.core.enums import MembershipStatus, OrgPlan, Role, UserStatus
from app.core.errors import AuthError, ValidationError

logger = logging.getLogger("baseflo.auth")
router = APIRouter(tags=["auth"])

_settings = get_settings()


class MagicLinkRequest(BaseModel):
    email: EmailStr


class MagicLinkVerifyRequest(BaseModel):
    email: EmailStr
    token: str = Field(min_length=1, max_length=200)


class InvitationCreateRequest(BaseModel):
    email: EmailStr
    role: Role = Role.MEMBER


class InvitationAcceptRequest(BaseModel):
    token: str = Field(min_length=1, max_length=200)


class OkResponse(BaseModel):
    ok: bool = True


class UserDTO(BaseModel):
    id: str
    email: str
    status: UserStatus


class OrganizationDTO(BaseModel):
    id: str
    name: str
    slug: str
    plan: OrgPlan


class MembershipDTO(BaseModel):
    organization: OrganizationDTO
    role: Role
    status: MembershipStatus


class AuthResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserDTO
    current_organization: OrganizationDTO
    memberships: list[MembershipDTO]


class MeResponse(BaseModel):
    user: UserDTO
    current_organization: OrganizationDTO
    memberships: list[MembershipDTO]


class InvitationDTO(BaseModel):
    id: str
    email: str
    role: Role
    organization_id: str
    expires_at: datetime


def _request_context(request: Request) -> AuthRequestContext:
    user_agent = request.headers.get("user-agent")
    return AuthRequestContext(
        ip_address=request.client.host if request.client else None,
        user_agent=user_agent[:500] if user_agent else None,
    )


def _set_auth_cookies(response: Response, access_token: str, refresh_token: str) -> None:
    secure = _settings.env != "local"
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=secure,
        samesite="lax",
        path="/",
        max_age=int(REFRESH_TOKEN_TTL.total_seconds()),
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=secure,
        samesite="lax",
        max_age=int(REFRESH_TOKEN_TTL.total_seconds()),
        path="/api/v1/auth/token",
    )


def _clear_auth_cookies(response: Response) -> None:
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/api/v1/auth/token")


def _user_dto(session: AuthSessionRecord) -> UserDTO:
    return UserDTO(
        id=str(session.user.id),
        email=session.user.email,
        status=session.user.status,
    )


def _org_dto(session: AuthSessionRecord) -> OrganizationDTO:
    organization = session.current_organization
    return OrganizationDTO(
        id=str(organization.id),
        name=organization.name,
        slug=organization.slug,
        plan=organization.plan,
    )


def _membership_dtos(session: AuthSessionRecord) -> list[MembershipDTO]:
    return [
        MembershipDTO(
            organization=OrganizationDTO(
                id=str(membership.organization.id),
                name=membership.organization.name,
                slug=membership.organization.slug,
                plan=membership.organization.plan,
            ),
            role=membership.role,
            status=membership.status,
        )
        for membership in session.memberships
    ]


def _auth_response(session: AuthSessionRecord, *, access_token: str, refresh_token: str) -> AuthResponse:
    return AuthResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=_user_dto(session),
        current_organization=_org_dto(session),
        memberships=_membership_dtos(session),
    )


def _access_token_for(session: AuthSessionRecord) -> str:
    return create_access_token(
        user_id=str(session.user.id),
        organization_id=str(session.current_organization.id),
        email=session.user.email,
    )


def _invitation_dto(invitation: InvitationRecord) -> InvitationDTO:
    return InvitationDTO(
        id=str(invitation.id),
        email=invitation.email,
        role=invitation.role,
        organization_id=str(invitation.organization_id),
        expires_at=invitation.expires_at,
    )


@router.post("/magic-link", response_model=OkResponse, status_code=status.HTTP_202_ACCEPTED)
async def request_magic_link(body: MagicLinkRequest, request: Request) -> OkResponse:
    """Generate a magic-link token and record a sign-in challenge."""
    email = body.email.lower().strip()
    raw_token = generate_token()
    now = datetime.now(UTC)

    await create_magic_link_challenge(
        email=email,
        token_hash=hash_token(raw_token),
        expires_at=now + MAGIC_LINK_TTL,
        now=now,
        context=_request_context(request),
    )

    if _settings.env == "local":
        logger.warning("DEV MAGIC LINK for %s: %s", email, raw_token)
    else:
        logger.info("Magic link issued for %s (email delivery not configured)", email)

    return OkResponse()


@router.post("/magic-link/verify", response_model=AuthResponse)
async def verify_magic_link(
    body: MagicLinkVerifyRequest,
    request: Request,
    response: Response,
) -> AuthResponse:
    email = body.email.lower().strip()
    now = datetime.now(UTC)
    refresh_plain, refresh_hash = issue_refresh_token()

    session = await consume_magic_link_sign_in(
        email=email,
        token_hash=hash_token(body.token),
        now=now,
        context=_request_context(request),
        refresh_token_hash=refresh_hash,
        refresh_expires_at=now + REFRESH_TOKEN_TTL,
        new_workspace_name=workspace_name_from_email(email),
        new_workspace_slug=generate_org_slug(email),
    )

    access_token = _access_token_for(session)
    _set_auth_cookies(response, access_token, refresh_plain)
    return _auth_response(session, access_token=access_token, refresh_token=refresh_plain)


@router.post("/token/refresh", response_model=AuthResponse)
async def refresh_access_token(
    request: Request,
    response: Response,
    refresh_token_cookie: Annotated[str | None, Cookie(alias="refresh_token")] = None,
) -> AuthResponse:
    body_token: str | None = None
    try:
        payload = await request.json()
        body_token = payload.get("refresh_token") if isinstance(payload, dict) else None
    except Exception:
        pass

    token = body_token or refresh_token_cookie
    if not token:
        raise AuthError(
            message="Refresh token required",
            code="AUTH_REFRESH_MISSING",
            status_hint=401,
        )

    now = datetime.now(UTC)
    new_plain, new_hash = issue_refresh_token()
    session = await rotate_refresh_session(
        refresh_token_hash=hash_token(token),
        new_refresh_token_hash=new_hash,
        new_refresh_expires_at=now + REFRESH_TOKEN_TTL,
        now=now,
        context=_request_context(request),
    )

    access_token = _access_token_for(session)
    _set_auth_cookies(response, access_token, new_plain)
    return _auth_response(session, access_token=access_token, refresh_token=new_plain)


@router.post("/logout", response_model=OkResponse)
async def logout(
    request: Request,
    response: Response,
    refresh_token_cookie: Annotated[str | None, Cookie(alias="refresh_token")] = None,
) -> OkResponse:
    if refresh_token_cookie:
        await revoke_refresh_session(
            refresh_token_hash=hash_token(refresh_token_cookie),
            now=datetime.now(UTC),
            context=_request_context(request),
        )
    _clear_auth_cookies(response)
    return OkResponse()


@router.get("/me", response_model=MeResponse)
async def get_me(
    tenant: Annotated[TenantCtx, Depends(require_auth)],
) -> MeResponse:
    session = await load_user_session(
        user_id=tenant.user_id,
        organization_id=tenant.organization_id,
    )
    return MeResponse(
        user=_user_dto(session),
        current_organization=_org_dto(session),
        memberships=_membership_dtos(session),
    )


@router.post(
    "/invitations",
    response_model=InvitationDTO,
    dependencies=[Depends(require_role(Role.OWNER, Role.ADMIN))],
)
async def create_invitation(
    body: InvitationCreateRequest,
    request: Request,
    tenant: Annotated[TenantCtx, Depends(require_auth)],
) -> InvitationDTO:
    """Invite an email to the active organization."""
    email = body.email.lower().strip()
    if body.role == Role.OWNER:
        raise ValidationError(
            message="Cannot invite another OWNER. Transfer ownership instead.",
            code="INVITATION_OWNER_NOT_ALLOWED",
            status_hint=400,
        )

    raw_token = generate_token()
    now = datetime.now(UTC)
    invitation = await create_invitation_record(
        organization_id=tenant.organization_id,
        invited_by_user_id=tenant.user_id,
        email=email,
        role=body.role,
        token_hash=hash_token(raw_token),
        expires_at=now + INVITATION_TTL,
        now=now,
        context=_request_context(request),
    )

    if _settings.env == "local":
        logger.warning(
            "DEV INVITATION for %s to org %s: %s",
            email,
            tenant.organization_id,
            raw_token,
        )
    else:
        logger.info("Invitation issued for %s (email delivery not configured)", email)

    return _invitation_dto(invitation)


@router.post("/invitations/accept", response_model=AuthResponse)
async def accept_invitation(
    body: InvitationAcceptRequest,
    request: Request,
    response: Response,
) -> AuthResponse:
    now = datetime.now(UTC)
    refresh_plain, refresh_hash = issue_refresh_token()
    session = await accept_invitation_record(
        invitation_token_hash=hash_token(body.token),
        now=now,
        context=_request_context(request),
        refresh_token_hash=refresh_hash,
        refresh_expires_at=now + REFRESH_TOKEN_TTL,
    )

    access_token = _access_token_for(session)
    _set_auth_cookies(response, access_token, refresh_plain)
    return _auth_response(session, access_token=access_token, refresh_token=refresh_plain)
