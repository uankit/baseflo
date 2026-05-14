"""Auth routes — magic link, refresh, /me, logout, invitations."""

from __future__ import annotations

import logging
import re
import secrets
from datetime import UTC, datetime
from typing import Annotated, Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Cookie, Depends, Request, Response, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select

from app.auth.dependencies import require_auth, require_role
from app.auth.service import (
    INVITATION_TTL,
    MAGIC_LINK_TTL,
    REFRESH_TOKEN_TTL,
    create_access_token,
    generate_token,
    hash_token,
    issue_refresh_token,
    verify_token,
)
from app.config import get_settings
from app.core.context import TenantCtx
from app.core.enums import (
    AuthEventKind,
    MagicLinkPurpose,
    MembershipStatus,
    OrgPlan,
    Role,
    UserStatus,
)
from app.core.errors import AuthError, ConflictError, NotFoundError, ValidationError
from app.db.models import (
    AuthEvent,
    Invitation,
    MagicLinkToken,
    Membership,
    Organization,
    RefreshToken,
    User,
)
from app.db.session import open_session

logger = logging.getLogger("baseflo.auth")
router = APIRouter(tags=["auth"])

_settings = get_settings()
_SLUG_RE = re.compile(r"[^a-z0-9-]+")


# ============================================================================
# Request / response schemas
# ============================================================================


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


# ============================================================================
# Helpers
# ============================================================================


def _client_ip(request: Request) -> str | None:
    # TODO: respect X-Forwarded-For when behind a trusted proxy.
    return request.client.host if request.client else None


def _user_agent(request: Request) -> str | None:
    ua = request.headers.get("user-agent")
    return ua[:500] if ua else None


def _slugify_email_local(email: str) -> str:
    local = email.split("@", 1)[0].lower()
    return (_SLUG_RE.sub("-", local).strip("-") or "org")[:50]


def _generate_org_slug(email: str) -> str:
    return f"{_slugify_email_local(email)}-{secrets.token_hex(4)}"


def _set_auth_cookies(response: Response, access_token: str, refresh_token: str) -> None:
    secure = _settings.env != "local"
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=secure,
        samesite="lax",
        max_age=int(REFRESH_TOKEN_TTL.total_seconds()),
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=secure,
        samesite="lax",
        max_age=int(REFRESH_TOKEN_TTL.total_seconds()),
        path="/auth/token",
    )


def _clear_auth_cookies(response: Response) -> None:
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token", path="/auth/token")


def _user_dto(user: User) -> UserDTO:
    return UserDTO(
        id=str(user.id),
        email=user.email,
        status=user.status,
    )


def _org_dto(org: Organization) -> OrganizationDTO:
    return OrganizationDTO(
        id=str(org.id),
        name=org.name,
        slug=org.slug,
        plan=org.plan,
    )


def _membership_dto(membership: Membership, org: Organization) -> MembershipDTO:
    return MembershipDTO(
        organization=_org_dto(org),
        role=membership.role,
        status=membership.status,
    )


# ============================================================================
# Magic link
# ============================================================================


@router.post("/magic-link", response_model=OkResponse, status_code=status.HTTP_202_ACCEPTED)
async def request_magic_link(body: MagicLinkRequest, request: Request) -> OkResponse:
    """Generate a magic-link token and (in prod) email it.

    The token is NEVER returned in the API response. In local/dev the token is
    logged at WARNING level so you can copy it from server logs.

    TODO: rate-limit by IP and email (e.g. 5/min, 20/hour). Today this endpoint
    is open to abuse — a real email backend or SMS gateway costs money on each
    call, so this matters before any deployment.
    """
    email = body.email.lower().strip()
    raw_token = generate_token()
    now = datetime.now(UTC)

    async with open_session() as session:
        session.add(
            MagicLinkToken(
                email=email,
                token_hash=hash_token(raw_token),
                purpose=MagicLinkPurpose.SIGN_IN,
                expires_at=now + MAGIC_LINK_TTL,
                ip_address=_client_ip(request),
                user_agent=_user_agent(request),
            )
        )
        session.add(
            AuthEvent(
                kind=AuthEventKind.MAGIC_LINK_REQUESTED,
                ip_address=_client_ip(request),
                user_agent=_user_agent(request),
                details={"email": email},
                occurred_at=now,
            )
        )

    if _settings.env == "local":
        logger.warning("DEV MAGIC LINK for %s: %s", email, raw_token)
    else:
        # TODO: send via email service (Resend/SendGrid/Postmark).
        logger.info("Magic link issued for %s (email delivery not configured)", email)

    return OkResponse()


@router.post("/magic-link/verify", response_model=AuthResponse)
async def verify_magic_link(
    body: MagicLinkVerifyRequest, request: Request, response: Response,
) -> AuthResponse:
    email = body.email.lower().strip()
    now = datetime.now(UTC)
    ip = _client_ip(request)
    ua = _user_agent(request)

    async with open_session() as session:
        result = await session.execute(
            select(MagicLinkToken)
            .where(
                MagicLinkToken.email == email,
                MagicLinkToken.consumed_at.is_(None),
                MagicLinkToken.expires_at > now,
                MagicLinkToken.purpose == MagicLinkPurpose.SIGN_IN,
            )
            .order_by(MagicLinkToken.created_at.desc())
            .limit(1)
        )
        mlt = result.scalar_one_or_none()

        if mlt is None or not verify_token(body.token, mlt.token_hash):
            session.add(
                AuthEvent(
                    kind=AuthEventKind.LOGIN_FAILED,
                    ip_address=ip,
                    user_agent=ua,
                    details={"reason": "invalid_magic_link", "email": email},
                    occurred_at=now,
                )
            )
            raise AuthError(
                message="Invalid or expired magic link",
                code="AUTH_MAGIC_LINK_INVALID",
                status_hint=400,
            )

        mlt.consumed_at = now

        result = await session.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        is_new_user = user is None
        if is_new_user:
            user = User(email=email, status=UserStatus.ACTIVE)
            session.add(user)
            await session.flush()
            session.add(
                AuthEvent(
                    kind=AuthEventKind.SIGNUP,
                    user_id=user.id,
                    ip_address=ip,
                    user_agent=ua,
                    occurred_at=now,
                )
            )

        result = await session.execute(
            select(Membership, Organization)
            .join(Organization, Membership.organization_id == Organization.id)
            .where(
                Membership.user_id == user.id,
                Membership.status == MembershipStatus.ACTIVE,
            )
            .order_by(Membership.joined_at.asc())
        )
        memberships_with_orgs = list(result.all())

        if not memberships_with_orgs:
            org = Organization(
                name=f"{_slugify_email_local(email).replace('-', ' ').title()}'s Workspace",
                slug=_generate_org_slug(email),
                plan=OrgPlan.FREE,
            )
            session.add(org)
            await session.flush()
            membership = Membership(
                user_id=user.id,
                organization_id=org.id,
                role=Role.OWNER,
                status=MembershipStatus.ACTIVE,
                joined_at=now,
            )
            session.add(membership)
            await session.flush()
            session.add(
                AuthEvent(
                    kind=AuthEventKind.ORG_CREATED,
                    user_id=user.id,
                    organization_id=org.id,
                    ip_address=ip,
                    user_agent=ua,
                    details={"reason": "auto_on_first_signin"},
                    occurred_at=now,
                )
            )
            session.add(
                AuthEvent(
                    kind=AuthEventKind.MEMBERSHIP_CREATED,
                    user_id=user.id,
                    organization_id=org.id,
                    ip_address=ip,
                    user_agent=ua,
                    details={"role": Role.OWNER.value},
                    occurred_at=now,
                )
            )
            memberships_with_orgs = [(membership, org)]

        current_membership, current_org = memberships_with_orgs[0]

        refresh_plain, refresh_hash = issue_refresh_token()
        session.add(
            RefreshToken(
                user_id=user.id,
                organization_id=current_org.id,
                token_hash=refresh_hash,
                expires_at=now + REFRESH_TOKEN_TTL,
                created_at=now,
            )
        )
        session.add(
            AuthEvent(
                kind=AuthEventKind.MAGIC_LINK_CONSUMED,
                user_id=user.id,
                organization_id=current_org.id,
                ip_address=ip,
                user_agent=ua,
                occurred_at=now,
            )
        )
        session.add(
            AuthEvent(
                kind=AuthEventKind.LOGIN,
                user_id=user.id,
                organization_id=current_org.id,
                ip_address=ip,
                user_agent=ua,
                occurred_at=now,
            )
        )
        session.add(
            AuthEvent(
                kind=AuthEventKind.REFRESH_TOKEN_ISSUED,
                user_id=user.id,
                organization_id=current_org.id,
                ip_address=ip,
                user_agent=ua,
                occurred_at=now,
            )
        )

    access_token = create_access_token(
        user_id=str(user.id),
        organization_id=str(current_org.id),
        email=user.email,
    )
    _set_auth_cookies(response, access_token, refresh_plain)

    return AuthResponse(
        access_token=access_token,
        refresh_token=refresh_plain,
        user=_user_dto(user),
        current_organization=_org_dto(current_org),
        memberships=[_membership_dto(m, o) for m, o in memberships_with_orgs],
    )


# ============================================================================
# Token refresh + logout
# ============================================================================


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
    token_hash = hash_token(token)

    async with open_session() as session:
        result = await session.execute(
            select(RefreshToken, User, Organization)
            .join(User, RefreshToken.user_id == User.id)
            .join(Organization, RefreshToken.organization_id == Organization.id)
            .where(RefreshToken.token_hash == token_hash)
        )
        row = result.one_or_none()
        if row is None:
            raise AuthError(
                message="Invalid refresh token",
                code="AUTH_REFRESH_INVALID",
                status_hint=401,
            )
        rt, user, org = row

        if rt.revoked_at is not None or rt.expires_at <= now:
            raise AuthError(
                message="Refresh token expired or revoked",
                code="AUTH_REFRESH_EXPIRED",
                status_hint=401,
            )
        if user.status != UserStatus.ACTIVE:
            raise AuthError(
                message="User is not active",
                code="AUTH_USER_INACTIVE",
                status_hint=403,
            )

        result = await session.execute(
            select(Membership.id).where(
                Membership.user_id == user.id,
                Membership.organization_id == org.id,
                Membership.status == MembershipStatus.ACTIVE,
            )
        )
        if result.scalar_one_or_none() is None:
            raise AuthError(
                message="Membership no longer active",
                code="AUTH_MEMBERSHIP_INACTIVE",
                status_hint=403,
            )

        new_plain, new_hash = issue_refresh_token()
        new_rt = RefreshToken(
            user_id=user.id,
            organization_id=org.id,
            token_hash=new_hash,
            expires_at=now + REFRESH_TOKEN_TTL,
            created_at=now,
        )
        session.add(new_rt)
        await session.flush()

        rt.revoked_at = now
        rt.replaced_by_id = new_rt.id

        result = await session.execute(
            select(Membership, Organization)
            .join(Organization, Membership.organization_id == Organization.id)
            .where(
                Membership.user_id == user.id,
                Membership.status == MembershipStatus.ACTIVE,
            )
            .order_by(Membership.joined_at.asc())
        )
        memberships_with_orgs = list(result.all())

        session.add(
            AuthEvent(
                kind=AuthEventKind.REFRESH_TOKEN_ROTATED,
                user_id=user.id,
                organization_id=org.id,
                ip_address=_client_ip(request),
                user_agent=_user_agent(request),
                occurred_at=now,
            )
        )

    access_token = create_access_token(
        user_id=str(user.id),
        organization_id=str(org.id),
        email=user.email,
    )
    _set_auth_cookies(response, access_token, new_plain)

    return AuthResponse(
        access_token=access_token,
        refresh_token=new_plain,
        user=_user_dto(user),
        current_organization=_org_dto(org),
        memberships=[_membership_dto(m, o) for m, o in memberships_with_orgs],
    )


@router.post("/logout", response_model=OkResponse)
async def logout(
    request: Request,
    response: Response,
    refresh_token_cookie: Annotated[str | None, Cookie(alias="refresh_token")] = None,
) -> OkResponse:
    """Revoke the current refresh token and clear cookies."""
    now = datetime.now(UTC)

    if refresh_token_cookie:
        token_hash = hash_token(refresh_token_cookie)
        async with open_session() as session:
            result = await session.execute(
                select(RefreshToken).where(
                    RefreshToken.token_hash == token_hash,
                    RefreshToken.revoked_at.is_(None),
                )
            )
            rt = result.scalar_one_or_none()
            if rt is not None:
                rt.revoked_at = now
                session.add(
                    AuthEvent(
                        kind=AuthEventKind.REFRESH_TOKEN_REVOKED,
                        user_id=rt.user_id,
                        organization_id=rt.organization_id,
                        ip_address=_client_ip(request),
                        user_agent=_user_agent(request),
                        details={"reason": "logout"},
                        occurred_at=now,
                    )
                )
                session.add(
                    AuthEvent(
                        kind=AuthEventKind.LOGOUT,
                        user_id=rt.user_id,
                        organization_id=rt.organization_id,
                        ip_address=_client_ip(request),
                        user_agent=_user_agent(request),
                        occurred_at=now,
                    )
                )

    _clear_auth_cookies(response)
    return OkResponse()


# ============================================================================
# /me
# ============================================================================


@router.get("/me", response_model=MeResponse)
async def get_me(
    tenant: Annotated[TenantCtx, Depends(require_auth)],
) -> MeResponse:
    async with open_session() as session:
        user = await session.get(User, tenant.user_id)
        if user is None:
            raise NotFoundError(
                message="User not found",
                code="USER_NOT_FOUND",
                status_hint=404,
            )

        result = await session.execute(
            select(Membership, Organization)
            .join(Organization, Membership.organization_id == Organization.id)
            .where(
                Membership.user_id == user.id,
                Membership.status == MembershipStatus.ACTIVE,
            )
            .order_by(Membership.joined_at.asc())
        )
        memberships_with_orgs = list(result.all())

        current_org: Organization | None = next(
            (o for _, o in memberships_with_orgs if o.id == tenant.organization_id),
            None,
        )
        if current_org is None:
            raise AuthError(
                message="Active organization not found",
                code="AUTH_ORG_NOT_FOUND",
                status_hint=403,
            )

    return MeResponse(
        user=_user_dto(user),
        current_organization=_org_dto(current_org),
        memberships=[_membership_dto(m, o) for m, o in memberships_with_orgs],
    )


# ============================================================================
# Invitations
# ============================================================================


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
    """Invite an email to the active organization.

    Token is sent via email (dev: logged to stdout). Token is NEVER returned.
    """
    email = body.email.lower().strip()
    if body.role == Role.OWNER:
        raise ValidationError(
            message="Cannot invite another OWNER. Transfer ownership instead.",
            code="INVITATION_OWNER_NOT_ALLOWED",
            status_hint=400,
        )

    now = datetime.now(UTC)
    raw_token = generate_token()

    async with open_session() as session:
        result = await session.execute(
            select(Membership)
            .join(User, Membership.user_id == User.id)
            .where(
                User.email == email,
                Membership.organization_id == tenant.organization_id,
                Membership.status == MembershipStatus.ACTIVE,
            )
        )
        if result.scalar_one_or_none() is not None:
            raise ConflictError(
                message="User is already a member of this organization",
                code="MEMBERSHIP_EXISTS",
                status_hint=409,
            )

        invitation = Invitation(
            organization_id=tenant.organization_id,
            email=email,
            role=body.role,
            invited_by_user_id=tenant.user_id,
            token_hash=hash_token(raw_token),
            expires_at=now + INVITATION_TTL,
        )
        session.add(invitation)
        await session.flush()

        session.add(
            AuthEvent(
                kind=AuthEventKind.INVITATION_SENT,
                user_id=tenant.user_id,
                organization_id=tenant.organization_id,
                ip_address=_client_ip(request),
                user_agent=_user_agent(request),
                details={"invited_email": email, "role": body.role.value},
                occurred_at=now,
            )
        )

        result_dto = InvitationDTO(
            id=str(invitation.id),
            email=invitation.email,
            role=invitation.role,
            organization_id=str(invitation.organization_id),
            expires_at=invitation.expires_at,
        )

    if _settings.env == "local":
        logger.warning(
            "DEV INVITATION for %s to org %s: %s",
            email, tenant.organization_id, raw_token,
        )
    else:
        # TODO: send via email service.
        logger.info("Invitation issued for %s (email delivery not configured)", email)

    return result_dto


@router.post("/invitations/accept", response_model=AuthResponse)
async def accept_invitation(
    body: InvitationAcceptRequest, request: Request, response: Response,
) -> AuthResponse:
    """Accept an invitation token. Creates user if needed; creates membership; issues tokens."""
    now = datetime.now(UTC)
    token_hash_value = hash_token(body.token)
    ip = _client_ip(request)
    ua = _user_agent(request)

    async with open_session() as session:
        result = await session.execute(
            select(Invitation, Organization)
            .join(Organization, Invitation.organization_id == Organization.id)
            .where(Invitation.token_hash == token_hash_value)
        )
        row = result.one_or_none()
        if row is None:
            raise AuthError(
                message="Invalid invitation",
                code="INVITATION_INVALID",
                status_hint=400,
            )
        invitation, org = row

        if invitation.accepted_at is not None:
            raise ConflictError(
                message="Invitation already accepted",
                code="INVITATION_USED",
                status_hint=409,
            )
        if invitation.revoked_at is not None:
            raise AuthError(
                message="Invitation revoked",
                code="INVITATION_REVOKED",
                status_hint=400,
            )
        if invitation.expires_at <= now:
            raise AuthError(
                message="Invitation expired",
                code="INVITATION_EXPIRED",
                status_hint=400,
            )

        result = await session.execute(select(User).where(User.email == invitation.email))
        user = result.scalar_one_or_none()
        is_new_user = user is None
        if is_new_user:
            user = User(email=invitation.email, status=UserStatus.ACTIVE)
            session.add(user)
            await session.flush()
            session.add(
                AuthEvent(
                    kind=AuthEventKind.SIGNUP,
                    user_id=user.id,
                    ip_address=ip,
                    user_agent=ua,
                    details={"via": "invitation"},
                    occurred_at=now,
                )
            )

        result = await session.execute(
            select(Membership).where(
                Membership.user_id == user.id,
                Membership.organization_id == org.id,
            )
        )
        existing = result.scalar_one_or_none()
        if existing is not None:
            if existing.status == MembershipStatus.ACTIVE:
                raise ConflictError(
                    message="Already a member of this organization",
                    code="MEMBERSHIP_EXISTS",
                    status_hint=409,
                )
            existing.status = MembershipStatus.ACTIVE
            existing.role = invitation.role
            existing.joined_at = now
            existing.revoked_at = None
            membership = existing
        else:
            membership = Membership(
                user_id=user.id,
                organization_id=org.id,
                role=invitation.role,
                status=MembershipStatus.ACTIVE,
                joined_at=now,
            )
            session.add(membership)

        invitation.accepted_at = now

        session.add(
            AuthEvent(
                kind=AuthEventKind.INVITATION_ACCEPTED,
                user_id=user.id,
                organization_id=org.id,
                ip_address=ip,
                user_agent=ua,
                occurred_at=now,
            )
        )
        session.add(
            AuthEvent(
                kind=AuthEventKind.MEMBERSHIP_CREATED,
                user_id=user.id,
                organization_id=org.id,
                ip_address=ip,
                user_agent=ua,
                details={"role": invitation.role.value, "via": "invitation"},
                occurred_at=now,
            )
        )

        refresh_plain, refresh_hash = issue_refresh_token()
        session.add(
            RefreshToken(
                user_id=user.id,
                organization_id=org.id,
                token_hash=refresh_hash,
                expires_at=now + REFRESH_TOKEN_TTL,
                created_at=now,
            )
        )
        session.add(
            AuthEvent(
                kind=AuthEventKind.LOGIN,
                user_id=user.id,
                organization_id=org.id,
                ip_address=ip,
                user_agent=ua,
                occurred_at=now,
            )
        )

        result = await session.execute(
            select(Membership, Organization)
            .join(Organization, Membership.organization_id == Organization.id)
            .where(
                Membership.user_id == user.id,
                Membership.status == MembershipStatus.ACTIVE,
            )
            .order_by(Membership.joined_at.asc())
        )
        memberships_with_orgs = list(result.all())

    access_token = create_access_token(
        user_id=str(user.id),
        organization_id=str(org.id),
        email=user.email,
    )
    _set_auth_cookies(response, access_token, refresh_plain)

    return AuthResponse(
        access_token=access_token,
        refresh_token=refresh_plain,
        user=_user_dto(user),
        current_organization=_org_dto(org),
        memberships=[_membership_dto(m, o) for m, o in memberships_with_orgs],
    )
