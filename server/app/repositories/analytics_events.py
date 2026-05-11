"""AnalyticsEvent repository.

Persists validated events. Bulk-insert is the hot path; the digest composer
queries `count_in_window` and `list_in_window` per project to assemble the
daily summary (M1.6).
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.analytics_event import AnalyticsEvent


class AnalyticsEventRepository:
    """Repository for the `analytics_events` table.

    Conventions:
      - All queries are tenant-scoped via the (organization_id, project_id) tuple
        the caller supplies. RLS enforces this at the DB level too.
      - Inserts go through `insert_batch` which uses ON CONFLICT (idempotency_key)
        to make SDK retries safe.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def insert_batch(
        self, events: Sequence[AnalyticsEvent]
    ) -> tuple[int, int]:
        """Insert events; returns (inserted_count, conflict_count).

        Conflicts on `(organization_id, project_id, idempotency_key)` are
        treated as already-present and counted but not raised — this is the
        contract the SDK relies on for safe retries.
        """
        if not events:
            return (0, 0)

        rows = [
            {
                "id": e.id,
                "organization_id": e.organization_id,
                "project_id": e.project_id,
                "project_version_id": e.project_version_id,
                "event_name": e.event_name,
                "distinct_id": e.distinct_id,
                "entity_id": e.entity_id,
                "properties": e.properties,
                "source": e.source,
                "idempotency_key": e.idempotency_key,
                "occurred_at": e.occurred_at,
            }
            for e in events
        ]
        # `pg_insert` is the Postgres-flavored INSERT with ON CONFLICT support;
        # SQLAlchemy types its first arg as the broader FromClause, so we name
        # the model directly to satisfy the strict overload.
        stmt = pg_insert(AnalyticsEvent).values(rows)
        # Conflict target is the unique partial index on idempotency_key.
        stmt = stmt.on_conflict_do_nothing(
            index_elements=["organization_id", "project_id", "idempotency_key"],
        )
        result = await self._session.execute(stmt)
        await self._session.flush()
        # `rowcount` lives on the underlying CursorResult; SQLAlchemy's stub
        # exposes it on Result via attr.
        inserted = int(getattr(result, "rowcount", 0) or 0)
        conflicts = len(rows) - inserted
        return (inserted, conflicts)

    async def count_in_window(
        self,
        *,
        organization_id: UUID,
        project_id: UUID,
        event_name: str | None,
        window_start: datetime,
        window_end: datetime,
    ) -> int:
        """Count events for one project in a time window, optionally filtered by name.

        Used by the digest composer (window_end - window_start = 24h).
        """
        stmt = (
            select(func.count())
            .select_from(AnalyticsEvent)
            .where(AnalyticsEvent.organization_id == organization_id)
            .where(AnalyticsEvent.project_id == project_id)
            .where(AnalyticsEvent.occurred_at >= window_start)
            .where(AnalyticsEvent.occurred_at < window_end)
        )
        if event_name is not None:
            stmt = stmt.where(AnalyticsEvent.event_name == event_name)
        return int((await self._session.execute(stmt)).scalar_one())

    async def counts_by_name_in_window(
        self,
        *,
        organization_id: UUID,
        project_id: UUID,
        window_start: datetime,
        window_end: datetime,
    ) -> dict[str, int]:
        """Group event counts by name. Returns `{event_name: count}`."""
        stmt = (
            select(AnalyticsEvent.event_name, func.count())
            .where(AnalyticsEvent.organization_id == organization_id)
            .where(AnalyticsEvent.project_id == project_id)
            .where(AnalyticsEvent.occurred_at >= window_start)
            .where(AnalyticsEvent.occurred_at < window_end)
            .group_by(AnalyticsEvent.event_name)
        )
        result = await self._session.execute(stmt)
        return {row[0]: int(row[1]) for row in result.all()}

    async def list_in_window(
        self,
        *,
        organization_id: UUID,
        project_id: UUID,
        window_start: datetime,
        window_end: datetime,
        limit: int = 1000,
    ) -> list[AnalyticsEvent]:
        stmt = (
            select(AnalyticsEvent)
            .where(AnalyticsEvent.organization_id == organization_id)
            .where(AnalyticsEvent.project_id == project_id)
            .where(AnalyticsEvent.occurred_at >= window_start)
            .where(AnalyticsEvent.occurred_at < window_end)
            .order_by(AnalyticsEvent.occurred_at)
            .limit(limit)
        )
        return list((await self._session.execute(stmt)).scalars().all())
