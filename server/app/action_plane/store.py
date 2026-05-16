"""Persistence boundary for Action Plane v1."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID

from sqlalchemy import select

from app.action_plane.contracts import (
    ActionRecord,
    ActionRecordDraft,
    ActionStatus,
    ActionType,
    SavedCohortRecord,
)
from app.core.errors import NotFoundError
from app.db.models import OperatingAction, OperatingArtifact, SavedCohort
from app.db.session import open_session

_TERMINAL_STATUSES = {"completed", "dismissed"}


async def upsert_action_drafts(
    organization_id: UUID,
    *,
    drafts: list[ActionRecordDraft],
) -> tuple[list[ActionRecord], int, int]:
    if not drafts:
        return [], 0, 0

    now = datetime.now(UTC)
    created_count = 0
    updated_count = 0
    keys = [draft.action_key for draft in drafts]

    async with open_session() as session:
        existing_rows = list(
            (
                await session.execute(
                    select(OperatingAction).where(
                        OperatingAction.organization_id == organization_id,
                        OperatingAction.action_key.in_(keys),
                    )
                )
            )
            .scalars()
            .all()
        )
        by_key = {row.action_key: row for row in existing_rows}
        rows: list[OperatingAction] = []

        for draft in drafts:
            existing = by_key.get(draft.action_key)
            if existing is None:
                row = OperatingAction(
                    organization_id=organization_id,
                    artifact_id=draft.artifact_id,
                    run_id=draft.run_id,
                    action_key=draft.action_key,
                    action_type=draft.action_type,
                    status="proposed",
                    title=draft.title,
                    summary=draft.summary,
                    why=draft.why,
                    source_refs=draft.source_refs,
                    payload=draft.payload,
                    prepared_payload={},
                    created_at=now,
                    updated_at=now,
                )
                session.add(row)
                rows.append(row)
                created_count += 1
                continue

            existing.artifact_id = draft.artifact_id
            existing.run_id = draft.run_id
            existing.action_type = draft.action_type
            if existing.status not in _TERMINAL_STATUSES:
                existing.title = draft.title
                existing.summary = draft.summary
                existing.why = draft.why
                existing.source_refs = draft.source_refs
                existing.payload = draft.payload
            existing.updated_at = now
            rows.append(existing)
            updated_count += 1

        await session.flush()
        records = [_action_record(row) for row in rows]
    return records, created_count, updated_count


async def load_actions(
    organization_id: UUID,
    *,
    action_type: ActionType | None = None,
    status: ActionStatus | None = None,
    include_terminal: bool = False,
    limit: int = 100,
) -> list[ActionRecord]:
    async with open_session() as session:
        filters = [OperatingAction.organization_id == organization_id]
        if action_type is not None:
            filters.append(OperatingAction.action_type == action_type)
        if status is not None:
            filters.append(OperatingAction.status == status)
        elif not include_terminal:
            filters.append(OperatingAction.status.not_in(list(_TERMINAL_STATUSES)))
        rows = list(
            (
                await session.execute(
                    select(OperatingAction)
                    .where(*filters)
                    .order_by(OperatingAction.created_at.desc())
                    .limit(limit)
                )
            )
            .scalars()
            .all()
        )
    return [_action_record(row) for row in rows]


async def load_action(organization_id: UUID, *, action_id: UUID) -> ActionRecord:
    async with open_session() as session:
        row = await session.get(OperatingAction, action_id)
        if row is None or row.organization_id != organization_id:
            raise NotFoundError(
                message="Action not found",
                code="ACTION_NOT_FOUND",
                status_hint=404,
            )
        return _action_record(row)


async def load_related_action_artifacts(
    organization_id: UUID,
    *,
    action: ActionRecord,
) -> dict[str, dict]:
    graph_id = action.source_refs.get("graph_id")
    if not isinstance(graph_id, str) or not graph_id:
        return {}
    keys = {
        "table": f"table:{graph_id}",
        "audience": f"audience:{graph_id}",
        "insight": f"insight:{graph_id}",
        "lineage": f"lineage:{graph_id}",
    }
    async with open_session() as session:
        rows = list(
            (
                await session.execute(
                    select(OperatingArtifact).where(
                        OperatingArtifact.organization_id == organization_id,
                        OperatingArtifact.artifact_key.in_(list(keys.values())),
                    )
                )
            )
            .scalars()
            .all()
        )
    by_key = {row.artifact_key: row.payload or {} for row in rows}
    return {name: by_key[key] for name, key in keys.items() if key in by_key}


async def mark_action_prepared(
    organization_id: UUID,
    *,
    action_id: UUID,
    prepared_payload: dict,
) -> ActionRecord:
    now = datetime.now(UTC)
    async with open_session() as session:
        row = await session.get(OperatingAction, action_id)
        if row is None or row.organization_id != organization_id:
            raise NotFoundError(
                message="Action not found",
                code="ACTION_NOT_FOUND",
                status_hint=404,
            )
        row.status = "prepared"
        row.prepared_payload = prepared_payload
        row.prepared_at = now
        row.updated_at = now
        await session.flush()
        return _action_record(row)


async def mark_action_completed(organization_id: UUID, *, action_id: UUID) -> ActionRecord:
    return await _mark_action_status(organization_id, action_id=action_id, status="completed")


async def mark_action_dismissed(organization_id: UUID, *, action_id: UUID) -> ActionRecord:
    return await _mark_action_status(organization_id, action_id=action_id, status="dismissed")


async def upsert_saved_cohort(
    organization_id: UUID,
    *,
    action: ActionRecord,
    prepared_payload: dict[str, Any],
) -> SavedCohortRecord:
    now = datetime.now(UTC)
    cohort_key = f"action:{action.id}"
    raw_rows = prepared_payload.get("rows")
    rows: list[Any] = raw_rows if isinstance(raw_rows, list) else []
    raw_audience = prepared_payload.get("audience")
    audience: dict[str, Any] = raw_audience if isinstance(raw_audience, dict) else {}
    async with open_session() as session:
        existing = (
            await session.execute(
                select(SavedCohort).where(
                    SavedCohort.organization_id == organization_id,
                    SavedCohort.cohort_key == cohort_key,
                )
            )
        ).scalar_one_or_none()
        if existing is None:
            existing = SavedCohort(
                organization_id=organization_id,
                action_id=action.id,
                cohort_key=cohort_key,
                name=str(prepared_payload.get("name") or action.title),
                description=str(prepared_payload.get("description") or action.summary),
                audience=audience,
                rows=[row for row in rows if isinstance(row, dict)],
                source_refs=action.source_refs,
                created_at=now,
                updated_at=now,
            )
            session.add(existing)
        else:
            existing.name = str(prepared_payload.get("name") or action.title)
            existing.description = str(prepared_payload.get("description") or action.summary)
            existing.audience = audience
            existing.rows = [row for row in rows if isinstance(row, dict)]
            existing.source_refs = action.source_refs
            existing.updated_at = now
        await session.flush()
        return _cohort_record(existing)


async def load_saved_cohorts(organization_id: UUID, *, limit: int = 100) -> list[SavedCohortRecord]:
    async with open_session() as session:
        rows = list(
            (
                await session.execute(
                    select(SavedCohort)
                    .where(SavedCohort.organization_id == organization_id)
                    .order_by(SavedCohort.updated_at.desc())
                    .limit(limit)
                )
            )
            .scalars()
            .all()
        )
    return [_cohort_record(row) for row in rows]


async def _mark_action_status(
    organization_id: UUID,
    *,
    action_id: UUID,
    status: ActionStatus,
) -> ActionRecord:
    now = datetime.now(UTC)
    async with open_session() as session:
        row = await session.get(OperatingAction, action_id)
        if row is None or row.organization_id != organization_id:
            raise NotFoundError(
                message="Action not found",
                code="ACTION_NOT_FOUND",
                status_hint=404,
            )
        row.status = status
        row.completed_at = now if status == "completed" else None
        row.dismissed_at = now if status == "dismissed" else None
        row.updated_at = now
        await session.flush()
        return _action_record(row)


def _action_record(row: OperatingAction) -> ActionRecord:
    return ActionRecord(
        id=row.id,
        organization_id=row.organization_id,
        artifact_id=row.artifact_id,
        run_id=row.run_id,
        action_key=row.action_key,
        action_type=cast(ActionType, row.action_type),
        status=cast(ActionStatus, row.status),
        title=row.title,
        summary=row.summary,
        why=row.why,
        source_refs=row.source_refs or {},
        payload=row.payload or {},
        prepared_payload=row.prepared_payload or {},
        prepared_at=row.prepared_at,
        completed_at=row.completed_at,
        dismissed_at=row.dismissed_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _cohort_record(row: SavedCohort) -> SavedCohortRecord:
    return SavedCohortRecord(
        id=row.id,
        organization_id=row.organization_id,
        action_id=row.action_id,
        cohort_key=row.cohort_key,
        name=row.name,
        description=row.description,
        audience=row.audience or {},
        rows=[item for item in row.rows or [] if isinstance(item, dict)],
        source_refs=row.source_refs or {},
        created_at=row.created_at,
        updated_at=row.updated_at,
    )
