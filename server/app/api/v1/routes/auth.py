"""Auth API routes — magic link, Google OAuth, signout, /me.

Per docs/40-features/AUTH.md.
"""

from __future__ import annotations

from collections.abc import AsyncIterator  # noqa: TC003 - FastAPI resolves hints at runtime.
from dataclasses import dataclass
from datetime import timedelta
from typing import Annotated
from uuid import UUID  # noqa: TC003 - Pydantic/FastAPI resolve hints at runtime.

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import RedirectResponse
from itsdangerous import URLSafeTimedSerializer
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: TC002 - FastAPI resolves hints at runtime.

from app.auth.cookies import clear_session_cookie, set_session_cookie
from app.auth.dependencies import (
    AuthenticatedSession,
    require_authenticated_session,
    require_tenant,
)
from app.auth.magic_link import MagicLinkService
from app.auth.oauth.google import GoogleOAuthService
from app.auth.sessions import SessionService
from app.core.config import get_config
from app.core.context import TenantCtx, try_get_tenant_ctx  # noqa: TC001 - FastAPI resolves hints at runtime.
from app.core.errors import BasefloError
from app.db.models.user import User
from app.db.session import open_session
from app.repositories.magic_link_tokens import MagicLinkTokenRepository
from app.repositories.memberships import MembershipRepository
from app.repositories.oauth_identities import OAuthIdentityRepository
from app.repositories.sessions import SessionRecordRepository
from app.repositories.users import UserRepository
from app.services.email.sender import default_email_sender

__all__ = [
    "MagicLinkRequest",
    "MagicLinkResponse",
    "MeResponse",
    "get_google_login_services",
    "get_google_oauth_service",
    "get_magic_link_login_services",
    "get_magic_link_service",
    "get_session_service",
    "router",
]


router = APIRouter(prefix="/auth", tags=["auth"])


# ---------- Pydantic schemas ----------


class MagicLinkRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)


class MagicLinkResponse(BaseModel):
    accepted: bool = True
    expires_at: str | None = None


class MeResponse(BaseModel):
    user_id: str
    organization_id: str
    role: str | None
    session_id: str | None
    is_api_key: bool


# ---------- Web-app session shape (camelCase to match @baseflo/contracts) ----------
#
# Used by the SPA at app.baseflo.com. Composes user + memberships + active
# org into one envelope. CLI continues to use /me; do not remove it.

class SessionUser(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    email: str
    display_name: str | None = Field(default=None, alias="displayName")
    email_verified_at: str | None = Field(default=None, alias="emailVerifiedAt")


class SessionOrgMembership(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    organization_id: str = Field(alias="organizationId")
    organization_slug: str = Field(alias="organizationSlug")
    organization_name: str = Field(alias="organizationName")
    role: str
    plan: str
    region: str


class SessionResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    user: SessionUser
    organizations: list[SessionOrgMembership]
    active_org_id: str | None = Field(default=None, alias="activeOrgId")
    expires_at: str = Field(alias="expiresAt")


class ConsumeMagicLinkRequest(BaseModel):
    token: str = Field(min_length=8, max_length=200)


@dataclass(frozen=True, slots=True)
class MagicLinkLoginServices:
    magic_link: MagicLinkService
    sessions: SessionService
    memberships: MembershipRepository
    session: AsyncSession


@dataclass(frozen=True, slots=True)
class GoogleLoginServices:
    google: GoogleOAuthService
    sessions: SessionService


# ---------- Service dependencies ----------


def _magic_link_service_for_session(session: AsyncSession) -> MagicLinkService:
    config = get_config()
    verify_template = (
        f"{config.web_base_url}/auth/magic-link?token={{token}}"
    )
    return MagicLinkService(
        repo=MagicLinkTokenRepository(session),
        users=UserRepository(session),
        sender=default_email_sender(),
        verify_url_template=verify_template,
    )


def _session_service_for_session(session: AsyncSession) -> SessionService:
    config = get_config()
    return SessionService(
        repo=SessionRecordRepository(session),
        ttl=timedelta(days=config.session_ttl_days),
    )


def _google_oauth_service_for_session(session: AsyncSession) -> GoogleOAuthService:
    config = get_config()
    if config.google_client_id is None or config.google_client_secret is None:
        raise BasefloError(
            error_code="BF-AUTH-004",
            message="Google OAuth is not configured on this deployment.",
            status_code=503,
        )
    signer = URLSafeTimedSerializer(
        config.secret_key.get_secret_value(),
        salt="auth.oauth.google",
    )
    return GoogleOAuthService(
        client_id=config.google_client_id,
        client_secret=config.google_client_secret.get_secret_value(),
        redirect_uri=(
            f"{config.api_base_url}/api/v1/auth/oauth/google/callback"
        ),
        identities=OAuthIdentityRepository(session),
        signer=signer,
    )


async def get_magic_link_service() -> AsyncIterator[MagicLinkService]:
    async with open_session() as session:
        yield _magic_link_service_for_session(session)


async def get_session_service() -> AsyncIterator[SessionService]:
    async with open_session() as session:
        yield _session_service_for_session(session)


async def get_google_oauth_service() -> AsyncIterator[GoogleOAuthService]:
    async with open_session() as session:
        yield _google_oauth_service_for_session(session)


async def get_magic_link_login_services() -> AsyncIterator[MagicLinkLoginServices]:
    async with open_session() as session:
        yield MagicLinkLoginServices(
            magic_link=_magic_link_service_for_session(session),
            sessions=_session_service_for_session(session),
            memberships=MembershipRepository(session),
            session=session,
        )


async def get_google_login_services() -> AsyncIterator[GoogleLoginServices]:
    async with open_session() as session:
        yield GoogleLoginServices(
            google=_google_oauth_service_for_session(session),
            sessions=_session_service_for_session(session),
        )


# ---------- Magic link ----------


@router.post(
    "/magic-link/request",
    status_code=202,
    response_model=MagicLinkResponse,
    summary="Request a sign-in magic link",
    description=(
        "Always returns 202 even when the email is unknown, to prevent "
        "user-enumeration attacks. The link is delivered via email; in dev "
        "the configured `LogEmailSender` writes it to logs instead."
    ),
)
async def request_magic_link(
    request: Request,
    body: MagicLinkRequest,
    service: Annotated[MagicLinkService, Depends(get_magic_link_service)],
) -> MagicLinkResponse:
    ip = request.client.host if request.client is not None else None
    ua = request.headers.get("user-agent")
    try:
        issued = await service.request(
            email=body.email, ip_address=ip, user_agent=ua,
        )
    except BasefloError:
        # Pretend success to avoid leaking which emails are valid.
        return MagicLinkResponse(accepted=True)
    return MagicLinkResponse(
        accepted=True,
        expires_at=issued.expires_at.isoformat(),
    )


@router.get(
    "/magic-link/verify",
    summary="Consume a magic link and create a session",
    description=(
        "Verifies the token, finds-or-creates the user, mints a session, "
        "sets the session cookie, and 302s to the configured frontend URL."
    ),
)
async def verify_magic_link(
    request: Request,
    token: str,
    services: Annotated[
        MagicLinkLoginServices, Depends(get_magic_link_login_services),
    ],
) -> RedirectResponse:
    config = get_config()
    user = await services.magic_link.consume(token)
    ip = request.client.host if request.client is not None else None
    ua = request.headers.get("user-agent")
    issued = await services.sessions.create(
        user_id=user.id, ip_address=ip, user_agent=ua,
    )
    response = RedirectResponse(url=f"{config.web_base_url}/", status_code=302)
    set_session_cookie(response, raw_token=issued.raw_token)
    return response


# ---------- Google OAuth ----------


@router.get(
    "/oauth/google/start",
    summary="Begin Google OAuth user sign-in",
)
async def google_oauth_start(
    google: Annotated[GoogleOAuthService, Depends(get_google_oauth_service)],
    redirect_to: str | None = None,
) -> RedirectResponse:
    url = google.authorize_url(redirect_to=redirect_to)
    return RedirectResponse(url=url, status_code=302)


@router.get(
    "/oauth/google/callback",
    summary="Google OAuth callback",
)
async def google_oauth_callback(
    request: Request,
    code: str,
    state: str,
    services: Annotated[GoogleLoginServices, Depends(get_google_login_services)],
) -> RedirectResponse:
    config = get_config()
    result = await services.google.consume_callback(code=code, state=state)
    ip = request.client.host if request.client is not None else None
    ua = request.headers.get("user-agent")
    issued = await services.sessions.create(
        user_id=result.user.id, ip_address=ip, user_agent=ua,
    )
    target = result.redirect_to or f"{config.web_base_url}/"
    response = RedirectResponse(url=target, status_code=302)
    set_session_cookie(response, raw_token=issued.raw_token)
    return response


# ---------- Sign out ----------


@router.post(
    "/signout",
    status_code=204,
    summary="Revoke the current session and clear the cookie",
)
async def signout(
    tenant: Annotated[TenantCtx, Depends(require_tenant)],
    sessions: Annotated[SessionService, Depends(get_session_service)],
) -> Response:
    if tenant.session_id is not None:
        await sessions.revoke(tenant.session_id)
    response = Response(status_code=204)
    clear_session_cookie(response)
    return response


# ---------- /me ----------


@router.get(
    "/me",
    response_model=MeResponse,
    summary="Return the active TenantCtx as JSON",
)
async def me(
    tenant: Annotated[TenantCtx, Depends(require_tenant)],
) -> MeResponse:
    return MeResponse(
        user_id=str(tenant.user_id) if tenant.user_id is not None else "",
        organization_id=str(tenant.organization_id),
        role=tenant.role,
        session_id=str(tenant.session_id) if tenant.session_id is not None else None,
        is_api_key=tenant.is_api_key,
    )


# ---------- Web-app session endpoint ----------


async def _compose_session_response(
    *,
    user_id: UUID,
    active_org_id: UUID | None,
    expires_at_iso: str,
) -> SessionResponse:
    """Build the `SessionResponse` envelope from primitives.

    Reads the user + the user's accepted memberships + the joined organizations.
    Used by both `/session` (active tenant context) and `/magic-link/consume`
    (just-issued session, before any tenant context exists for the request).
    """
    async with open_session() as session:
        return await _compose_session_response_in_session(
            session=session,
            user_id=user_id,
            active_org_id=active_org_id,
            expires_at_iso=expires_at_iso,
        )


async def _compose_session_response_in_session(
    *,
    session: AsyncSession,
    user_id: UUID,
    active_org_id: UUID | None,
    expires_at_iso: str,
) -> SessionResponse:
    user = await session.get(User, user_id)
    if user is None or user.deleted_at is not None:
        raise BasefloError(
            error_code="BF-AUTH-001",
            message="User not found.",
            status_code=401,
    )

    memberships = await MembershipRepository(session).list_for_user(user_id)
    org_payload = [
        SessionOrgMembership(
            organization_id=str(m.organization_id),
            organization_slug=m.organization_slug,
            organization_name=m.organization_name,
            role=m.role,
            plan=m.plan,
            region=m.region,
        )
        for m in memberships
    ]

    return SessionResponse(
        user=SessionUser(
            id=str(user.id),
            email=user.email,
            display_name=user.display_name,
            email_verified_at=user.email_verified_at.isoformat()
            if user.email_verified_at is not None
            else None,
        ),
        organizations=org_payload,
        active_org_id=str(active_org_id) if active_org_id else None,
        expires_at=expires_at_iso,
    )


@router.get(
    "/session",
    response_model=SessionResponse,
    summary="Return the rich web-app session envelope (user + orgs)",
)
async def session_endpoint(
    auth: Annotated[AuthenticatedSession, Depends(require_authenticated_session)],
) -> SessionResponse:
    tenant = try_get_tenant_ctx()
    return await _compose_session_response(
        user_id=auth.user.id,
        active_org_id=tenant.organization_id if tenant is not None else None,
        expires_at_iso=auth.expires_at.isoformat(),
    )


# ---------- POST variant of magic-link consume (JSON, not redirect) ----------


@router.post(
    "/magic-link/consume",
    response_model=SessionResponse,
    summary="Consume a magic link via JSON, mint a session, return Session JSON",
    description=(
        "POST variant of /magic-link/verify for SPA / API clients. Sets the "
        "session cookie via Set-Cookie and returns the rich Session envelope. "
        "The GET /verify endpoint continues to exist for email-link flow."
    ),
)
async def consume_magic_link(
    request: Request,
    body: ConsumeMagicLinkRequest,
    response: Response,
    services: Annotated[
        MagicLinkLoginServices, Depends(get_magic_link_login_services),
    ],
) -> SessionResponse:
    user = await services.magic_link.consume(body.token)
    ip = request.client.host if request.client is not None else None
    ua = request.headers.get("user-agent")
    issued = await services.sessions.create(
        user_id=user.id, ip_address=ip, user_agent=ua,
    )
    set_session_cookie(response, raw_token=issued.raw_token)

    memberships = await services.memberships.list_for_user(user.id)
    active_org = memberships[0].organization_id if memberships else None

    return await _compose_session_response_in_session(
        session=services.session,
        user_id=user.id,
        active_org_id=active_org,
        expires_at_iso=issued.expires_at.isoformat(),
    )
