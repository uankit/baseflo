"""AgentFeedEntry repository — CRUD + feed queries."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.db.models.agent_feed import AgentFeedEntry


class AgentFeedRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, entry_id: UUID) -> AgentFeedEntry:
        result = await self._session.get(AgentFeedEntry, entry_id)
        if result is None:
            raise NotFoundError(
                message=f"Feed entry {entry_id} not found.",
                error_code="BF-API-001",
                details={"entry_id": str(entry_id)},
            )
        return result

    async def create(self, entry: AgentFeedEntry) -> AgentFeedEntry:
        self._session.add(entry)
        await self._session.flush()
        return entry

    async def list_for_project(
        self,
        project_id: UUID,
        *,
        agent_id: str | None = None,
        entry_type: str | None = None,
        limit: int = 50,
    ) -> list[AgentFeedEntry]:
        stmt = (
            select(AgentFeedEntry)
            .where(AgentFeedEntry.project_id == project_id)
            .order_by(AgentFeedEntry.created_at.desc())
            .limit(limit)
        )
        if agent_id is not None:
            stmt = stmt.where(AgentFeedEntry.agent_id == agent_id)
        if entry_type is not None:
            stmt = stmt.where(AgentFeedEntry.entry_type == entry_type)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def acknowledge(self, entry_id: UUID) -> AgentFeedEntry:
        from datetime import UTC, datetime

        entry = await self.get(entry_id)
        entry.acknowledged_at = datetime.now(UTC)
        await self._session.flush()
        return entry
