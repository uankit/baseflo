"""Persistence boundary and transactional workflows for auth.

Routes and token helpers should not know SQLAlchemy models. This module is the
single database-facing boundary for email magic links, refresh tokens,
memberships, and invitations. Future identity types (Google, phone OTP, etc.)
should add auth-domain workflows here instead of leaking persistence into API
routes.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import select

from app.core.enums import (
    AuthEventKind,
    MagicLinkPurpose,
    MembershipStatus,
    OrgPlan,
    Role,
    UserStatus,
)
from app.core.errors import AuthError, ConflictError, NotFoundError
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


@dataclass(frozen=True)
class AuthRequestContext:
    ip_address: str | None
    user_agent: str | None


@dataclass(frozen=True)
class UserRecord:
    id: UUID
    email: str
    status: UserStatus


@dataclass(frozen=True)
class OrganizationRecord:
    id: UUID
    name: str
    slug: str
    plan: OrgPlan


@dataclass(frozen=True)
class MembershipRecord:
    role: Role
    status: MembershipStatus
    organization: OrganizationRecord


@dataclass(frozen=True)
class AuthSessionRecord:
    user: UserRecord
    current_organization: OrganizationRecord
    memberships: list[MembershipRecord]


@dataclass(frozen=True)
class InvitationRecord:
    id: UUID
    email: str
    role: Role
    organization_id: UUID
    expires_at: datetime


def _user_record(user: User) -> UserRecord:
    return UserRecord(id=user.id, email=user.email, status=user.status)


def _organization_record(organization: Organization) -> OrganizationRecord:
    return OrganizationRecord(
        id=organization.id,
        name=organization.name,
        slug=organization.slug,
        plan=organization.plan,
    )


def _membership_record(membership: Membership, organization: Organization) -> MembershipRecord:
    return MembershipRecord(
        role=membership.role,
        status=membership.status,
        organization=_organization_record(organization),
    )


def _session_record(
    *,
    user: User,
    current_organization: Organization,
    memberships_with_orgs: list[tuple[Membership, Organization]],
) -> AuthSessionRecord:
    return AuthSessionRecord(
        user=_user_record(user),
        current_organization=_organization_record(current_organization),
        memberships=[
            _membership_record(membership, organization)
            for membership, organization in memberships_with_orgs
        ],
    )


async def has_active_membership(*, user_id: UUID, organization_id: UUID) -> bool:
    async with open_session() as session:
        result = await session.execute(
            select(Membership.id).where(
                Membership.user_id == user_id,
                Membership.organization_id == organization_id,
                Membership.status == MembershipStatus.ACTIVE,
            )
        )
        return result.scalar_one_or_none() is not None


async def active_membership_role(*, user_id: UUID, organization_id: UUID) -> Role | None:
    async with open_session() as session:
        result = await session.execute(
            select(Membership.role).where(
                Membership.user_id == user_id,
                Membership.organization_id == organization_id,
                Membership.status == MembershipStatus.ACTIVE,
            )
        )
        return result.scalar_one_or_none()


async def create_magic_link_challenge(
    *,
    email: str,
    token_hash: str,
    expires_at: datetime,
    now: datetime,
    context: AuthRequestContext,
) -> None:
    async with open_session() as session:
        session.add(
            MagicLinkToken(
                email=email,
                token_hash=token_hash,
                purpose=MagicLinkPurpose.SIGN_IN,
                expires_at=expires_at,
                ip_address=context.ip_address,
                user_agent=context.user_agent,
            )
        )
        session.add(
            AuthEvent(
                kind=AuthEventKind.MAGIC_LINK_REQUESTED,
                ip_address=context.ip_address,
                user_agent=context.user_agent,
                details={"email": email},
                occurred_at=now,
            )
        )


async def consume_magic_link_sign_in(
    *,
    email: str,
    token_hash: str,
    now: datetime,
    context: AuthRequestContext,
    refresh_token_hash: str,
    refresh_expires_at: datetime,
    new_workspace_name: str,
    new_workspace_slug: str,
) -> AuthSessionRecord:
    async with open_session() as session:
        result = await session.execute(
            select(MagicLinkToken)
            .where(
                MagicLinkToken.email == email,
                MagicLinkToken.token_hash == token_hash,
                MagicLinkToken.consumed_at.is_(None),
                MagicLinkToken.expires_at > now,
                MagicLinkToken.purpose == MagicLinkPurpose.SIGN_IN,
            )
            .order_by(MagicLinkToken.created_at.desc())
            .limit(1)
        )
        magic_link = result.scalar_one_or_none()

        if magic_link is None:
            session.add(
                AuthEvent(
                    kind=AuthEventKind.LOGIN_FAILED,
                    ip_address=context.ip_address,
                    user_agent=context.user_agent,
                    details={"reason": "invalid_magic_link", "email": email},
                    occurred_at=now,
                )
            )
            raise AuthError(
                message="Invalid or expired magic link",
                code="AUTH_MAGIC_LINK_INVALID",
                status_hint=400,
            )

        magic_link.consumed_at = now

        user = (
            await session.execute(select(User).where(User.email == email))
        ).scalar_one_or_none()
        if user is None:
            user = User(email=email, status=UserStatus.ACTIVE)
            session.add(user)
            await session.flush()
            session.add(
                AuthEvent(
                    kind=AuthEventKind.SIGNUP,
                    user_id=user.id,
                    ip_address=context.ip_address,
                    user_agent=context.user_agent,
                    occurred_at=now,
                )
            )

        memberships_with_orgs = await _active_memberships(session, user.id)

        if not memberships_with_orgs:
            organization = Organization(
                name=new_workspace_name,
                slug=new_workspace_slug,
                plan=OrgPlan.FREE,
            )
            session.add(organization)
            await session.flush()
            membership = Membership(
                user_id=user.id,
                organization_id=organization.id,
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
                    organization_id=organization.id,
                    ip_address=context.ip_address,
                    user_agent=context.user_agent,
                    details={"reason": "auto_on_first_signin"},
                    occurred_at=now,
                )
            )
            session.add(
                AuthEvent(
                    kind=AuthEventKind.MEMBERSHIP_CREATED,
                    user_id=user.id,
                    organization_id=organization.id,
                    ip_address=context.ip_address,
                    user_agent=context.user_agent,
                    details={"role": Role.OWNER.value},
                    occurred_at=now,
                )
            )
            memberships_with_orgs = [(membership, organization)]

        _current_membership, current_organization = memberships_with_orgs[0]

        session.add(
            RefreshToken(
                user_id=user.id,
                organization_id=current_organization.id,
                token_hash=refresh_token_hash,
                expires_at=refresh_expires_at,
                created_at=now,
            )
        )
        session.add(
            AuthEvent(
                kind=AuthEventKind.MAGIC_LINK_CONSUMED,
                user_id=user.id,
                organization_id=current_organization.id,
                ip_address=context.ip_address,
                user_agent=context.user_agent,
                occurred_at=now,
            )
        )
        session.add(
            AuthEvent(
                kind=AuthEventKind.LOGIN,
                user_id=user.id,
                organization_id=current_organization.id,
                ip_address=context.ip_address,
                user_agent=context.user_agent,
                occurred_at=now,
            )
        )
        session.add(
            AuthEvent(
                kind=AuthEventKind.REFRESH_TOKEN_ISSUED,
                user_id=user.id,
                organization_id=current_organization.id,
                ip_address=context.ip_address,
                user_agent=context.user_agent,
                occurred_at=now,
            )
        )

        return _session_record(
            user=user,
            current_organization=current_organization,
            memberships_with_orgs=memberships_with_orgs,
        )


async def rotate_refresh_session(
    *,
    refresh_token_hash: str,
    new_refresh_token_hash: str,
    new_refresh_expires_at: datetime,
    now: datetime,
    context: AuthRequestContext,
) -> AuthSessionRecord:
    async with open_session() as session:
        result = await session.execute(
            select(RefreshToken, User, Organization)
            .join(User, RefreshToken.user_id == User.id)
            .join(Organization, RefreshToken.organization_id == Organization.id)
            .where(RefreshToken.token_hash == refresh_token_hash)
        )
        row = result.one_or_none()
        if row is None:
            raise AuthError(
                message="Invalid refresh token",
                code="AUTH_REFRESH_INVALID",
                status_hint=401,
            )
        refresh_token, user, organization = row

        if refresh_token.revoked_at is not None or refresh_token.expires_at <= now:
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

        if not await _has_active_membership_in_session(session, user.id, organization.id):
            raise AuthError(
                message="Membership no longer active",
                code="AUTH_MEMBERSHIP_INACTIVE",
                status_hint=403,
            )

        new_refresh = RefreshToken(
            user_id=user.id,
            organization_id=organization.id,
            token_hash=new_refresh_token_hash,
            expires_at=new_refresh_expires_at,
            created_at=now,
        )
        session.add(new_refresh)
        await session.flush()

        refresh_token.revoked_at = now
        refresh_token.replaced_by_id = new_refresh.id

        memberships_with_orgs = await _active_memberships(session, user.id)

        session.add(
            AuthEvent(
                kind=AuthEventKind.REFRESH_TOKEN_ROTATED,
                user_id=user.id,
                organization_id=organization.id,
                ip_address=context.ip_address,
                user_agent=context.user_agent,
                occurred_at=now,
            )
        )

        return _session_record(
            user=user,
            current_organization=organization,
            memberships_with_orgs=memberships_with_orgs,
        )


async def revoke_refresh_session(
    *,
    refresh_token_hash: str,
    now: datetime,
    context: AuthRequestContext,
) -> None:
    async with open_session() as session:
        refresh_token = (
            await session.execute(
                select(RefreshToken).where(
                    RefreshToken.token_hash == refresh_token_hash,
                    RefreshToken.revoked_at.is_(None),
                )
            )
        ).scalar_one_or_none()
        if refresh_token is None:
            return
        refresh_token.revoked_at = now
        session.add(
            AuthEvent(
                kind=AuthEventKind.REFRESH_TOKEN_REVOKED,
                user_id=refresh_token.user_id,
                organization_id=refresh_token.organization_id,
                ip_address=context.ip_address,
                user_agent=context.user_agent,
                details={"reason": "logout"},
                occurred_at=now,
            )
        )
        session.add(
            AuthEvent(
                kind=AuthEventKind.LOGOUT,
                user_id=refresh_token.user_id,
                organization_id=refresh_token.organization_id,
                ip_address=context.ip_address,
                user_agent=context.user_agent,
                occurred_at=now,
            )
        )


async def load_user_session(*, user_id: UUID, organization_id: UUID) -> AuthSessionRecord:
    async with open_session() as session:
        user = await session.get(User, user_id)
        if user is None:
            raise NotFoundError(
                message="User not found",
                code="USER_NOT_FOUND",
                status_hint=404,
            )

        memberships_with_orgs = await _active_memberships(session, user.id)
        current_organization = next(
            (organization for _membership, organization in memberships_with_orgs if organization.id == organization_id),
            None,
        )
        if current_organization is None:
            raise AuthError(
                message="Active organization not found",
                code="AUTH_ORG_NOT_FOUND",
                status_hint=403,
            )
        return _session_record(
            user=user,
            current_organization=current_organization,
            memberships_with_orgs=memberships_with_orgs,
        )


async def create_invitation_record(
    *,
    organization_id: UUID,
    invited_by_user_id: UUID,
    email: str,
    role: Role,
    token_hash: str,
    expires_at: datetime,
    now: datetime,
    context: AuthRequestContext,
) -> InvitationRecord:
    async with open_session() as session:
        existing = (
            await session.execute(
                select(Membership)
                .join(User, Membership.user_id == User.id)
                .where(
                    User.email == email,
                    Membership.organization_id == organization_id,
                    Membership.status == MembershipStatus.ACTIVE,
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            raise ConflictError(
                message="User is already a member of this organization",
                code="MEMBERSHIP_EXISTS",
                status_hint=409,
            )

        invitation = Invitation(
            organization_id=organization_id,
            email=email,
            role=role,
            invited_by_user_id=invited_by_user_id,
            token_hash=token_hash,
            expires_at=expires_at,
        )
        session.add(invitation)
        await session.flush()

        session.add(
            AuthEvent(
                kind=AuthEventKind.INVITATION_SENT,
                user_id=invited_by_user_id,
                organization_id=organization_id,
                ip_address=context.ip_address,
                user_agent=context.user_agent,
                details={"invited_email": email, "role": role.value},
                occurred_at=now,
            )
        )

        return InvitationRecord(
            id=invitation.id,
            email=invitation.email,
            role=invitation.role,
            organization_id=invitation.organization_id,
            expires_at=invitation.expires_at,
        )


async def accept_invitation_record(
    *,
    invitation_token_hash: str,
    now: datetime,
    context: AuthRequestContext,
    refresh_token_hash: str,
    refresh_expires_at: datetime,
) -> AuthSessionRecord:
    async with open_session() as session:
        row = (
            await session.execute(
                select(Invitation, Organization)
                .join(Organization, Invitation.organization_id == Organization.id)
                .where(Invitation.token_hash == invitation_token_hash)
            )
        ).one_or_none()
        if row is None:
            raise AuthError(
                message="Invalid invitation",
                code="INVITATION_INVALID",
                status_hint=400,
            )
        invitation, organization = row

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

        user = (
            await session.execute(select(User).where(User.email == invitation.email))
        ).scalar_one_or_none()
        if user is None:
            user = User(email=invitation.email, status=UserStatus.ACTIVE)
            session.add(user)
            await session.flush()
            session.add(
                AuthEvent(
                    kind=AuthEventKind.SIGNUP,
                    user_id=user.id,
                    ip_address=context.ip_address,
                    user_agent=context.user_agent,
                    details={"via": "invitation"},
                    occurred_at=now,
                )
            )

        existing_membership = (
            await session.execute(
                select(Membership).where(
                    Membership.user_id == user.id,
                    Membership.organization_id == organization.id,
                )
            )
        ).scalar_one_or_none()
        if existing_membership is not None:
            if existing_membership.status == MembershipStatus.ACTIVE:
                raise ConflictError(
                    message="Already a member of this organization",
                    code="MEMBERSHIP_EXISTS",
                    status_hint=409,
                )
            existing_membership.status = MembershipStatus.ACTIVE
            existing_membership.role = invitation.role
            existing_membership.joined_at = now
            existing_membership.revoked_at = None
        else:
            session.add(
                Membership(
                    user_id=user.id,
                    organization_id=organization.id,
                    role=invitation.role,
                    status=MembershipStatus.ACTIVE,
                    joined_at=now,
                )
            )

        invitation.accepted_at = now

        session.add(
            AuthEvent(
                kind=AuthEventKind.INVITATION_ACCEPTED,
                user_id=user.id,
                organization_id=organization.id,
                ip_address=context.ip_address,
                user_agent=context.user_agent,
                occurred_at=now,
            )
        )
        session.add(
            AuthEvent(
                kind=AuthEventKind.MEMBERSHIP_CREATED,
                user_id=user.id,
                organization_id=organization.id,
                ip_address=context.ip_address,
                user_agent=context.user_agent,
                details={"role": invitation.role.value, "via": "invitation"},
                occurred_at=now,
            )
        )

        session.add(
            RefreshToken(
                user_id=user.id,
                organization_id=organization.id,
                token_hash=refresh_token_hash,
                expires_at=refresh_expires_at,
                created_at=now,
            )
        )
        session.add(
            AuthEvent(
                kind=AuthEventKind.LOGIN,
                user_id=user.id,
                organization_id=organization.id,
                ip_address=context.ip_address,
                user_agent=context.user_agent,
                occurred_at=now,
            )
        )

        await session.flush()
        memberships_with_orgs = await _active_memberships(session, user.id)

        return _session_record(
            user=user,
            current_organization=organization,
            memberships_with_orgs=memberships_with_orgs,
        )


async def _active_memberships(session, user_id: UUID) -> list[tuple[Membership, Organization]]:
    result = await session.execute(
        select(Membership, Organization)
        .join(Organization, Membership.organization_id == Organization.id)
        .where(
            Membership.user_id == user_id,
            Membership.status == MembershipStatus.ACTIVE,
        )
        .order_by(Membership.joined_at.asc())
    )
    return list(result.all())


async def _has_active_membership_in_session(
    session,
    user_id: UUID,
    organization_id: UUID,
) -> bool:
    result = await session.execute(
        select(Membership.id).where(
            Membership.user_id == user_id,
            Membership.organization_id == organization_id,
            Membership.status == MembershipStatus.ACTIVE,
        )
    )
    return result.scalar_one_or_none() is not None
