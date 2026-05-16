"""Persistence boundary for async run records and events."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Protocol, cast
from uuid import UUID, uuid4

from fastapi.encoders import jsonable_encoder
from sqlalchemy import select

from app.communication.contracts import RunEvent, RunKind, RunRecord, RunStatus
from app.core.errors import NotFoundError
from app.db.models import Run
from app.db.models import RunEvent as RunEventRow
from app.db.session import open_session


class RunStore(Protocol):
    async def create_run(
        self,
        *,
        organization_id: UUID,
        kind: RunKind,
        request: dict[str, Any],
    ) -> RunRecord: ...

    async def get_run(
        self,
        run_id: UUID,
        *,
        organization_id: UUID | None = None,
    ) -> RunRecord: ...

    async def list_events(
        self,
        run_id: UUID,
        *,
        organization_id: UUID | None = None,
    ) -> list[RunEvent]: ...

    async def mark_running(self, run_id: UUID, *, organization_id: UUID) -> RunRecord: ...

    async def complete_run(
        self,
        run_id: UUID,
        *,
        organization_id: UUID,
        status: RunStatus,
        result: dict[str, Any] | None = None,
        error: dict[str, Any] | None = None,
    ) -> RunRecord: ...

    async def append_event(self, event: RunEvent) -> RunEvent: ...


class PostgresRunStore:
    async def create_run(
        self,
        *,
        organization_id: UUID,
        kind: RunKind,
        request: dict[str, Any],
    ) -> RunRecord:
        now = datetime.now(UTC)
        async with open_session() as session:
            row = Run(
                organization_id=organization_id,
                kind=kind,
                status="queued",
                request=_json(request),
                created_at=now,
                updated_at=now,
            )
            session.add(row)
            await session.flush()
            return _run_record(row)

    async def get_run(
        self,
        run_id: UUID,
        *,
        organization_id: UUID | None = None,
    ) -> RunRecord:
        async with open_session() as session:
            row = await session.get(Run, run_id)
            if row is None or (organization_id is not None and row.organization_id != organization_id):
                raise NotFoundError(message="Run not found", code="RUN_NOT_FOUND", status_hint=404)
            return _run_record(row)

    async def list_events(
        self,
        run_id: UUID,
        *,
        organization_id: UUID | None = None,
    ) -> list[RunEvent]:
        await self.get_run(run_id, organization_id=organization_id)
        async with open_session() as session:
            filters = [RunEventRow.run_id == run_id]
            if organization_id is not None:
                filters.append(RunEventRow.organization_id == organization_id)
            rows = list(
                (
                    await session.execute(
                        select(RunEventRow)
                        .where(*filters)
                        .order_by(RunEventRow.created_at, RunEventRow.id)
                    )
                )
                .scalars()
                .all()
            )
            return [_run_event(row) for row in rows]

    async def mark_running(self, run_id: UUID, *, organization_id: UUID) -> RunRecord:
        now = datetime.now(UTC)
        async with open_session() as session:
            row = await session.get(Run, run_id)
            if row is None or row.organization_id != organization_id:
                raise NotFoundError(message="Run not found", code="RUN_NOT_FOUND", status_hint=404)
            row.status = "running"
            row.started_at = now
            row.updated_at = now
            await session.flush()
            return _run_record(row)

    async def complete_run(
        self,
        run_id: UUID,
        *,
        organization_id: UUID,
        status: RunStatus,
        result: dict[str, Any] | None = None,
        error: dict[str, Any] | None = None,
    ) -> RunRecord:
        now = datetime.now(UTC)
        async with open_session() as session:
            row = await session.get(Run, run_id)
            if row is None or row.organization_id != organization_id:
                raise NotFoundError(message="Run not found", code="RUN_NOT_FOUND", status_hint=404)
            row.status = status
            row.result = _json(result) if result is not None else None
            row.error = _json(error) if error is not None else None
            row.completed_at = now
            row.updated_at = now
            await session.flush()
            return _run_record(row)

    async def append_event(self, event: RunEvent) -> RunEvent:
        async with open_session() as session:
            run = await session.get(Run, event.run_id)
            if run is None or run.organization_id != event.organization_id:
                raise NotFoundError(message="Run not found", code="RUN_NOT_FOUND", status_hint=404)
            row = RunEventRow(
                id=event.event_id,
                run_id=event.run_id,
                organization_id=event.organization_id,
                type=event.type,
                stage=event.stage,
                message=event.message,
                progress=event.progress,
                payload=_json(event.payload),
                created_at=event.created_at,
            )
            session.add(row)
            await session.flush()
            return _run_event(row)


class InMemoryRunStore:
    def __init__(self) -> None:
        self._runs: dict[UUID, RunRecord] = {}
        self._events: dict[UUID, list[RunEvent]] = {}

    async def create_run(
        self,
        *,
        organization_id: UUID,
        kind: RunKind,
        request: dict[str, Any],
    ) -> RunRecord:
        run = RunRecord(
            run_id=uuid4(),
            organization_id=organization_id,
            kind=kind,
            request=_json(request),
        )
        self._runs[run.run_id] = run
        self._events[run.run_id] = []
        return run

    async def get_run(
        self,
        run_id: UUID,
        *,
        organization_id: UUID | None = None,
    ) -> RunRecord:
        run = self._runs.get(run_id)
        if run is None or (organization_id is not None and run.organization_id != organization_id):
            raise NotFoundError(message="Run not found", code="RUN_NOT_FOUND", status_hint=404)
        return run

    async def list_events(
        self,
        run_id: UUID,
        *,
        organization_id: UUID | None = None,
    ) -> list[RunEvent]:
        await self.get_run(run_id, organization_id=organization_id)
        return list(self._events.get(run_id, []))

    async def mark_running(self, run_id: UUID, *, organization_id: UUID) -> RunRecord:
        run = await self.get_run(run_id, organization_id=organization_id)
        updated = run.model_copy(update={"status": "running", "started_at": datetime.now(UTC)})
        self._runs[run_id] = updated
        return updated

    async def complete_run(
        self,
        run_id: UUID,
        *,
        organization_id: UUID,
        status: RunStatus,
        result: dict[str, Any] | None = None,
        error: dict[str, Any] | None = None,
    ) -> RunRecord:
        run = await self.get_run(run_id, organization_id=organization_id)
        updated = run.model_copy(
            update={
                "status": status,
                "result": _json(result) if result is not None else None,
                "error": _json(error) if error is not None else None,
                "completed_at": datetime.now(UTC),
            }
        )
        self._runs[run_id] = updated
        return updated

    async def append_event(self, event: RunEvent) -> RunEvent:
        await self.get_run(event.run_id, organization_id=event.organization_id)
        self._events.setdefault(event.run_id, []).append(event)
        return event


def _run_record(row: Run) -> RunRecord:
    return RunRecord(
        run_id=row.id,
        organization_id=row.organization_id,
        kind=cast(RunKind, row.kind),
        status=cast(RunStatus, row.status),
        request=row.request or {},
        result=row.result,
        error=row.error,
        created_at=row.created_at,
        started_at=row.started_at,
        completed_at=row.completed_at,
    )


def _run_event(row: RunEventRow) -> RunEvent:
    return RunEvent(
        event_id=row.id,
        run_id=row.run_id,
        organization_id=row.organization_id,
        type=row.type,
        stage=row.stage,
        message=row.message,
        progress=row.progress,
        payload=row.payload or {},
        created_at=row.created_at,
    )


def _json(value: Any) -> Any:
    return jsonable_encoder(value)
