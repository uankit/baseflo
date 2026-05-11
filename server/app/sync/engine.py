"""Sync engine — pulls source data into tenant Postgres."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.connect.base import Connector, SourceQuery
from app.connect.registry import get as get_connector
from app.core.errors import BasefloError
from app.db.models import DataSource, SyncRun


def _escape_ident(name: str) -> str:
    """Escape an identifier for safe use in raw SQL."""
    return '"' + name.replace('"', '""') + '"'


class SyncEngine:
    """Orchestrates one sync run: read from source → write to raw table."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def sync_source(self, source: DataSource) -> SyncRun:
        """Full sync of a single data source."""
        run = SyncRun(
            source_id=source.id,
            status="running",
            rows_synced=0,
            started_at=datetime.now(UTC),
        )
        self._session.add(run)
        await self._session.flush()

        try:
            connector = get_connector(source.kind)
            schema = await connector.introspect(source.config)

            total_rows = 0
            for table_schema in schema.tables:
                rows = await self._sync_table(
                    source=source,
                    connector=connector,
                    table_schema=table_schema,
                )
                total_rows += rows

            run.status = "success"
            run.rows_synced = total_rows
            source.status = "active"
            source.last_synced_at = datetime.now(UTC)

            # Trigger brain pipeline after successful sync
            # Brain failures should not mark sync as failed
            try:
                from app.brain.orchestrator import BrainOrchestrator
                brain = BrainOrchestrator()
                await brain.on_source_synced(str(source.id))
            except Exception:
                # TODO: log brain failure for observability
                pass

        except Exception as exc:
            run.status = "failed"
            run.error_message = str(exc)
            source.status = "error"

        run.finished_at = datetime.now(UTC)
        return run

    async def _sync_table(
        self,
        source: DataSource,
        connector: Connector,
        table_schema: Any,
    ) -> int:
        """Sync one table. Creates raw table if not exists, inserts rows."""
        raw_table_name = f"raw__{source.project_id.hex}__{table_schema.name}"
        raw_table_quoted = _escape_ident(raw_table_name)

        # Ensure raw table exists (simple TEXT columns for MVP)
        col_defs = ", ".join(
            f"{_escape_ident(c.name)} TEXT" for c in table_schema.columns
        )
        ddl = f"""
        CREATE TABLE IF NOT EXISTS {raw_table_quoted} (
            _baseflo_id SERIAL PRIMARY KEY,
            _baseflo_source_id TEXT,
            _baseflo_synced_at TIMESTAMPTZ DEFAULT NOW(),
            {col_defs}
        )
        """
        await self._session.execute(text(ddl))

        # Stream rows and insert
        query = SourceQuery(table=table_schema.name)
        count = 0
        batch: list[dict[str, Any]] = []
        BATCH_SIZE = 500

        async for row in connector.read(source.config, query):
            record: dict[str, Any] = {
                "_baseflo_source_id": row.source_id,
            }
            for k, v in row.values.items():
                record[k] = str(v) if v is not None else None
            batch.append(record)
            if len(batch) >= BATCH_SIZE:
                count += await self._insert_batch(raw_table_quoted, batch)
                batch.clear()

        if batch:
            count += await self._insert_batch(raw_table_quoted, batch)

        return count

    async def _insert_batch(
        self, table_name_quoted: str, rows: list[dict[str, Any]],
    ) -> int:
        if not rows:
            return 0
        keys = list(rows[0].keys())
        cols = ", ".join(_escape_ident(k) for k in keys)
        placeholders = ", ".join(f":{k}" for k in keys)
        stmt = text(f"INSERT INTO {table_name_quoted} ({cols}) VALUES ({placeholders})")
        for row in rows:
            await self._session.execute(stmt, row)
        return len(rows)
