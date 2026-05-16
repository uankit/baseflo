"""Canonical data-plane context builder for agents."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from app.agent_plane.contracts import AssetEvidence, CanonicalContextPack, FieldEvidence
from app.agent_plane.store import load_context_pack

_MAX_CONTEXT_ASSETS = 60
_MAX_FIELDS_PER_ASSET = 80
_MAX_GRAPH_EDGES = 120
_MAX_MEMORIES = 30
_MAX_SAMPLE_VALUES = 4
_MAX_PREVIEW_ROWS = 2
_MAX_PREVIEW_COLUMNS = 12
_MAX_TEXT_CHARS = 96
_MAX_BUSINESS_ASSETS = 16
_MAX_BUSINESS_FIELDS_PER_ASSET = 12
_MAX_BUSINESS_GRAPH_EDGES = 40
_MAX_BUSINESS_MEMORIES = 8
_MAX_BUSINESS_SAMPLE_VALUES = 1


async def load_canonical_context(
    organization_id: UUID,
    *,
    snapshot_ids: list[UUID] | None = None,
    include_preview_rows: bool = True,
) -> CanonicalContextPack:
    """Load the compact canonical evidence all agents can safely consume."""
    return await load_context_pack(
        organization_id,
        snapshot_ids=snapshot_ids,
        include_preview_rows=include_preview_rows,
    )


def is_system_field(field: Any) -> bool:
    profile = field.profile if isinstance(field.profile, dict) else {}
    return bool(profile.get("system_column")) or str(field.name).startswith("_bf_")


def context_payload(context: CanonicalContextPack) -> dict[str, Any]:
    """Backward-compatible compact payload for model prompts."""
    return compact_context_payload(context)


def compact_context_payload(context: CanonicalContextPack) -> dict[str, Any]:
    """Return a bounded evidence pack for business-level agents.

    Agents need names, roles, row counts, type hints, candidate keys, and a few
    samples. They do not need full previews or profiler JSON. The canonical data
    and execution planes retain the complete data; this is only the prompt view.
    """
    return {
        "organization_id": context.organization_id,
        "snapshots": [
            {
                "snapshot_id": snapshot.snapshot_id,
                "data_source_id": snapshot.data_source_id,
                "mode": snapshot.mode,
                "status": snapshot.status,
                "asset_count": snapshot.asset_count,
                "row_count": snapshot.row_count,
            }
            for snapshot in context.snapshots[:_MAX_CONTEXT_ASSETS]
        ],
        "assets": [
            compact_asset_payload(asset, include_preview_rows=False)
            for asset in context.assets[:_MAX_CONTEXT_ASSETS]
        ],
        "graph_edges": [
            {
                "edge_id": edge.edge_id,
                "subject_type": edge.subject_type,
                "subject_id": edge.subject_id,
                "predicate": edge.predicate,
                "object_type": edge.object_type,
                "object_id": edge.object_id,
                "confidence": edge.confidence,
                "evidence": _compact_mapping(edge.evidence, max_items=8),
            }
            for edge in context.graph_edges[:_MAX_GRAPH_EDGES]
        ],
        "memories": [_compact_mapping(memory, max_items=12) for memory in context.memories[:_MAX_MEMORIES]],
        "limits": {
            "max_assets": _MAX_CONTEXT_ASSETS,
            "max_fields_per_asset": _MAX_FIELDS_PER_ASSET,
            "max_sample_values_per_field": _MAX_SAMPLE_VALUES,
            "note": "Prompt payload is compacted; full canonical data remains in the execution plane.",
        },
    }


def business_overview_payload(context: CanonicalContextPack) -> dict[str, Any]:
    """Tiny prompt view for BusinessUnderstander.

    This agent only decides business shape. It does not need relationship
    evidence, profiler reasons, previews, or every field in a wide workbook.
    Exact rows remain queryable through the execution plane.
    """
    return {
        "organization_id": context.organization_id,
        "summary": {
            "snapshot_count": len(context.snapshots),
            "asset_count": len(context.assets),
            "field_count": sum(len(asset.fields) for asset in context.assets),
            "row_count": sum(asset.row_count for asset in context.assets),
        },
        "snapshots": [
            {
                "snapshot_id": snapshot.snapshot_id,
                "asset_count": snapshot.asset_count,
                "row_count": snapshot.row_count,
            }
            for snapshot in context.snapshots[:_MAX_BUSINESS_ASSETS]
        ],
        "assets": [_business_asset_payload(asset) for asset in context.assets[:_MAX_BUSINESS_ASSETS]],
        "relationship_hints": [
            {
                "subject_id": edge.subject_id,
                "predicate": edge.predicate,
                "object_id": edge.object_id,
                "confidence": edge.confidence,
            }
            for edge in context.graph_edges[:_MAX_BUSINESS_GRAPH_EDGES]
        ],
        "memories": [
            {
                "kind": _compact_value(memory.get("kind")),
                "statement": _compact_value(memory.get("statement") or memory.get("value")),
                "confidence": memory.get("confidence"),
            }
            for memory in context.memories[:_MAX_BUSINESS_MEMORIES]
            if isinstance(memory, dict)
        ],
        "limits": {
            "field_selection": "Only the highest-signal fields per asset are shown.",
            "full_data_available_to_execution": True,
        },
    }


def _business_asset_payload(asset: AssetEvidence) -> dict[str, Any]:
    profile = _asset_profile_summary(asset.profile)
    return {
        "asset_id": asset.asset_id,
        "asset_key": asset.asset_key,
        "qualified_name": asset.qualified_name,
        "label": asset.label,
        "asset_type": asset.asset_type,
        "row_count": asset.row_count,
        "field_count": asset.field_count,
        "profile": {
            "quality_flags": profile.get("quality_flags", []),
            "primary_key_field_ids": profile.get("primary_key_field_ids", []),
            "label_field_ids": profile.get("label_field_ids", []),
            "measure_field_ids": profile.get("measure_field_ids", []),
            "timestamp_field_ids": profile.get("timestamp_field_ids", []),
        },
        "fields": [_business_field_payload(field) for field in _business_fields(asset)],
    }


def _business_fields(asset: AssetEvidence) -> list[FieldEvidence]:
    profile = _asset_profile_summary(asset.profile)
    priority_ids: list[str] = []
    for key in ("primary_key_field_ids", "label_field_ids", "measure_field_ids", "timestamp_field_ids"):
        priority_ids.extend(str(field_id) for field_id in profile.get(key, []) if field_id)
    fields_by_id = {field.field_id: field for field in asset.fields}
    selected: list[FieldEvidence] = []
    seen: set[str] = set()
    for field_id in priority_ids:
        field = fields_by_id.get(field_id)
        if field is not None and field.field_id not in seen:
            selected.append(field)
            seen.add(field.field_id)
        if len(selected) >= _MAX_BUSINESS_FIELDS_PER_ASSET:
            return selected
    for field in asset.fields:
        if field.field_id in seen:
            continue
        selected.append(field)
        seen.add(field.field_id)
        if len(selected) >= _MAX_BUSINESS_FIELDS_PER_ASSET:
            break
    return selected


def _business_field_payload(field: FieldEvidence) -> dict[str, Any]:
    profile = _field_profile_summary(field.profile)
    candidates = [
        candidate.get("kind")
        for candidate in profile.get("candidates", [])
        if isinstance(candidate, dict) and candidate.get("kind")
    ]
    return {
        "field_id": field.field_id,
        "name": field.name,
        "observed_type": field.observed_type,
        "nullable": field.nullable,
        "candidates": candidates[:3],
        "sample_values": [
            _compact_value(value)
            for value in field.sample_values[:_MAX_BUSINESS_SAMPLE_VALUES]
        ],
    }


def compact_asset_payload(
    asset: AssetEvidence,
    *,
    include_preview_rows: bool = False,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "asset_id": asset.asset_id,
        "data_source_id": asset.data_source_id,
        "snapshot_id": asset.snapshot_id,
        "asset_key": asset.asset_key,
        "qualified_name": asset.qualified_name,
        "storage_table": asset.storage_table,
        "label": asset.label,
        "asset_type": asset.asset_type,
        "row_count": asset.row_count,
        "field_count": asset.field_count,
        "metadata": _compact_mapping(asset.metadata, max_items=12),
        "profile": _asset_profile_summary(asset.profile),
        "fields": [
            compact_field_payload(field)
            for field in asset.fields[:_MAX_FIELDS_PER_ASSET]
        ],
    }
    if include_preview_rows:
        payload["preview_rows"] = _compact_preview_rows(asset.preview_rows)
    return payload


def compact_field_payload(field: FieldEvidence) -> dict[str, Any]:
    return {
        "field_id": field.field_id,
        "asset_id": field.asset_id,
        "name": field.name,
        "ordinal": field.ordinal,
        "storage_type": field.storage_type,
        "observed_type": field.observed_type,
        "nullable": field.nullable,
        "sample_values": [
            _compact_value(value)
            for value in field.sample_values[:_MAX_SAMPLE_VALUES]
        ],
        "profile": _field_profile_summary(field.profile),
    }


def compact_field_catalog(context: CanonicalContextPack) -> list[dict[str, Any]]:
    return [
        {
            "asset_id": asset.asset_id,
            "asset_label": asset.label,
            "asset_qualified_name": asset.qualified_name,
            **compact_field_payload(field),
        }
        for asset in context.assets[:_MAX_CONTEXT_ASSETS]
        for field in asset.fields[:_MAX_FIELDS_PER_ASSET]
    ]


def _asset_profile_summary(profile: dict[str, Any]) -> dict[str, Any]:
    profiler = _nested_dict(profile, "profiler")
    return {
        "row_count": profiler.get("row_count"),
        "density": profiler.get("density"),
        "quality_flags": _compact_list(profiler.get("quality_flags"), max_items=8),
        "primary_key_field_ids": _compact_list(profiler.get("primary_key_field_ids"), max_items=8),
        "label_field_ids": _compact_list(profiler.get("label_field_ids"), max_items=8),
        "measure_field_ids": _compact_list(profiler.get("measure_field_ids"), max_items=12),
        "timestamp_field_ids": _compact_list(profiler.get("timestamp_field_ids"), max_items=8),
        "freshness": _compact_mapping(profiler.get("freshness"), max_items=8),
    }


def _field_profile_summary(profile: dict[str, Any]) -> dict[str, Any]:
    profiler = _nested_dict(profile, "profiler")
    return {
        "row_count": profiler.get("row_count"),
        "non_null_rate": profiler.get("non_null_rate"),
        "distinct_count": profiler.get("distinct_count"),
        "uniqueness_rate": profiler.get("uniqueness_rate"),
        "min_value": _compact_value(profiler.get("min_value")),
        "max_value": _compact_value(profiler.get("max_value")),
        "candidates": [
            {
                "kind": _compact_value(candidate.get("kind")),
                "confidence": candidate.get("confidence"),
                "reasons": _compact_list(candidate.get("reasons"), max_items=3),
            }
            for candidate in _compact_list(profiler.get("candidates"), max_items=5)
            if isinstance(candidate, dict)
        ],
        "quality_flags": _compact_list(profiler.get("quality_flags"), max_items=5),
    }


def _compact_preview_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    compacted: list[dict[str, Any]] = []
    for row in rows[:_MAX_PREVIEW_ROWS]:
        next_row: dict[str, Any] = {}
        for index, (key, value) in enumerate(row.items()):
            if index >= _MAX_PREVIEW_COLUMNS:
                break
            next_row[key] = _compact_value(value)
        compacted.append(next_row)
    return compacted


def _compact_mapping(value: Any, *, max_items: int) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    result: dict[str, Any] = {}
    for index, (key, item) in enumerate(value.items()):
        if index >= max_items:
            break
        result[str(key)] = _compact_value(item)
    return result


def _nested_dict(value: dict[str, Any], key: str) -> dict[str, Any]:
    candidate = value.get(key)
    return candidate if isinstance(candidate, dict) else {}


def _compact_list(value: Any, *, max_items: int) -> list[Any]:
    if not isinstance(value, list):
        return []
    return [_compact_value(item) for item in value[:max_items]]


def _compact_value(value: Any) -> Any:
    if value is None or isinstance(value, bool | int | float):
        return value
    if isinstance(value, str):
        text = value.strip()
        return text if len(text) <= _MAX_TEXT_CHARS else f"{text[:_MAX_TEXT_CHARS]}..."
    if isinstance(value, list):
        return [_compact_value(item) for item in value[:_MAX_SAMPLE_VALUES]]
    if isinstance(value, dict):
        return _compact_mapping(value, max_items=8)
    text = str(value).strip()
    return text if len(text) <= _MAX_TEXT_CHARS else f"{text[:_MAX_TEXT_CHARS]}..."
