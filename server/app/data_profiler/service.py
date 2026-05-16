"""Deterministic profiler service for canonical data."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from app.data_plane.naming import quote_ident
from app.data_plane.storage import safe_query
from app.data_profiler.contracts import (
    AssetProfile,
    FieldProfile,
    ProfilerRunResult,
    RelationshipProfile,
)
from app.data_profiler.inference import candidate_confidence, has_candidate, profile_values
from app.data_profiler.relationships import is_join_candidate, relationship_profile
from app.data_profiler.store import (
    AssetRecord,
    FieldRecord,
    load_profiler_input,
    persist_profiler_output,
)

GENERATOR = "data_profiler_v1"
_MAX_PROFILE_VALUES = 5000
_MAX_RELATIONSHIP_FIELDS_PER_ASSET = 40


async def profile_organization(
    organization_id: UUID,
    *,
    snapshot_ids: list[UUID] | None = None,
) -> ProfilerRunResult:
    """Profile the latest canonical snapshots for an organization."""
    profiler_input = await load_profiler_input(
        organization_id,
        snapshot_ids=snapshot_ids,
        generator=GENERATOR,
    )
    snapshots = profiler_input.snapshots
    if not snapshots:
        return ProfilerRunResult(
            organization_id=str(organization_id),
            snapshot_ids=[],
            asset_count=0,
            field_count=0,
            relationship_count=0,
            quality_flags=["no_completed_snapshots"],
        )
    assets = profiler_input.assets
    fields = profiler_input.fields

    fields_by_asset: dict[UUID, list[FieldRecord]] = defaultdict(list)
    for field in fields:
        if not _is_system_field(field):
            fields_by_asset[field.asset_id].append(field)

    field_profiles_by_id: dict[UUID, FieldProfile] = {}
    asset_profiles: list[AssetProfile] = []
    for asset in assets:
        field_profiles = await _profile_asset_fields(
            organization_id,
            asset,
            fields_by_asset.get(asset.id, []),
        )
        for field_id, profile in field_profiles.items():
            field_profiles_by_id[field_id] = profile
        asset_profiles.append(_asset_profile(asset, list(field_profiles.values())))

    relationships = await _relationship_profiles(
        organization_id,
        assets,
        fields_by_asset,
        field_profiles_by_id,
    )
    await persist_profiler_output(
        organization_id,
        asset_profiles=asset_profiles,
        field_profiles_by_id=field_profiles_by_id,
        relationships=relationships,
        generator=GENERATOR,
    )

    return ProfilerRunResult(
        organization_id=str(organization_id),
        snapshot_ids=[str(snapshot.id) for snapshot in snapshots],
        asset_count=len(asset_profiles),
        field_count=len(field_profiles_by_id),
        relationship_count=len(relationships),
        quality_flags=_run_quality_flags(asset_profiles),
    )


async def _profile_asset_fields(
    organization_id: UUID,
    asset: AssetRecord,
    fields: list[FieldRecord],
) -> dict[UUID, FieldProfile]:
    async def _one(field: FieldRecord) -> tuple[UUID, FieldProfile]:
        values = await _field_values(organization_id, asset, field)
        profile = profile_values(
            field_id=str(field.id),
            asset_id=str(asset.id),
            name=field.name,
            values=values,
            row_count=asset.row_count,
        )
        return field.id, profile

    pairs = await asyncio.gather(*[_one(field) for field in fields])
    return dict(pairs)


async def _field_values(organization_id: UUID, asset: AssetRecord, field: FieldRecord) -> list[Any]:
    sql = (
        f"SELECT {quote_ident(field.name)} AS value "
        f"FROM {quote_ident(asset.storage_table)} "
        f"LIMIT {_MAX_PROFILE_VALUES}"
    )
    rows = await asyncio.to_thread(safe_query, organization_id, sql, max_rows=_MAX_PROFILE_VALUES)
    return [row.get("value") for row in rows]


def _asset_profile(asset: AssetRecord, field_profiles: list[FieldProfile]) -> AssetProfile:
    profiled_count = len(field_profiles)
    non_null_total = sum(profile.non_null_count for profile in field_profiles)
    possible_cells = max(asset.row_count * profiled_count, 1)
    quality_flags: list[str] = []
    if asset.row_count == 0:
        quality_flags.append("empty_asset")
    if profiled_count == 0:
        quality_flags.append("no_profiled_fields")
    if not any(has_candidate(profile, "primary_key") for profile in field_profiles) and asset.row_count > 0:
        quality_flags.append("no_primary_key_candidate")

    timestamp_profiles = [
        profile for profile in field_profiles if has_candidate(profile, "timestamp")
    ]
    freshness: dict[str, Any] = {}
    if timestamp_profiles:
        best = max(timestamp_profiles, key=lambda profile: candidate_confidence(profile, "timestamp"))
        freshness = {
            "field_id": best.field_id,
            "field_name": best.name,
            "max_value": best.max_value,
            "profiled_at": datetime.now(UTC).isoformat(),
        }

    return AssetProfile(
        asset_id=str(asset.id),
        qualified_name=asset.qualified_name,
        row_count=asset.row_count,
        field_count=asset.field_count,
        profiled_field_count=profiled_count,
        density=round(non_null_total / possible_cells, 4),
        primary_key_field_ids=[
            profile.field_id for profile in field_profiles if has_candidate(profile, "primary_key")
        ],
        label_field_ids=[
            profile.field_id for profile in field_profiles if has_candidate(profile, "label")
        ],
        measure_field_ids=[
            profile.field_id for profile in field_profiles if has_candidate(profile, "measure")
        ],
        timestamp_field_ids=[
            profile.field_id for profile in field_profiles if has_candidate(profile, "timestamp")
        ],
        freshness=freshness,
        quality_flags=quality_flags,
    )


async def _relationship_profiles(
    organization_id: UUID,
    assets: list[AssetRecord],
    fields_by_asset: dict[UUID, list[FieldRecord]],
    field_profiles_by_id: dict[UUID, FieldProfile],
) -> list[RelationshipProfile]:
    fields_for_asset: dict[UUID, list[FieldRecord]] = {}
    for asset in assets:
        candidates = [
            field
            for field in fields_by_asset.get(asset.id, [])
            if is_join_candidate(field_profiles_by_id[field.id])
        ]
        candidates.sort(
            key=lambda field: max(
                candidate_confidence(field_profiles_by_id[field.id], "primary_key"),
                candidate_confidence(field_profiles_by_id[field.id], "foreign_key"),
                candidate_confidence(field_profiles_by_id[field.id], "identifier"),
                candidate_confidence(field_profiles_by_id[field.id], "label"),
            ),
            reverse=True,
        )
        fields_for_asset[asset.id] = candidates[:_MAX_RELATIONSHIP_FIELDS_PER_ASSET]

    by_id = {asset.id: asset for asset in assets}
    relationships: list[RelationshipProfile] = []
    for index, left_asset in enumerate(assets):
        for right_asset in assets[index + 1:]:
            for left_field in fields_for_asset.get(left_asset.id, []):
                left_profile = field_profiles_by_id[left_field.id]
                for right_field in fields_for_asset.get(right_asset.id, []):
                    right_profile = field_profiles_by_id[right_field.id]
                    shared = await _shared_values(
                        organization_id,
                        by_id[left_field.asset_id],
                        left_field,
                        by_id[right_field.asset_id],
                        right_field,
                    )
                    profile = relationship_profile(
                        left=left_profile,
                        right=right_profile,
                        shared_values=shared,
                    )
                    if profile is not None:
                        relationships.append(profile)
    relationships.sort(key=lambda rel: rel.confidence, reverse=True)
    return relationships[:100]


async def _shared_values(
    organization_id: UUID,
    left_asset: AssetRecord,
    left_field: FieldRecord,
    right_asset: AssetRecord,
    right_field: FieldRecord,
) -> list[str]:
    left_expr = _normalized_sql(left_field.name)
    right_expr = _normalized_sql(right_field.name)
    sql = f"""
        WITH l AS (
            SELECT DISTINCT {left_expr} AS v
            FROM {quote_ident(left_asset.storage_table)}
            WHERE {left_expr} IS NOT NULL
            LIMIT {_MAX_PROFILE_VALUES}
        ),
        r AS (
            SELECT DISTINCT {right_expr} AS v
            FROM {quote_ident(right_asset.storage_table)}
            WHERE {right_expr} IS NOT NULL
            LIMIT {_MAX_PROFILE_VALUES}
        )
        SELECT l.v AS value
        FROM l INNER JOIN r USING (v)
        LIMIT 25
    """
    rows = await asyncio.to_thread(safe_query, organization_id, sql, max_rows=25)
    return [str(row["value"]) for row in rows if row.get("value") is not None]


def _normalized_sql(column_name: str) -> str:
    return f"NULLIF(lower(trim(CAST({quote_ident(column_name)} AS VARCHAR))), '')"


def _run_quality_flags(asset_profiles: list[AssetProfile]) -> list[str]:
    flags: list[str] = []
    if not asset_profiles:
        return ["no_assets"]
    if any("empty_asset" in profile.quality_flags for profile in asset_profiles):
        flags.append("has_empty_assets")
    if not any(profile.primary_key_field_ids for profile in asset_profiles):
        flags.append("no_primary_keys_detected")
    return flags


def _is_system_field(field: FieldRecord) -> bool:
    profile = field.profile if isinstance(field.profile, dict) else {}
    return bool(profile.get("system_column")) or field.name.startswith("_bf_")
