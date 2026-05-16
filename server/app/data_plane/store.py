"""Persistence boundary for the canonical data-plane catalog."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import delete, or_, select

from app.connector_runtime.store import DataSourceRecord
from app.data_plane.catalog import (
    asset_type_from_metadata,
    node_id,
    snapshot_key,
)
from app.db.models import (
    CanonicalAsset,
    CanonicalField,
    CanonicalSnapshot,
    DataGraphEdge,
    DataSource,
)
from app.db.session import open_session


def _graph_edge(
    *,
    organization_id: UUID,
    snapshot_id: UUID | None,
    subject_type: str,
    subject_id: str,
    predicate: str,
    object_type: str,
    object_id: str,
    confidence: float = 1.0,
    created_by: str = "canonicalizer",
    evidence: dict[str, Any] | None = None,
) -> DataGraphEdge:
    return DataGraphEdge(
        organization_id=organization_id,
        snapshot_id=snapshot_id,
        subject_type=subject_type,
        subject_id=subject_id,
        predicate=predicate,
        object_type=object_type,
        object_id=object_id,
        confidence=confidence,
        created_by=created_by,
        evidence=evidence or {},
    )


async def begin_source_snapshot(
    data_source: DataSourceRecord,
    *,
    now: datetime,
    metadata: dict[str, Any] | None = None,
) -> UUID:
    async with open_session() as session:
        persistent_source = await session.get(DataSource, data_source.id)
        if persistent_source is None:
            raise RuntimeError("Data source disappeared during canonicalization")
        await _reset_canonical_catalog_for_source(session, persistent_source)
        snapshot = await _begin_canonical_snapshot(
            session,
            persistent_source,
            now=now,
            metadata=metadata,
        )
        return snapshot.id


async def register_source_asset(
    data_source: DataSourceRecord,
    *,
    snapshot_id: UUID,
    asset_key: str,
    qualified_name: str,
    label: str,
    columns: list[str],
    row_count: int,
    metadata: dict[str, Any] | None = None,
    profile: dict[str, Any] | None = None,
    source_columns_by_storage: dict[str, str | None] | None = None,
) -> UUID:
    async with open_session() as session:
        persistent_source = await session.get(DataSource, data_source.id)
        if persistent_source is None:
            raise RuntimeError("Data source disappeared during canonicalization")
        snapshot = await session.get(CanonicalSnapshot, snapshot_id)
        if snapshot is None:
            raise RuntimeError("Canonical snapshot disappeared during sync")
        asset = await _register_canonical_asset(
            session,
            persistent_source,
            snapshot,
            asset_key=asset_key,
            qualified_name=qualified_name,
            label=label,
            columns=columns,
            row_count=row_count,
            metadata=metadata,
            profile=profile,
            source_columns_by_storage=source_columns_by_storage,
        )
        return asset.id


async def update_source_asset_row_count(asset_id: UUID, *, row_count: int) -> None:
    async with open_session() as session:
        asset = await session.get(CanonicalAsset, asset_id)
        if asset is not None:
            asset.row_count = row_count


async def complete_source_snapshot(
    snapshot_id: UUID,
    *,
    status: str,
    asset_count: int,
    row_count: int,
    now: datetime,
    metadata: dict[str, Any] | None = None,
) -> None:
    async with open_session() as session:
        snapshot = await session.get(CanonicalSnapshot, snapshot_id)
        if snapshot is not None:
            await _complete_canonical_snapshot(
                session,
                snapshot,
                status=status,
                asset_count=asset_count,
                row_count=row_count,
                now=now,
                metadata=metadata,
            )


async def fail_source_snapshot(
    snapshot_id: UUID,
    *,
    asset_count: int,
    row_count: int,
    now: datetime,
    error: str,
) -> None:
    await complete_source_snapshot(
        snapshot_id,
        status="failed",
        asset_count=asset_count,
        row_count=row_count,
        now=now,
        metadata={"error": error},
    )


async def _reset_canonical_catalog_for_source(session: Any, data_source: DataSource) -> None:
    asset_ids = list(
        (
            await session.execute(
                select(CanonicalAsset.id).where(
                    CanonicalAsset.organization_id == data_source.organization_id,
                    CanonicalAsset.data_source_id == data_source.id,
                )
            )
        )
        .scalars()
        .all()
    )
    snapshot_ids = list(
        (
            await session.execute(
                select(CanonicalSnapshot.id).where(
                    CanonicalSnapshot.organization_id == data_source.organization_id,
                    CanonicalSnapshot.data_source_id == data_source.id,
                )
            )
        )
        .scalars()
        .all()
    )
    field_ids: list[UUID] = []
    if asset_ids:
        field_ids = list(
            (
                await session.execute(
                    select(CanonicalField.id).where(CanonicalField.asset_id.in_(asset_ids))
                )
            )
            .scalars()
            .all()
        )

    stale_node_ids = [
        *[node_id("canonical_asset", asset_id) for asset_id in asset_ids],
        *[node_id("canonical_field", field_id) for field_id in field_ids],
        node_id("data_source", data_source.id),
    ]
    edge_filters = [DataGraphEdge.organization_id == data_source.organization_id]
    if snapshot_ids or stale_node_ids:
        stale_filters = []
        if snapshot_ids:
            stale_filters.append(DataGraphEdge.snapshot_id.in_(snapshot_ids))
        if stale_node_ids:
            stale_filters.append(DataGraphEdge.subject_id.in_(stale_node_ids))
            stale_filters.append(DataGraphEdge.object_id.in_(stale_node_ids))
        edge_filters.append(or_(*stale_filters))
        await session.execute(delete(DataGraphEdge).where(*edge_filters))

    await session.execute(
        delete(CanonicalAsset).where(
            CanonicalAsset.organization_id == data_source.organization_id,
            CanonicalAsset.data_source_id == data_source.id,
        )
    )


async def _remove_conflicting_canonical_assets(
    session: Any,
    data_source: DataSource,
    *,
    qualified_name: str,
) -> None:
    asset_ids = list(
        (
            await session.execute(
                select(CanonicalAsset.id).where(
                    CanonicalAsset.organization_id == data_source.organization_id,
                    CanonicalAsset.qualified_name == qualified_name,
                    CanonicalAsset.data_source_id != data_source.id,
                )
            )
        )
        .scalars()
        .all()
    )
    if not asset_ids:
        return
    field_ids = list(
        (
            await session.execute(
                select(CanonicalField.id).where(CanonicalField.asset_id.in_(asset_ids))
            )
        )
        .scalars()
        .all()
    )
    stale_node_ids = [
        *[node_id("canonical_asset", asset_id) for asset_id in asset_ids],
        *[node_id("canonical_field", field_id) for field_id in field_ids],
    ]
    if stale_node_ids:
        await session.execute(
            delete(DataGraphEdge).where(
                DataGraphEdge.organization_id == data_source.organization_id,
                or_(
                    DataGraphEdge.subject_id.in_(stale_node_ids),
                    DataGraphEdge.object_id.in_(stale_node_ids),
                ),
            )
        )
    await session.execute(
        delete(CanonicalAsset).where(
            CanonicalAsset.organization_id == data_source.organization_id,
            CanonicalAsset.id.in_(asset_ids),
        )
    )


async def _begin_canonical_snapshot(
    session: Any,
    data_source: DataSource,
    *,
    now: datetime,
    metadata: dict[str, Any] | None = None,
) -> CanonicalSnapshot:
    snapshot = CanonicalSnapshot(
        organization_id=data_source.organization_id,
        data_source_id=data_source.id,
        snapshot_key=snapshot_key(data_source.id, now),
        mode="full_refresh",
        status="running",
        started_at=now,
        metadata_=metadata or {},
    )
    session.add(snapshot)
    await session.flush()
    return snapshot


async def _register_canonical_asset(
    session: Any,
    data_source: DataSource,
    snapshot: CanonicalSnapshot,
    *,
    asset_key: str,
    qualified_name: str,
    label: str,
    columns: list[str],
    row_count: int,
    metadata: dict[str, Any] | None = None,
    profile: dict[str, Any] | None = None,
    source_columns_by_storage: dict[str, str | None] | None = None,
) -> CanonicalAsset:
    metadata = metadata or {}
    await _remove_conflicting_canonical_assets(
        session,
        data_source,
        qualified_name=qualified_name,
    )
    asset = CanonicalAsset(
        organization_id=data_source.organization_id,
        data_source_id=data_source.id,
        snapshot_id=snapshot.id,
        asset_key=asset_key,
        qualified_name=qualified_name,
        storage_table=qualified_name,
        label=label,
        asset_type=asset_type_from_metadata(metadata),
        status="active",
        row_count=row_count,
        field_count=len(columns),
        metadata_=metadata,
        profile=profile or {},
    )
    session.add(asset)
    await session.flush()

    source_node = node_id("data_source", data_source.id)
    snapshot_node = node_id("canonical_snapshot", snapshot.id)
    asset_node = node_id("canonical_asset", asset.id)
    session.add_all(
        [
            _graph_edge(
                organization_id=data_source.organization_id,
                snapshot_id=snapshot.id,
                subject_type="data_source",
                subject_id=source_node,
                predicate="HAS_ASSET",
                object_type="canonical_asset",
                object_id=asset_node,
                evidence={"qualified_name": qualified_name, "asset_key": asset_key},
            ),
            _graph_edge(
                organization_id=data_source.organization_id,
                snapshot_id=snapshot.id,
                subject_type="canonical_snapshot",
                subject_id=snapshot_node,
                predicate="CAPTURED_ASSET",
                object_type="canonical_asset",
                object_id=asset_node,
                evidence={"qualified_name": qualified_name, "row_count": row_count},
            ),
        ]
    )

    fields: list[CanonicalField] = []
    for ordinal, column in enumerate(columns):
        source_column = (source_columns_by_storage or {}).get(column, column)
        canonical_field = CanonicalField(
            organization_id=data_source.organization_id,
            asset_id=asset.id,
            name=column,
            ordinal=ordinal,
            storage_type="varchar",
            observed_type="unknown",
            nullable=True,
            sample_values=[],
            profile={
                "source_column": source_column,
                "ordinal": ordinal,
                "system_column": source_column is None,
            },
        )
        session.add(canonical_field)
        fields.append(canonical_field)
    await session.flush()

    for field in fields:
        field_node = node_id("canonical_field", field.id)
        source_column = (
            field.profile.get("source_column") if isinstance(field.profile, dict) else field.name
        )
        session.add(
            _graph_edge(
                organization_id=data_source.organization_id,
                snapshot_id=snapshot.id,
                subject_type="canonical_asset",
                subject_id=asset_node,
                predicate="HAS_FIELD",
                object_type="canonical_field",
                object_id=field_node,
                evidence={
                    "qualified_name": qualified_name,
                    "field": field.name,
                    "ordinal": field.ordinal,
                },
            )
        )
        if source_column is None:
            session.add(
                _graph_edge(
                    organization_id=data_source.organization_id,
                    snapshot_id=snapshot.id,
                    subject_type="canonical_field",
                    subject_id=field_node,
                    predicate="DERIVED_FROM",
                    object_type="baseflo_metadata",
                    object_id=f"baseflo:{field.name}",
                    evidence={
                        "field": field.name,
                        "system_column": True,
                    },
                )
            )
            continue
        session.add(
            _graph_edge(
                organization_id=data_source.organization_id,
                snapshot_id=snapshot.id,
                subject_type="canonical_field",
                subject_id=field_node,
                predicate="DERIVED_FROM",
                object_type="source_field",
                object_id=f"{data_source.kind}:{data_source.id}:{asset_key}:{source_column}",
                evidence={
                    "source_kind": data_source.kind,
                    "data_source_id": str(data_source.id),
                    "asset_key": asset_key,
                    "field": field.name,
                    "source_column": source_column,
                },
            )
        )

    return asset


async def _complete_canonical_snapshot(
    session: Any,
    snapshot: CanonicalSnapshot,
    *,
    status: str,
    asset_count: int,
    row_count: int,
    now: datetime,
    metadata: dict[str, Any] | None = None,
) -> None:
    snapshot.status = status
    snapshot.asset_count = asset_count
    snapshot.row_count = row_count
    snapshot.completed_at = now
    if metadata:
        snapshot.metadata_ = {**(snapshot.metadata_ or {}), **metadata}
