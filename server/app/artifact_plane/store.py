"""Persistence boundary for durable operating artifacts."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import cast
from uuid import UUID

from sqlalchemy import select

from app.artifact_plane.assembler import artifact_fingerprint
from app.artifact_plane.contracts import (
    ArtifactDraft,
    ArtifactKind,
    ArtifactPlaneRunResult,
    ArtifactRecord,
    ArtifactStatus,
)
from app.core.errors import NotFoundError
from app.db.models import OperatingArtifact
from app.db.session import open_session

_TERMINAL_STATUSES = {"dismissed", "resolved"}


async def upsert_artifacts(
    organization_id: UUID,
    *,
    run_id: UUID,
    drafts: list[ArtifactDraft],
) -> ArtifactPlaneRunResult:
    if not drafts:
        return ArtifactPlaneRunResult(organization_id=organization_id, run_id=run_id)

    now = datetime.now(UTC)
    keys = [draft.artifact_key for draft in drafts]
    created_count = 0
    updated_count = 0
    unchanged_count = 0

    async with open_session() as session:
        existing_rows = list(
            (
                await session.execute(
                    select(OperatingArtifact).where(
                        OperatingArtifact.organization_id == organization_id,
                        OperatingArtifact.artifact_key.in_(keys),
                    )
                )
            )
            .scalars()
            .all()
        )
        by_key = {row.artifact_key: row for row in existing_rows}
        rows: list[OperatingArtifact] = []

        for draft in drafts:
            fingerprint = artifact_fingerprint(draft)
            existing = by_key.get(draft.artifact_key)
            if existing is None:
                row = OperatingArtifact(
                    organization_id=organization_id,
                    run_id=run_id,
                    artifact_key=draft.artifact_key,
                    kind=draft.kind,
                    status="new",
                    title=draft.title,
                    summary=draft.summary,
                    why=draft.why,
                    tags=draft.tags,
                    priority=draft.priority,
                    source_refs=draft.source_refs,
                    payload=draft.payload,
                    fingerprint=fingerprint,
                    first_seen_at=now,
                    last_seen_at=now,
                    created_at=now,
                    updated_at=now,
                )
                session.add(row)
                rows.append(row)
                created_count += 1
                continue

            existing.run_id = run_id
            existing.last_seen_at = now
            existing.updated_at = now
            if existing.fingerprint == fingerprint:
                unchanged_count += 1
                rows.append(existing)
                continue

            existing.kind = draft.kind
            if existing.status not in _TERMINAL_STATUSES:
                existing.status = "new"
                existing.dismissed_at = None
                existing.resolved_at = None
            existing.title = draft.title
            existing.summary = draft.summary
            existing.why = draft.why
            existing.tags = draft.tags
            existing.priority = draft.priority
            existing.source_refs = draft.source_refs
            existing.payload = draft.payload
            existing.fingerprint = fingerprint
            rows.append(existing)
            updated_count += 1

        await session.flush()
        records = [_artifact_record(row) for row in rows]

    return _result(
        organization_id=organization_id,
        run_id=run_id,
        artifacts=records,
        created_count=created_count,
        updated_count=updated_count,
        unchanged_count=unchanged_count,
    )


async def load_artifacts(
    organization_id: UUID,
    *,
    kind: ArtifactKind | None = None,
    status: ArtifactStatus | None = None,
    include_terminal: bool = False,
    limit: int = 100,
) -> list[ArtifactRecord]:
    async with open_session() as session:
        filters = [OperatingArtifact.organization_id == organization_id]
        if kind is not None:
            filters.append(OperatingArtifact.kind == kind)
        if status is not None:
            filters.append(OperatingArtifact.status == status)
        elif not include_terminal:
            filters.append(OperatingArtifact.status.not_in(list(_TERMINAL_STATUSES)))
        rows = list(
            (
                await session.execute(
                    select(OperatingArtifact)
                    .where(*filters)
                    .order_by(OperatingArtifact.priority.desc(), OperatingArtifact.last_seen_at.desc())
                    .limit(limit)
                )
            )
            .scalars()
            .all()
        )
    return [_artifact_record(row) for row in rows]


async def load_run_artifacts(organization_id: UUID, *, run_id: UUID) -> list[ArtifactRecord]:
    async with open_session() as session:
        rows = list(
            (
                await session.execute(
                    select(OperatingArtifact)
                    .where(
                        OperatingArtifact.organization_id == organization_id,
                        OperatingArtifact.run_id == run_id,
                    )
                    .order_by(OperatingArtifact.priority.desc(), OperatingArtifact.kind)
                )
            )
            .scalars()
            .all()
        )
    return [_artifact_record(row) for row in rows]


async def latest_artifact(
    organization_id: UUID,
    *,
    kind: ArtifactKind,
) -> ArtifactRecord | None:
    rows = await load_artifacts(organization_id, kind=kind, limit=1)
    return rows[0] if rows else None


async def update_artifact_status(
    organization_id: UUID,
    *,
    artifact_id: UUID,
    status: ArtifactStatus,
    snoozed_until: datetime | None = None,
) -> ArtifactRecord:
    now = datetime.now(UTC)
    async with open_session() as session:
        row = await session.get(OperatingArtifact, artifact_id)
        if row is None or row.organization_id != organization_id:
            raise NotFoundError(
                message="Artifact not found",
                code="ARTIFACT_NOT_FOUND",
                status_hint=404,
            )
        row.status = status
        row.updated_at = now
        row.snoozed_until = snoozed_until if status == "snoozed" else None
        row.dismissed_at = now if status == "dismissed" else None
        row.resolved_at = now if status == "resolved" else None
        await session.flush()
        return _artifact_record(row)


def _result(
    *,
    organization_id: UUID,
    run_id: UUID,
    artifacts: list[ArtifactRecord],
    created_count: int,
    updated_count: int,
    unchanged_count: int,
) -> ArtifactPlaneRunResult:
    return ArtifactPlaneRunResult(
        organization_id=organization_id,
        run_id=run_id,
        artifacts=artifacts,
        brief_artifact_id=_first_id(artifacts, "brief"),
        business_view_artifact_id=_first_id(artifacts, "business_view"),
        business_surfaces_artifact_id=_first_id(artifacts, "business_surfaces"),
        entity_resolution_artifact_id=_first_id(artifacts, "entity_resolution"),
        knowledge_graph_artifact_id=_first_id(artifacts, "knowledge_graph"),
        semantic_layer_artifact_id=_first_id(artifacts, "semantic_layer"),
        chart_grammar_artifact_id=_first_id(artifacts, "chart_grammar"),
        insight_ranking_artifact_id=_first_id(artifacts, "insight_ranking"),
        lineage_artifact_id=_first_id(artifacts, "lineage"),
        inbox_item_ids=[artifact.id for artifact in artifacts if artifact.kind == "inbox_item"],
        ask_artifact_ids=[
            artifact.id
            for artifact in artifacts
            if artifact.kind in {"ask_answer", "table", "chart", "narrative", "lineage"}
        ],
        action_artifact_ids=[artifact.id for artifact in artifacts if artifact.kind == "action"],
        created_count=created_count,
        updated_count=updated_count,
        unchanged_count=unchanged_count,
    )


def _first_id(artifacts: list[ArtifactRecord], kind: ArtifactKind) -> UUID | None:
    for artifact in artifacts:
        if artifact.kind == kind:
            return artifact.id
    return None


def _artifact_record(row: OperatingArtifact) -> ArtifactRecord:
    return ArtifactRecord(
        id=row.id,
        organization_id=row.organization_id,
        run_id=row.run_id,
        artifact_key=row.artifact_key,
        kind=cast(ArtifactKind, row.kind),
        status=cast(ArtifactStatus, row.status),
        title=row.title,
        summary=row.summary,
        why=row.why,
        tags=[str(tag) for tag in row.tags or []],
        priority=row.priority,
        source_refs=row.source_refs or {},
        payload=row.payload or {},
        fingerprint=row.fingerprint,
        first_seen_at=row.first_seen_at,
        last_seen_at=row.last_seen_at,
        snoozed_until=row.snoozed_until,
        dismissed_at=row.dismissed_at,
        resolved_at=row.resolved_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )
