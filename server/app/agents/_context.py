"""Helpers that turn database state into compact context blocks for agents.

Agents read structured data, not free text. These helpers format the shape
each agent expects: column profiles, sample rows, semantics, materialized
results. Keeping it in one place keeps prompts consistent.
"""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from app.db.models import (
    BusinessMemory,
    OperatingAsset,
    OperatingColumn,
    OperatingRelationship,
)


_SAMPLE_ROWS_PER_ASSET = 5
_SAMPLE_VALUES_PER_COLUMN = 5


def _truncate(value: Any, max_len: int = 80) -> str:
    text = "" if value is None else str(value)
    if len(text) <= max_len:
        return text
    return text[: max_len - 1] + "…"


def asset_block(asset: OperatingAsset, columns: list[OperatingColumn]) -> dict[str, Any]:
    """Compact JSON-able view of one asset for the AssetSemanticist."""
    return {
        "asset_id": str(asset.id),
        "qualified_name": asset.qualified_name,
        "source_name": asset.source_name,
        "table_label": asset.table_label,
        "row_count": asset.row_count,
        "column_count": asset.column_count,
        "raw_preview_rows": (
            asset.profile.get("source_metadata", {}).get("preview_rows", [])[:12]
            if isinstance(asset.profile, dict)
            and isinstance(asset.profile.get("source_metadata"), dict)
            else []
        ),
        "columns": [
            {
                "name": col.name,
                "observed_type": col.observed_type,
                "semantic_type": col.semantic_type,
                "null_rate": col.null_rate,
                "unique_count": col.unique_count,
                "non_null_count": col.profile.get("non_null_count") if isinstance(col.profile, dict) else None,
                "sample_values": [
                    _truncate(v, 60) for v in (col.sample_values or [])[:_SAMPLE_VALUES_PER_COLUMN]
                ],
            }
            for col in columns
        ],
    }


def relationship_candidates_block(
    relationships: list[OperatingRelationship],
    *,
    label_by_id: dict[UUID, str],
    qname_by_id: dict[UUID, str],
) -> list[dict[str, Any]]:
    """Raw value-overlap join candidates fed to RelationshipMapper."""
    return [
        {
            "left_asset": label_by_id.get(rel.left_asset_id),
            "left_table": qname_by_id.get(rel.left_asset_id),
            "left_column": rel.left_column,
            "right_asset": label_by_id.get(rel.right_asset_id),
            "right_table": qname_by_id.get(rel.right_asset_id),
            "right_column": rel.right_column,
            "relationship_kind": rel.relationship_kind,
            "value_overlap_confidence": rel.confidence,
            "evidence": rel.evidence or {},
        }
        for rel in relationships[:50]
    ]


def memory_block(memories: list[BusinessMemory]) -> list[dict[str, Any]]:
    return [
        {"key": m.key, "value": m.value, "source": m.source}
        for m in memories
        if m.status == "active"
    ]


def result_preview_block(rows: list[dict[str, Any]], *, limit: int = 12) -> list[dict[str, Any]]:
    """Materialized rows the Hypothesizer interprets."""
    return [
        {k: _truncate(v, 80) for k, v in row.items()}
        for row in rows[:limit]
    ]


def asset_summary(asset: OperatingAsset, role: dict[str, Any] | None) -> dict[str, Any]:
    """Compact asset descriptor used by cross-asset agents (mapper, lens, brief)."""
    summary: dict[str, Any] = {
        "asset_id": str(asset.id),
        "qualified_name": asset.qualified_name,
        "source_name": asset.source_name,
        "table_label": asset.table_label,
        "row_count": asset.row_count,
    }
    if role:
        summary["role"] = role.get("role")
        summary["entity_type"] = role.get("entity_type")
        summary["keys"] = role.get("keys") or []
        summary["time_dim"] = role.get("time_dim")
        summary["measures"] = role.get("measures") or []
        summary["tags"] = role.get("tags") or []
    return summary


def dumps(value: Any) -> str:
    """JSON-encode a context block compactly for the prompt body."""
    return json.dumps(value, default=str, ensure_ascii=False)
