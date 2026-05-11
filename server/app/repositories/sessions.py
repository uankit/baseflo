"""SessionRecordRepository — concrete persistence for `sessions`."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.sessions import StoredSession
from app.db.models.session_record import SessionRecord

__all__ = ["SessionRecordRepository"]


class SessionRecordRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        user_id: UUID,
        token_hash: bytes,
        expires_at: datetime,
        user_agent: str | None,
        ip_address: str | None,
    ) -> StoredSession:
        row = SessionRecord(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
            user_agent=user_agent,
            ip_address=ip_address,
        )
        self._session.add(row)
        await self._session.flush()
        return _to_stored(row)

    async def find_by_token_hash(self, token_hash: bytes) -> StoredSession | None:
        stmt = select(SessionRecord).where(SessionRecord.token_hash == token_hash)
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return _to_stored(row)

    async def revoke(self, session_id: UUID, revoked_at: datetime) -> None:
        await self._session.execute(
            update(SessionRecord)
            .where(SessionRecord.id == session_id)
            .values(revoked_at=revoked_at)
        )

    async def extend(self, session_id: UUID, new_expires_at: datetime) -> None:
        await self._session.execute(
            update(SessionRecord)
            .where(SessionRecord.id == session_id)
            .values(expires_at=new_expires_at)
        )


def _to_stored(row: SessionRecord) -> StoredSession:
    return StoredSession(
        session_id=row.id,
        user_id=row.user_id,
        expires_at=row.expires_at,
        revoked_at=row.revoked_at,
    )
