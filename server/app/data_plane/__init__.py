"""Canonical data-plane package.

This package is the first independent stage in the Baseflo workflow. It accepts
any connected source after connector introspection and prepares Baseflo's own
canonical data plane: physical DuckDB tables, Postgres catalog rows, and graph
lineage. Downstream intelligence should consume this plane, not raw connectors.
"""

from app.data_plane.contracts import (
    CANONICAL_META_COLUMNS,
    CanonicalFieldSpec,
    DataPlaneAssetResult,
    DataPlaneSyncResult,
)
from app.data_plane.naming import canonical_storage_columns, qualified_name, unique_column_names
from app.data_plane.service import sync_data_source
from app.data_plane.storage import list_canonical_tables, safe_query
from app.data_plane.values import duckdb_storage_value

__all__ = [
    "CANONICAL_META_COLUMNS",
    "CanonicalFieldSpec",
    "DataPlaneAssetResult",
    "DataPlaneSyncResult",
    "canonical_storage_columns",
    "duckdb_storage_value",
    "list_canonical_tables",
    "qualified_name",
    "safe_query",
    "sync_data_source",
    "unique_column_names",
]
