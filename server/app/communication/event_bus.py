"""Run event bus for Baseflo communication.

This is the standard interface used by routes and orchestration code. The
default store is Postgres-backed, while the live SSE wake-up conditions remain
process-local.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any
from uuid import UUID

from app.communication.contracts import RunEvent, RunKind, RunRecord, RunStatus
from app.communication.store import PostgresRunStore, RunStore


class RunEventBus:
    def __init__(self, *, store: RunStore | None = None) -> None:
        self.store = store or PostgresRunStore()
        self._conditions: dict[UUID, asyncio.Condition] = {}
        self._lock = asyncio.Lock()

    async def _condition_for(self, run_id: UUID) -> asyncio.Condition:
        async with self._lock:
            condition = self._conditions.get(run_id)
            if condition is None:
                condition = asyncio.Condition()
                self._conditions[run_id] = condition
            return condition

    async def create_run(
        self,
        *,
        organization_id: UUID,
        kind: RunKind,
        request: dict[str, Any],
    ) -> RunRecord:
        run = await self.store.create_run(
            organization_id=organization_id,
            kind=kind,
            request=request,
        )
        await self._condition_for(run.run_id)
        await self.publish(
            run.run_id,
            organization_id=organization_id,
            type="run.queued",
            stage="queued",
            message=f"{kind} run queued",
            progress=0,
        )
        return run

    async def get_run(self, run_id: UUID, *, organization_id: UUID | None = None) -> RunRecord:
        return await self.store.get_run(run_id, organization_id=organization_id)

    async def list_events(self, run_id: UUID, *, organization_id: UUID | None = None) -> list[RunEvent]:
        return await self.store.list_events(run_id, organization_id=organization_id)

    async def mark_running(self, run_id: UUID, *, organization_id: UUID) -> None:
        await self.store.mark_running(run_id, organization_id=organization_id)
        await self.publish(
            run_id,
            organization_id=organization_id,
            type="run.started",
            stage="run",
            message="Run started",
            progress=0.01,
        )

    async def complete_run(
        self,
        run_id: UUID,
        *,
        organization_id: UUID,
        status: RunStatus,
        result: dict[str, Any] | None = None,
        error: dict[str, Any] | None = None,
    ) -> None:
        await self.store.complete_run(
            run_id,
            organization_id=organization_id,
            status=status,
            result=result,
            error=error,
        )
        event_type = "run.completed" if status in {"completed", "partial"} else "run.failed"
        await self.publish(
            run_id,
            organization_id=organization_id,
            type=event_type,
            stage="run",
            message=f"Run {status}",
            progress=1,
            payload={"status": status, **({"error": error} if error else {})},
        )

    async def publish(
        self,
        run_id: UUID,
        *,
        organization_id: UUID,
        type: str,
        stage: str,
        message: str,
        progress: float | None = None,
        payload: dict[str, Any] | None = None,
    ) -> RunEvent:
        event = RunEvent(
            run_id=run_id,
            organization_id=organization_id,
            type=type,
            stage=stage,
            message=message,
            progress=progress,
            payload=payload or {},
        )
        stored = await self.store.append_event(event)
        condition = await self._condition_for(run_id)
        async with condition:
            condition.notify_all()
        return stored

    async def stream_events(
        self,
        run_id: UUID,
        *,
        organization_id: UUID,
        start_index: int = 0,
        heartbeat_seconds: float = 15.0,
    ) -> AsyncIterator[RunEvent]:
        await self.get_run(run_id, organization_id=organization_id)
        index = start_index
        while True:
            events = await self.list_events(run_id, organization_id=organization_id)
            run = await self.get_run(run_id, organization_id=organization_id)
            condition = await self._condition_for(run_id)
            while index < len(events):
                event = events[index]
                index += 1
                yield event
            if run.status in {"completed", "partial", "failed", "cancelled"}:
                break
            try:
                async with condition:
                    await asyncio.wait_for(condition.wait(), timeout=heartbeat_seconds)
            except TimeoutError:
                yield RunEvent(
                    run_id=run_id,
                    organization_id=organization_id,
                    type="run.heartbeat",
                    stage="run",
                    message="Run is still active",
                    payload={"status": run.status},
                )


run_event_bus = RunEventBus()
