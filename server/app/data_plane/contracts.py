"""Typed contracts for the canonical data-plane stage.

The data plane is the first stage of the Baseflo pipeline:

    any source -> canonical storage + catalog + graph

It is deliberately source-neutral. It does not infer business meaning, build
insights, or decide what a user should do. It only preserves source data in a
stable shape that downstream intelligence can inspect safely and quickly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

CANONICAL_META_COLUMNS = [
    "_bf_record_id",
    "_bf_source_id",
    "_bf_data_source_id",
    "_bf_snapshot_id",
    "_bf_asset_id",
    "_bf_ingested_at",
    "_bf_source_record_id",
]


@dataclass(frozen=True, slots=True)
class CanonicalFieldSpec:
    name: str
    ordinal: int
    storage_type: str = "varchar"
    observed_type: str = "unknown"
    nullable: bool = True
    sample_values: list[Any] = field(default_factory=list)
    profile: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class DataPlaneAssetResult:
    asset_key: str
    qualified_name: str
    label: str
    row_count: int


@dataclass(frozen=True, slots=True)
class DataPlaneSyncResult:
    snapshot_id: UUID
    status: str
    assets: list[DataPlaneAssetResult]
    row_count: int

    @property
    def asset_count(self) -> int:
        return len(self.assets)

    def row_counts_by_table(self) -> dict[str, int]:
        return {asset.qualified_name: asset.row_count for asset in self.assets}
