"""Server-Sent Events helpers for Baseflo live run streams."""

from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi.responses import StreamingResponse

from app.communication.contracts import RunEvent


def sse_response(events: AsyncIterator[RunEvent]) -> StreamingResponse:
    async def _stream() -> AsyncIterator[str]:
        async for event in events:
            yield _encode_event(event)

    return StreamingResponse(
        _stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


def _encode_event(event: RunEvent) -> str:
    return (
        f"id: {event.event_id}\n"
        f"event: {event.type}\n"
        f"data: {event.model_dump_json()}\n\n"
    )
