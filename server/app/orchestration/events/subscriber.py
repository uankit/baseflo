"""SSE subscriber.

Subscribes to a conversation's event stream with replay support. The flow:

1. Open a dedicated asyncpg connection (NOT from the pool — LISTEN holds the
   connection for the lifetime of the subscription).
2. Issue `LISTEN conversation_<id>` first, so any NOTIFY arriving during the
   subsequent backlog read is buffered on the connection rather than missed.
3. Replay all rows with `sequence > last_seen` from the DB.
4. Yield those.
5. After replay, drain pg_notify backlog from step 2.
6. Stream live notifications as they arrive, fetching each row by sequence.

The dedicated connection is critical: SQLAlchemy's pooled connections cycle
through clients and would silently drop the LISTEN.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import UUID

import asyncpg
from pydantic import TypeAdapter
from sqlalchemy import text

from app.core.config import get_config
from app.observability.logging import get_logger
from app.orchestration.events.types import (
    ConversationEventEnvelope,
    EventPayload,
    EventType,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.db.models.conversation import ConversationEvent

logger = get_logger("orchestration.events.subscriber")


# Validates a JSONB row payload into the discriminated EventPayload union by
# inspecting the `type` field. Built once and reused on every event.
_PAYLOAD_ADAPTER: TypeAdapter[EventPayload] = TypeAdapter(EventPayload)


@dataclass(frozen=True, slots=True)
class ListenConnection:
    connection: asyncpg.Connection
    queue: asyncio.Queue[str]


def _row_to_envelope(row: asyncpg.Record) -> ConversationEventEnvelope:
    return ConversationEventEnvelope(
        id=row["id"],
        conversation_id=row["conversation_id"],
        sequence=int(row["sequence"]),
        event_type=EventType(row["event_type"]),
        payload=_PAYLOAD_ADAPTER.validate_python(row["payload"]),
        created_at=row["created_at"],
    )


def _orm_to_envelope(event: ConversationEvent) -> ConversationEventEnvelope:
    return ConversationEventEnvelope(
        id=event.id,
        conversation_id=event.conversation_id,
        sequence=event.sequence,
        event_type=EventType(event.event_type),
        payload=_PAYLOAD_ADAPTER.validate_python(event.payload),
        created_at=event.created_at,
    )


def _asyncpg_dsn() -> str:
    """Convert the SQLAlchemy URL to a plain Postgres DSN for asyncpg."""
    url = get_config().database_url
    return url.replace("postgresql+asyncpg://", "postgresql://")


@asynccontextmanager
async def listen_connection(conversation_id: UUID) -> AsyncIterator[ListenConnection]:
    """Open a dedicated asyncpg connection bound to the conversation channel."""
    conn = await asyncpg.connect(dsn=_asyncpg_dsn())
    channel = f"conversation_{conversation_id}"
    try:
        # Notification queue stays alongside the slotted asyncpg connection;
        # asyncpg Connection objects cannot be assigned ad-hoc attributes.
        queue: asyncio.Queue[str] = asyncio.Queue()

        def _push(_conn: asyncpg.Connection, _pid: int, _channel: str, payload: str) -> None:
            queue.put_nowait(payload)

        await conn.add_listener(channel, _push)
        try:
            yield ListenConnection(connection=conn, queue=queue)
        finally:
            await conn.remove_listener(channel, _push)
    finally:
        await conn.close()


async def subscribe(
    conversation_id: UUID,
    *,
    organization_id: UUID | None = None,
    last_sequence: int = 0,
    heartbeat_interval_s: float = 25.0,
) -> AsyncIterator[ConversationEventEnvelope | None]:
    """Yield event envelopes ordered by sequence; `None` is a heartbeat tick.

    The caller is responsible for converting envelopes (or heartbeats) into
    SSE wire format. Yielding `None` periodically lets the SSE handler emit
    a comment line so intermediate proxies don't time out.

    This is an async generator. To stop streaming, the consumer breaks; the
    `listen_connection` context manager cleans up on exit.
    """
    from app.db.session import open_session  # noqa: PLC0415 — avoid import cycle
    from app.repositories.conversations import ConversationEventRepository  # noqa: PLC0415

    async def _apply_explicit_scope(session: AsyncSession) -> None:
        if organization_id is None:
            return
        await session.execute(
            text("SELECT set_config('app.organization_id', :org, true)"),
            {"org": str(organization_id)},
        )

    async with listen_connection(conversation_id) as listener:
        queue = listener.queue

        # Phase 1: replay rows with sequence > last_sequence.
        async with open_session() as session:
            await _apply_explicit_scope(session)
            repo = ConversationEventRepository(session)
            backlog = await repo.list_since(conversation_id, after_sequence=last_sequence)
        for replay_event in backlog:
            yield _orm_to_envelope(replay_event)
            last_sequence = max(last_sequence, replay_event.sequence)

        # Phase 2: drain any NOTIFY arrivals that came in *during* phase 1
        # but pointed at sequences we've already replayed.
        while not queue.empty():
            try:
                queue.get_nowait()
            except asyncio.QueueEmpty:
                break

        # Phase 3: live stream. Each NOTIFY's payload is the new sequence;
        # we fetch the corresponding row from the DB to keep payloads consistent
        # (NOTIFY in Postgres is bounded to ~8KB; we never put data into it).
        while True:
            try:
                payload = await asyncio.wait_for(queue.get(), timeout=heartbeat_interval_s)
            except asyncio.TimeoutError:
                yield None  # heartbeat
                continue

            try:
                seq = int(payload)
            except ValueError:
                logger.warning("sse_unparseable_notify_payload", payload=payload)
                continue

            if seq <= last_sequence:
                continue

            async with open_session() as session:
                await _apply_explicit_scope(session)
                repo = ConversationEventRepository(session)
                event = await repo.get_by_sequence(conversation_id, seq)
            if event is None:
                logger.warning(
                    "sse_notify_for_missing_row",
                    conversation_id=str(conversation_id),
                    sequence=seq,
                )
                continue

            yield _orm_to_envelope(event)
            last_sequence = seq
