"""Persistence boundary for deterministic profiling."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import delete, or_, select

from app.data_plane.catalog import node_id
from app.data_profiler.contracts import AssetProfile, FieldProfile, RelationshipProfile
from app.db.models import CanonicalAsset, CanonicalField, CanonicalSnapshot, DataGraphEdge
from app.db.session import open_session


@dataclass(frozen=True)
class SnapshotRecord:
    id: UUID
    data_source_id: UUID


@dataclass(frozen=True)
class AssetRecord:
    id: UUID
    snapshot_id: UUID | None
    qualified_name: str
    storage_table: str
    row_count: int
    field_count: int


@dataclass(frozen=True)
class FieldRecord:
    id: UUID
    asset_id: UUID
    name: str
    ordinal: int
    profile: dict[str, Any]


@dataclass(frozen=True)
class ProfilerInput:
    snapshots: list[SnapshotRecord]
    assets: list[AssetRecord]
    fields: list[FieldRecord]


async def load_profiler_input(
    organization_id: UUID,
    *,
    snapshot_ids: list[UUID] | None,
    generator: str,
) -> ProfilerInput:
    async with open_session() as session:
        snapshots = await _load_snapshots(session, organization_id, snapshot_ids=snapshot_ids)
        if not snapshots:
            return ProfilerInput(snapshots=[], assets=[], fields=[])

        snapshot_id_values = [snapshot.id for snapshot in snapshots]
        assets = list(
            (
                await session.execute(
                    select(CanonicalAsset)
                    .where(
                        CanonicalAsset.organization_id == organization_id,
                        CanonicalAsset.snapshot_id.in_(snapshot_id_values),
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

        await session.execute(
            delete(DataGraphEdge).where(
                DataGraphEdge.organization_id == organization_id,
                DataGraphEdge.created_by == generator,
                or_(
                    DataGraphEdge.snapshot_id.in_(snapshot_id_values),
                    DataGraphEdge.snapshot_id.is_(None),
                ),
            )
        )

        return ProfilerInput(
            snapshots=[
                SnapshotRecord(id=snapshot.id, data_source_id=snapshot.data_source_id)
                for snapshot in snapshots
            ],
            assets=[
                AssetRecord(
                    id=asset.id,
                    snapshot_id=asset.snapshot_id,
                    qualified_name=asset.qualified_name,
                    storage_table=asset.storage_table,
                    row_count=asset.row_count,
                    field_count=asset.field_count,
                )
                for asset in assets
            ],
            fields=[
                FieldRecord(
                    id=field.id,
                    asset_id=field.asset_id,
                    name=field.name,
                    ordinal=field.ordinal,
                    profile=field.profile or {},
                )
                for field in fields
            ],
        )


async def persist_profiler_output(
    organization_id: UUID,
    *,
    asset_profiles: list[AssetProfile],
    field_profiles_by_id: dict[UUID, FieldProfile],
    relationships: list[RelationshipProfile],
    generator: str,
) -> None:
    async with open_session() as session:
        for field_id, field_profile in field_profiles_by_id.items():
            field = await session.get(CanonicalField, field_id)
            if field is None:
                continue
            field.observed_type = field_profile.observed_type
            field.nullable = field_profile.non_null_count < field_profile.row_count
            field.sample_values = field_profile.sample_values
            field.profile = {
                **(field.profile or {}),
                "profiler": field_profile.model_dump(mode="json"),
                "profiler_version": generator,
            }

        asset_snapshot_id: dict[str, UUID | None] = {}
        for asset_profile in asset_profiles:
            asset = await session.get(CanonicalAsset, UUID(asset_profile.asset_id))
            if asset is None:
                continue
            asset.profile = {
                **(asset.profile or {}),
                "profiler": asset_profile.model_dump(mode="json"),
                "profiler_version": generator,
            }
            asset_snapshot_id[asset_profile.asset_id] = asset.snapshot_id

        for relationship in relationships:
            snapshot_id = asset_snapshot_id.get(relationship.left_asset_id)
            if snapshot_id != asset_snapshot_id.get(relationship.right_asset_id):
                snapshot_id = None
            session.add(
                DataGraphEdge(
                    organization_id=organization_id,
                    snapshot_id=snapshot_id,
                    subject_type="canonical_field",
                    subject_id=node_id("canonical_field", relationship.left_field_id),
                    predicate=relationship.predicate,
                    object_type="canonical_field",
                    object_id=node_id("canonical_field", relationship.right_field_id),
                    confidence=relationship.confidence,
                    created_by=generator,
                    evidence=relationship.model_dump(mode="json"),
                )
            )


async def _load_snapshots(
    session: Any,
    organization_id: UUID,
    *,
    snapshot_ids: list[UUID] | None,
) -> list[CanonicalSnapshot]:
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
    completed = list(
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
    for snapshot in completed:
        latest_by_source.setdefault(snapshot.data_source_id, snapshot)
    return list(latest_by_source.values())
