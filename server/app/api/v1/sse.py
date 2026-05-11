"""Shared SSE helpers for conversation event streams."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any
from uuid import UUID

from fastapi.responses import StreamingResponse

from app.orchestration.events.subscriber import subscribe
from app.orchestration.events.types import ConversationEventEnvelope


def resolve_last_sequence(
    *, last_event_id: int | None, seq: int | None,
) -> int:
    """Resolve browser reconnect state from standard SSE or query fallback.

    EventSource does not let clients set custom headers on a manually recreated
    connection, so the web client also passes `?seq=N` after an error-triggered
    reconnect. The standard `Last-Event-ID` header wins when present.
    """
    if last_event_id is not None:
        return last_event_id
    return seq if seq is not None else 0


def conversation_event_to_saga_event(
    envelope: ConversationEventEnvelope,
) -> dict[str, Any]:
    """Map the internal DB envelope to the public web SSE contract."""
    return {
        "conversationId": str(envelope.conversation_id),
        "sequence": envelope.sequence,
        "kind": envelope.event_type.value,
        "createdAt": envelope.created_at.isoformat(),
        "payload": _camelize_keys(envelope.payload.model_dump(mode="json")),
    }


def _camelize_keys(value: Any) -> Any:
    if isinstance(value, list):
        return [_camelize_keys(item) for item in value]
    if isinstance(value, dict):
        return {
            _to_camel(str(key)): _camelize_keys(item)
            for key, item in value.items()
        }
    return value


def _to_camel(key: str) -> str:
    if "_" not in key or key.startswith("_"):
        return key
    first, *rest = key.split("_")
    return first + "".join(part[:1].upper() + part[1:] for part in rest)


def conversation_event_stream_response(
    *, conversation_id: UUID, organization_id: UUID, last_sequence: int,
) -> StreamingResponse:
    async def _stream() -> AsyncIterator[bytes]:
        async for envelope in subscribe(
            conversation_id,
            organization_id=organization_id,
            last_sequence=last_sequence,
        ):
            if envelope is None:
                yield b": ping\n\n"
                continue

            event = conversation_event_to_saga_event(envelope)
            data = json.dumps(event, default=str)
            chunk = (
                f"id: {envelope.sequence}\n"
                f"event: {envelope.event_type.value}\n"
                f"data: {data}\n\n"
            )
            yield chunk.encode("utf-8")

    return StreamingResponse(
        _stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
