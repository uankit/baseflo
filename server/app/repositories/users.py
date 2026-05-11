"""User repository — auth-flow access to the `users` table."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.magic_link import UserHandle
from app.db.models.user import User

__all__ = ["UserRepository"]


class UserRepository:
    """Tenant-agnostic CRUD for `users`. RLS does not gate this table — it
    holds the human identities that span tenants.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_or_create_by_email(self, email: str) -> UserHandle:
        """Return existing user with that email or create a new one.

        Race-safe: if a parallel writer creates the row between the SELECT and
        our INSERT, the unique constraint fires and we re-fetch.
        """
        existing = await self._session.execute(select(User).where(User.email == email))
        user = existing.scalar_one_or_none()
        if user is None:
            user = User(email=email)
            self._session.add(user)
            try:
                await self._session.flush()
            except IntegrityError:
                await self._session.rollback()
                existing = await self._session.execute(
                    select(User).where(User.email == email)
                )
                user = existing.scalar_one()
        return UserHandle(id=user.id, email=user.email)
