"""MagicLinkTokenRepository — concrete persistence for sign-in tokens."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.magic_link import MagicLinkRecord
from app.db.models.magic_link_token import MagicLinkToken

__all__ = ["MagicLinkTokenRepository"]


class MagicLinkTokenRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_token(
        self,
        *,
        email: str,
        token_hash: bytes,
        expires_at: datetime,
        ip_address: str | None,
        user_agent: str | None,
    ) -> MagicLinkRecord:
        row = MagicLinkToken(
            email=email,
            token_hash=token_hash,
            expires_at=expires_at,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        self._session.add(row)
        await self._session.flush()
        return _to_record(row)

    async def find_by_token_hash(self, token_hash: bytes) -> MagicLinkRecord | None:
        stmt = select(MagicLinkToken).where(MagicLinkToken.token_hash == token_hash)
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return _to_record(row)

    async def mark_consumed(self, token_id: UUID, consumed_at: datetime) -> None:
        await self._session.execute(
            update(MagicLinkToken)
            .where(MagicLinkToken.id == token_id)
            .values(consumed_at=consumed_at)
        )


def _to_record(row: MagicLinkToken) -> MagicLinkRecord:
    return MagicLinkRecord(
        id=row.id,
        email=row.email,
        token_hash=row.token_hash,
        expires_at=row.expires_at,
        consumed_at=row.consumed_at,
    )
