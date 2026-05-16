"""Source-to-canonical data-plane synchronization service."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from connectors import SourceQuery

from app.connector_runtime import ConnectionRecord, DataSourceRecord, get_source_instance
from app.data_plane.contracts import (
    CANONICAL_META_COLUMNS,
    DataPlaneAssetResult,
    DataPlaneSyncResult,
)
from app.data_plane.naming import canonical_storage_columns, qualified_name, unique_column_names
from app.data_plane.storage import CanonicalDuckDBWriter
from app.data_plane.store import (
    begin_source_snapshot,
    complete_source_snapshot,
    fail_source_snapshot,
    register_source_asset,
    update_source_asset_row_count,
)
from app.data_plane.values import duckdb_storage_value

_BATCH_SIZE = 500


async def sync_data_source(
    data_source: DataSourceRecord,
    connection: ConnectionRecord,
) -> DataPlaneSyncResult:
    """Build the canonical data plane for one connected data source.

    Input:
    - a persisted data-source record with discovered schema;
    - its authenticated connection record.

    Output:
    - DuckDB canonical tables for every discovered asset;
    - Postgres canonical catalog rows for snapshot/assets/fields;
    - graph edges for source->asset, snapshot->asset, asset->field, field lineage;
    - a typed `DataPlaneSyncResult` summarizing the completed plane build.
    """
    source = get_source_instance(data_source.kind)
    refreshed = await source.authenticate({"credentials": connection.credentials})
    credentials = refreshed["credentials"]

    schema = data_source.discovered_schema or {}
    now = datetime.now(UTC)
    result_assets: list[DataPlaneAssetResult] = []
    asset_count = 0
    total_rows = 0

    snapshot_id = await begin_source_snapshot(
        data_source,
        now=now,
        metadata={
            "source_kind": data_source.kind,
            "data_source_name": data_source.name,
            "connection_id": str(data_source.connection_id),
        },
    )

    writer = await CanonicalDuckDBWriter.open(data_source.organization_id)
    try:
        for table_info in schema.get("tables", []):
            asset_result = await _sync_table_asset(
                data_source=data_source,
                connection=connection,
                credentials=credentials,
                snapshot_id=snapshot_id,
                table_info=table_info,
                now=now,
                writer=writer,
            )
            if asset_result is None:
                continue
            result_assets.append(asset_result)
            asset_count += 1
            total_rows += asset_result.row_count
    except Exception as exc:
        await fail_source_snapshot(
            snapshot_id,
            asset_count=asset_count,
            row_count=total_rows,
            now=datetime.now(UTC),
            error=str(exc),
        )
        raise
    finally:
        await writer.close()

    await complete_source_snapshot(
        snapshot_id,
        status="completed",
        asset_count=asset_count,
        row_count=total_rows,
        now=datetime.now(UTC),
        metadata={"tables": [asset.qualified_name for asset in result_assets]},
    )

    return DataPlaneSyncResult(
        snapshot_id=snapshot_id,
        status="completed",
        assets=result_assets,
        row_count=total_rows,
    )


async def _sync_table_asset(
    *,
    data_source: DataSourceRecord,
    connection: ConnectionRecord,
    credentials: dict[str, Any],
    snapshot_id: UUID,
    table_info: dict[str, Any],
    now: datetime,
    writer: CanonicalDuckDBWriter,
) -> DataPlaneAssetResult | None:
    table_name = table_info["name"]
    label = table_info["label"]
    source_columns = unique_column_names([column["name"] for column in table_info["columns"]])
    if not source_columns:
        return None

    storage_columns, source_columns_by_storage = canonical_storage_columns(source_columns)
    qname = qualified_name(data_source.name, table_name)

    await writer.recreate_table(qname, storage_columns)

    asset_id = await register_source_asset(
        data_source,
        snapshot_id=snapshot_id,
        asset_key=table_name,
        qualified_name=qname,
        label=label,
        columns=storage_columns,
        row_count=0,
        metadata={
            **(table_info.get("metadata") or {}),
            "table_name": table_name,
            "label": label,
            "storage_format": "duckdb_canonical_table_v1",
            "system_columns": CANONICAL_META_COLUMNS,
            "source_columns_by_storage": source_columns_by_storage,
        },
        profile={"declared_columns": source_columns},
        source_columns_by_storage=source_columns_by_storage,
    )

    config = {**data_source.config, "credentials": credentials}
    query = SourceQuery(table=table_name, label=label)
    source = get_source_instance(data_source.kind)

    batch: list[list[Any]] = []
    total = 0
    async for row in source.read(config, query):
        record_number = total + len(batch) + 1
        source_record_id = row.source_id or str(record_number)
        metadata_values = {
            "_bf_record_id": f"{snapshot_id}:{qname}:{source_record_id}",
            "_bf_source_id": str(connection.id),
            "_bf_data_source_id": str(data_source.id),
            "_bf_snapshot_id": str(snapshot_id),
            "_bf_asset_id": str(asset_id),
            "_bf_ingested_at": now.isoformat(),
            "_bf_source_record_id": str(source_record_id),
        }
        data_values = {
            storage_column: (
                row.values.get(source_column)
                if source_column is not None
                else metadata_values[storage_column]
            )
            for storage_column, source_column in source_columns_by_storage.items()
        }
        batch.append([duckdb_storage_value(data_values.get(column)) for column in storage_columns])
        if len(batch) >= _BATCH_SIZE:
            total += await writer.insert_rows(qname, batch)
            batch = []
    if batch:
        total += await writer.insert_rows(qname, batch)

    await update_source_asset_row_count(asset_id, row_count=total)

    return DataPlaneAssetResult(
        asset_key=table_name,
        qualified_name=qname,
        label=label,
        row_count=total,
    )
