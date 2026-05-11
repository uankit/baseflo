"""ConnectorTokenRepository — concrete `TokenVaultRepository`."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.connector import ConnectorToken

__all__ = ["ConnectorTokenRepository"]


class ConnectorTokenRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def put(
        self,
        *,
        connector_id: UUID,
        token_type: str,
        ciphertext: bytes,
        wrapped_dek: bytes,
        expires_at: datetime | None,
        scopes: list[str],
    ) -> UUID:
        row = ConnectorToken(
            connector_id=connector_id,
            token_type=token_type,
            ciphertext=ciphertext,
            wrapped_dek=wrapped_dek,
            expires_at=expires_at,
            scopes=scopes,
        )
        self._session.add(row)
        await self._session.flush()
        return row.id

    async def find_active(
        self, connector_id: UUID,
    ) -> tuple[UUID, bytes, bytes, datetime | None, list[str]] | None:
        stmt = (
            select(ConnectorToken)
            .where(
                ConnectorToken.connector_id == connector_id,
                ConnectorToken.revoked_at.is_(None),
            )
            .order_by(ConnectorToken.created_at.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return (
            row.id,
            row.ciphertext,
            row.wrapped_dek,
            row.expires_at,
            list(row.scopes),
        )

    async def revoke(self, token_id: UUID, revoked_at: datetime) -> None:
        await self._session.execute(
            update(ConnectorToken)
            .where(ConnectorToken.id == token_id)
            .values(revoked_at=revoked_at)
        )
