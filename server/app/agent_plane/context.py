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
_MAX_RELATIONSHIP_ASSETS = 60
_MAX_RELATIONSHIP_FIELDS = 240
_MAX_RELATIONSHIP_FIELDS_PER_ASSET = 10
_MAX_RELATIONSHIP_EDGES = 40
_RELATIONSHIP_FIELD_ROLES = {
    "primary_key",
    "foreign_key",
    "identifier",
    "label",
    "category",
    "status",
}


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


def relationship_mapper_payload(
    context: CanonicalContextPack,
    *,
    business_model: Any,
    asset_roles: list[Any],
    field_roles: list[Any],
) -> dict[str, Any]:
    """Relationship-focused prompt view for RelationshipMapper.

    The mapper needs business nouns, asset roles, semantic key fields, and
    deterministic relationship candidates. It does not need every field role or
    lineage edge in a wide workbook.
    """
    relationship_edges = _relationship_edges(context.graph_edges)
    edge_field_ids = _edge_field_ids(relationship_edges)
    return {
        "organization_id": context.organization_id,
        "business_model": _relationship_business_model_payload(business_model),
        "asset_roles": [
            _relationship_asset_role_payload(role)
            for role in asset_roles[:_MAX_RELATIONSHIP_ASSETS]
        ],
        "field_roles": _relationship_field_roles(field_roles, edge_field_ids=edge_field_ids),
        "graph_edges": [_relationship_edge_payload(edge) for edge in relationship_edges],
        "limits": {
            "field_selection": (
                "Only relationship-relevant fields are shown: keys, identifiers, labels, "
                "status/category fields, and fields referenced by deterministic relationship candidates."
            ),
            "edge_selection": "Only RELATIONSHIP_CANDIDATE graph edges are shown.",
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


def _relationship_business_model_payload(model: Any) -> dict[str, Any]:
    data = _model_payload(model)
    return {
        "paragraph": _compact_value(data.get("paragraph")),
        "business_kind": _compact_value(data.get("business_kind")),
        "primary_currency": _compact_value(data.get("primary_currency")),
        "entities": [
            {
                "name": _compact_value(entity.get("name")),
                "plural": _compact_value(entity.get("plural")),
                "primary_asset_id": _compact_value(entity.get("primary_asset_id")),
                "related_asset_ids": _compact_list(entity.get("related_asset_ids"), max_items=12),
            }
            for entity in _compact_list(data.get("entities"), max_items=30)
            if isinstance(entity, dict)
        ],
        "primary_kpis": [
            {
                "name": _compact_value(kpi.get("name")),
                "field_refs": _compact_list(kpi.get("field_refs"), max_items=8),
                "source_asset_ids": _compact_list(kpi.get("source_asset_ids"), max_items=8),
            }
            for kpi in _compact_list(data.get("primary_kpis"), max_items=20)
            if isinstance(kpi, dict)
        ],
        "useful_lenses": _compact_list(data.get("useful_lenses"), max_items=12),
        "confidence": data.get("confidence"),
    }


def _relationship_asset_role_payload(role: Any) -> dict[str, Any]:
    data = _model_payload(role)
    return {
        "asset_id": _compact_value(data.get("asset_id")),
        "role": _compact_value(data.get("role")),
        "entity_type": _compact_value(data.get("entity_type")),
        "label": _compact_value(data.get("label")),
        "tags": _compact_list(data.get("tags"), max_items=8),
        "confidence": data.get("confidence"),
    }


def _relationship_field_roles(
    roles: list[Any],
    *,
    edge_field_ids: set[str],
) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for role in roles:
        data = _model_payload(role)
        field_id = str(data.get("field_id") or "")
        asset_id = str(data.get("asset_id") or "")
        role_name = str(data.get("role") or "")
        semantic_type = str(data.get("semantic_type") or "")
        if not field_id or not asset_id:
            continue
        if (
            field_id not in edge_field_ids
            and role_name not in _RELATIONSHIP_FIELD_ROLES
            and not _looks_relationship_relevant(semantic_type, data.get("field_name"))
        ):
            continue
        grouped.setdefault(asset_id, []).append(
            {
                "field_id": _compact_value(field_id),
                "asset_id": _compact_value(asset_id),
                "field_name": _compact_value(data.get("field_name")),
                "semantic_type": _compact_value(semantic_type),
                "role": _compact_value(role_name),
                "entity_hint": _compact_value(data.get("entity_hint")),
                "measure_kind": _compact_value(data.get("measure_kind")),
                "confidence": data.get("confidence"),
            }
        )

    selected: list[dict[str, Any]] = []
    for asset_id in sorted(grouped):
        fields = sorted(
            grouped[asset_id],
            key=lambda item: (
                _relationship_role_rank(str(item.get("role") or "")),
                -(float(item.get("confidence") or 0.0)),
                str(item.get("field_name") or ""),
            ),
        )
        selected.extend(fields[:_MAX_RELATIONSHIP_FIELDS_PER_ASSET])
        if len(selected) >= _MAX_RELATIONSHIP_FIELDS:
            break
    return selected[:_MAX_RELATIONSHIP_FIELDS]


def _relationship_edges(edges: list[Any]) -> list[Any]:
    return sorted(
        [
            edge
            for edge in edges
            if _model_payload(edge).get("predicate") == "RELATIONSHIP_CANDIDATE"
        ],
        key=lambda edge: -(float(_model_payload(edge).get("confidence") or 0.0)),
    )[:_MAX_RELATIONSHIP_EDGES]


def _relationship_edge_payload(edge: Any) -> dict[str, Any]:
    data = _model_payload(edge)
    evidence_value = data.get("evidence")
    evidence = evidence_value if isinstance(evidence_value, dict) else {}
    return {
        "edge_id": _compact_value(data.get("edge_id")),
        "subject_id": _compact_value(data.get("subject_id")),
        "predicate": _compact_value(data.get("predicate")),
        "object_id": _compact_value(data.get("object_id")),
        "confidence": data.get("confidence"),
        "evidence": {
            "left_asset_id": _compact_value(evidence.get("left_asset_id")),
            "left_field_id": _compact_value(evidence.get("left_field_id")),
            "right_asset_id": _compact_value(evidence.get("right_asset_id")),
            "right_field_id": _compact_value(evidence.get("right_field_id")),
            "cardinality": _compact_value(evidence.get("cardinality")),
            "overlap_ratio": evidence.get("overlap_ratio"),
            "shared_value_count": evidence.get("shared_value_count"),
            "sample_shared_values": _compact_list(evidence.get("sample_shared_values"), max_items=3),
            "reasons": _compact_list(evidence.get("reasons"), max_items=3),
        },
    }


def _edge_field_ids(edges: list[Any]) -> set[str]:
    field_ids: set[str] = set()
    for edge in edges:
        data = _model_payload(edge)
        evidence_value = data.get("evidence")
        evidence = evidence_value if isinstance(evidence_value, dict) else {}
        for value in (
            evidence.get("left_field_id"),
            evidence.get("right_field_id"),
            str(data.get("subject_id") or "").removeprefix("canonical_field:"),
            str(data.get("object_id") or "").removeprefix("canonical_field:"),
        ):
            if value:
                field_ids.add(str(value))
    return field_ids


def _relationship_role_rank(role: str) -> int:
    ranks = {
        "primary_key": 0,
        "foreign_key": 1,
        "identifier": 2,
        "label": 3,
        "category": 4,
        "status": 5,
    }
    return ranks.get(role, 20)


def _looks_relationship_relevant(semantic_type: str, field_name: Any) -> bool:
    blob = f"{semantic_type} {field_name or ''}".lower()
    return any(token in blob for token in ("id", "key", "code", "name", "party", "customer", "vendor", "supplier"))


def _model_payload(value: Any) -> dict[str, Any]:
    if hasattr(value, "model_dump"):
        dumped = value.model_dump(mode="json")
        return dumped if isinstance(dumped, dict) else {}
    return value if isinstance(value, dict) else {}


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
