"""Persistence boundary for Agent Plane canonical context."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Any
from uuid import UUID

from sqlalchemy import or_, select

from app.agent_plane.contracts import (
    AssetEvidence,
    CanonicalContextPack,
    FieldEvidence,
    GraphEdgeEvidence,
    SnapshotEvidence,
)
from app.data_plane.naming import quote_ident
from app.data_plane.storage import safe_query
from app.db.models import (
    BusinessMemory,
    CanonicalAsset,
    CanonicalField,
    CanonicalSnapshot,
    DataGraphEdge,
)
from app.db.session import open_session

_PREVIEW_LIMIT = 5


async def load_context_pack(
    organization_id: UUID,
    *,
    snapshot_ids: list[UUID] | None = None,
    include_preview_rows: bool = True,
) -> CanonicalContextPack:
    async with open_session() as session:
        snapshots = await _load_snapshots(session, organization_id, snapshot_ids=snapshot_ids)
        snapshot_id_set = {snapshot.id for snapshot in snapshots}
        assets = list(
            (
                await session.execute(
                    select(CanonicalAsset)
                    .where(
                        CanonicalAsset.organization_id == organization_id,
                        CanonicalAsset.snapshot_id.in_(snapshot_id_set),
                    )
                    .order_by(CanonicalAsset.qualified_name)
                )
            )
            .scalars()
            .all()
        )
        asset_ids = [asset.id for asset in assets]
        fields = list(
            (
                await session.execute(
                    select(CanonicalField)
                    .where(
                        CanonicalField.organization_id == organization_id,
                        CanonicalField.asset_id.in_(asset_ids),
                    )
                    .order_by(CanonicalField.asset_id, CanonicalField.ordinal)
                )
            )
            .scalars()
            .all()
        ) if asset_ids else []
        edges = list(
            (
                await session.execute(
                    select(DataGraphEdge)
                    .where(
                        DataGraphEdge.organization_id == organization_id,
                        or_(
                            DataGraphEdge.snapshot_id.in_(snapshot_id_set),
                            DataGraphEdge.snapshot_id.is_(None),
                        ),
                    )
                    .order_by(DataGraphEdge.created_at)
                )
            )
            .scalars()
            .all()
        )
        memories = [
            {
                "key": memory.key,
                "kind": memory.kind,
                "scope": memory.scope,
                "subject_ref": memory.subject_ref or {},
                "statement": memory.value,
                "value": memory.value,
                "evidence_refs": memory.evidence_refs or [],
                "source": memory.source,
                "confidence": memory.confidence,
                "metadata": memory.metadata_ or {},
            }
            for memory in (
                (
                    await session.execute(
                        select(BusinessMemory)
                        .where(
                            BusinessMemory.organization_id == organization_id,
                            BusinessMemory.status == "active",
                        )
                        .order_by(BusinessMemory.updated_at.desc())
                    )
                )
                .scalars()
                .all()
            )
        ]

    fields_by_asset: dict[UUID, list[CanonicalField]] = defaultdict(list)
    for field in fields:
        if not _is_system_field(field):
            fields_by_asset[field.asset_id].append(field)

    preview_by_asset: dict[UUID, list[dict[str, Any]]] = {}
    if include_preview_rows:
        preview_by_asset = await _load_previews(organization_id, assets, fields_by_asset)

    return CanonicalContextPack(
        organization_id=str(organization_id),
        snapshots=[_snapshot_evidence(snapshot) for snapshot in snapshots],
        assets=[
            _asset_evidence(asset, fields_by_asset.get(asset.id, []), preview_by_asset.get(asset.id, []))
            for asset in assets
        ],
        graph_edges=[_edge_evidence(edge) for edge in edges],
        memories=memories,
    )


async def _load_snapshots(session: Any, organization_id: UUID, *, snapshot_ids: list[UUID] | None) -> list[CanonicalSnapshot]:
    if snapshot_ids:
        return list(
            (
                await session.execute(
                    select(CanonicalSnapshot)
                    .where(
                        CanonicalSnapshot.organization_id == organization_id,
                        CanonicalSnapshot.id.in_(snapshot_ids),
                    )
                    .order_by(CanonicalSnapshot.started_at.desc())
                )
            )
            .scalars()
            .all()
        )

    all_completed = list(
        (
            await session.execute(
                select(CanonicalSnapshot)
                .where(
                    CanonicalSnapshot.organization_id == organization_id,
                    CanonicalSnapshot.status == "completed",
                )
                .order_by(CanonicalSnapshot.started_at.desc())
            )
        )
        .scalars()
        .all()
    )
    latest_by_source: dict[UUID, CanonicalSnapshot] = {}
    for snapshot in all_completed:
        latest_by_source.setdefault(snapshot.data_source_id, snapshot)
    return list(latest_by_source.values())


async def _load_previews(
    organization_id: UUID,
    assets: list[CanonicalAsset],
    fields_by_asset: dict[UUID, list[CanonicalField]],
) -> dict[UUID, list[dict[str, Any]]]:
    async def _preview(asset: CanonicalAsset) -> tuple[UUID, list[dict[str, Any]]]:
        fields = fields_by_asset.get(asset.id, [])
        if not fields:
            return asset.id, []
        columns = ", ".join(quote_ident(field.name) for field in fields[:25])
        sql = f"SELECT {columns} FROM {quote_ident(asset.storage_table)} LIMIT {_PREVIEW_LIMIT}"
        try:
            rows = await asyncio.to_thread(safe_query, organization_id, sql, max_rows=_PREVIEW_LIMIT)
        except Exception:
            rows = []
        return asset.id, rows

    pairs = await asyncio.gather(*[_preview(asset) for asset in assets])
    return dict(pairs)


def _snapshot_evidence(snapshot: CanonicalSnapshot) -> SnapshotEvidence:
    return SnapshotEvidence(
        snapshot_id=str(snapshot.id),
        data_source_id=str(snapshot.data_source_id),
        snapshot_key=snapshot.snapshot_key,
        mode=snapshot.mode,
        status=snapshot.status,
        started_at=snapshot.started_at.isoformat(),
        completed_at=snapshot.completed_at.isoformat() if snapshot.completed_at else None,
        asset_count=snapshot.asset_count,
        row_count=snapshot.row_count,
        metadata=snapshot.metadata_ or {},
    )


def _asset_evidence(
    asset: CanonicalAsset,
    fields: list[CanonicalField],
    preview_rows: list[dict[str, Any]],
) -> AssetEvidence:
    return AssetEvidence(
        asset_id=str(asset.id),
        data_source_id=str(asset.data_source_id),
        snapshot_id=str(asset.snapshot_id) if asset.snapshot_id else None,
        asset_key=asset.asset_key,
        qualified_name=asset.qualified_name,
        storage_table=asset.storage_table,
        label=asset.label,
        asset_type=asset.asset_type,
        row_count=asset.row_count,
        field_count=len(fields),
        metadata=asset.metadata_ or {},
        profile=asset.profile or {},
        fields=[_field_evidence(field) for field in fields],
        preview_rows=preview_rows,
    )


def _field_evidence(field: CanonicalField) -> FieldEvidence:
    return FieldEvidence(
        field_id=str(field.id),
        asset_id=str(field.asset_id),
        name=field.name,
        ordinal=field.ordinal,
        storage_type=field.storage_type,
        observed_type=field.observed_type,
        nullable=field.nullable,
        sample_values=field.sample_values or [],
        profile=field.profile or {},
    )


def _edge_evidence(edge: DataGraphEdge) -> GraphEdgeEvidence:
    return GraphEdgeEvidence(
        edge_id=str(edge.id),
        snapshot_id=str(edge.snapshot_id) if edge.snapshot_id else None,
        subject_type=edge.subject_type,
        subject_id=edge.subject_id,
        predicate=edge.predicate,
        object_type=edge.object_type,
        object_id=edge.object_id,
        status=edge.status,
        confidence=edge.confidence,
        created_by=edge.created_by,
        evidence=edge.evidence or {},
    )


def _is_system_field(field: CanonicalField) -> bool:
    profile = field.profile if isinstance(field.profile, dict) else {}
    return bool(profile.get("system_column")) or field.name.startswith("_bf_")
