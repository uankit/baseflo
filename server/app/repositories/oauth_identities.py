"""OAuthIdentityRepository — concrete `IdentityDirectory` for user sign-in OAuth."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.magic_link import UserHandle
from app.db.models.oauth_identity import OAuthIdentity
from app.db.models.user import User

__all__ = ["OAuthIdentityRepository"]


class OAuthIdentityRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_user_by_provider_subject(
        self, *, provider: str, subject: str,
    ) -> UserHandle | None:
        stmt = (
            select(User)
            .join(OAuthIdentity, OAuthIdentity.user_id == User.id)
            .where(
                OAuthIdentity.provider == provider,
                OAuthIdentity.subject == subject,
            )
        )
        result = await self._session.execute(stmt)
        user = result.scalar_one_or_none()
        if user is None:
            return None
        return UserHandle(id=user.id, email=user.email)

    async def link_or_create(
        self,
        *,
        provider: str,
        subject: str,
        email: str,
        display_name: str | None = None,
    ) -> UserHandle:
        prior = await self.find_user_by_provider_subject(
            provider=provider, subject=subject,
        )
        if prior is not None:
            return prior

        # User by email: link or create.
        existing = await self._session.execute(select(User).where(User.email == email))
        user = existing.scalar_one_or_none()
        if user is None:
            user = User(email=email, display_name=display_name)
            self._session.add(user)
            try:
                await self._session.flush()
            except IntegrityError:
                await self._session.rollback()
                existing = await self._session.execute(
                    select(User).where(User.email == email)
                )
                user = existing.scalar_one()

        # Link.
        link = OAuthIdentity(
            user_id=user.id,
            provider=provider,
            subject=subject,
        )
        self._session.add(link)
        await self._session.flush()
        return UserHandle(id=user.id, email=user.email)
