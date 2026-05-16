"""Persistence for autonomous business memory."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select

from app.db.models import BusinessMemory
from app.db.session import open_session
from app.memory_plane.contracts import BusinessMemoryRecord, MemoryCandidate, MemoryWriteResult


async def upsert_memory_candidates(
    organization_id: UUID,
    candidates: list[MemoryCandidate],
) -> list[MemoryWriteResult]:
    if not candidates:
        return []

    now = datetime.now(UTC)
    writes: list[MemoryWriteResult] = []
    async with open_session() as session:
        existing_rows = list(
            (
                await session.execute(
                    select(BusinessMemory).where(
                        BusinessMemory.organization_id == organization_id,
                        BusinessMemory.key.in_([candidate.key for candidate in candidates]),
                    )
                )
            )
            .scalars()
            .all()
        )
        by_key = {row.key: row for row in existing_rows}
        for candidate in candidates:
            existing = by_key.get(candidate.key)
            if existing is None:
                session.add(
                    BusinessMemory(
                        organization_id=organization_id,
                        key=candidate.key,
                        value=candidate.statement,
                        kind=candidate.kind,
                        scope=candidate.scope,
                        subject_ref=candidate.subject_ref,
                        evidence_refs=candidate.evidence_refs,
                        metadata_=candidate.metadata,
                        source=candidate.source,
                        status="active",
                        confidence=candidate.confidence,
                        last_confirmed_at=now,
                    )
                )
                writes.append(
                    MemoryWriteResult(
                        key=candidate.key,
                        action="created",
                        confidence=candidate.confidence,
                    )
                )
                continue

            if _same_memory(existing, candidate):
                writes.append(
                    MemoryWriteResult(
                        key=candidate.key,
                        action="unchanged",
                        confidence=existing.confidence,
                    )
                )
                continue

            if existing.source == "user" and existing.confidence > candidate.confidence:
                writes.append(
                    MemoryWriteResult(
                        key=candidate.key,
                        action="skipped",
                        reason="user memory has higher confidence",
                        confidence=existing.confidence,
                    )
                )
                continue

            existing.value = candidate.statement
            existing.kind = candidate.kind
            existing.scope = candidate.scope
            existing.subject_ref = candidate.subject_ref
            existing.evidence_refs = candidate.evidence_refs
            existing.metadata_ = candidate.metadata
            existing.source = candidate.source
            existing.status = "active"
            existing.confidence = max(existing.confidence, candidate.confidence)
            existing.last_confirmed_at = now
            writes.append(
                MemoryWriteResult(
                    key=candidate.key,
                    action="updated",
                    confidence=existing.confidence,
                )
            )
    return writes


async def load_business_memories(
    organization_id: UUID,
    *,
    limit: int = 200,
) -> list[BusinessMemoryRecord]:
    async with open_session() as session:
        rows = list(
            (
                await session.execute(
                    select(BusinessMemory)
                    .where(
                        BusinessMemory.organization_id == organization_id,
                        BusinessMemory.status == "active",
                    )
                    .order_by(BusinessMemory.updated_at.desc())
                    .limit(limit)
                )
            )
            .scalars()
            .all()
        )
    return [
        BusinessMemoryRecord(
            id=str(row.id),
            key=row.key,
            kind=row.kind,
            scope=row.scope,
            subject_ref=row.subject_ref or {},
            statement=row.value,
            evidence_refs=row.evidence_refs or [],
            confidence=row.confidence,
            source=row.source,
            status=row.status,
            metadata=row.metadata_ or {},
            last_confirmed_at=row.last_confirmed_at,
        )
        for row in rows
    ]


def _same_memory(existing: BusinessMemory, candidate: MemoryCandidate) -> bool:
    return (
        existing.value == candidate.statement
        and existing.kind == candidate.kind
        and existing.scope == candidate.scope
        and (existing.subject_ref or {}) == candidate.subject_ref
        and (existing.evidence_refs or []) == candidate.evidence_refs
        and (existing.metadata_ or {}) == candidate.metadata
        and existing.status == "active"
        and existing.confidence >= candidate.confidence
    )
