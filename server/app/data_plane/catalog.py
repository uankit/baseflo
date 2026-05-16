"""Pure canonical catalog naming helpers."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID


def node_id(kind: str, value: str | UUID) -> str:
    return f"{kind}:{value}"


def snapshot_key(data_source_id: UUID, now: datetime) -> str:
    stamp = now.astimezone(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    return f"source:{data_source_id}:snapshot:{stamp}"


def asset_type_from_metadata(metadata: dict[str, Any]) -> str:
    if metadata.get("asset_type"):
        return str(metadata["asset_type"])
    if str(metadata.get("format") or "").startswith("canonical_grid"):
        return "grid"
    return "records"
