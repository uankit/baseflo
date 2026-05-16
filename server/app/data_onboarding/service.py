"""Data-source onboarding service.

Routes should stay thin. This service owns the source-neutral lifecycle after a
user selects resources from a connection:

1. authenticate/refresh credentials,
2. create DataSource records,
3. introspect connector schemas,
4. sync canonical data-plane assets,
5. refresh deterministic profiles when at least one source synced.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from pydantic_core import to_jsonable_python

from app.connector_runtime.adapters import ResourceLike
from app.connector_runtime.factory import get_source_instance
from app.connector_runtime.resources import resource_config_for
from app.connector_runtime.store import (
    DataSourceRecord,
    create_data_source,
    load_connection,
    load_data_sources_by_ids,
    load_source_with_connection,
    mark_data_source_error,
    mark_data_source_synced,
    update_connection_credentials,
    update_data_source_introspection,
)
from app.core.enums import DataSourceStatus
from app.core.errors import NotFoundError
from app.data_plane import sync_data_source
from app.data_profiler import profile_organization


@dataclass(frozen=True, slots=True)
class DataSourceOnboardingResult:
    data_sources: list[DataSourceRecord]
    synced_any: bool


class DataSourceOnboardingService:
    """Create and canonicalize selected connector resources."""

    async def create_sources(
        self,
        *,
        organization_id: UUID,
        user_id: UUID,
        connection_id: UUID,
        resources: Sequence[ResourceLike],
    ) -> DataSourceOnboardingResult:
        connection = await load_connection(connection_id, organization_id=organization_id)
        if connection is None:
            raise NotFoundError(
                message="Connection not found",
                code="CONNECTION_NOT_FOUND",
                status_hint=404,
            )

        kind = connection.kind
        source = get_source_instance(kind)
        credentials = dict(connection.credentials)
        refreshed = await source.authenticate({"credentials": credentials})
        new_credentials = refreshed["credentials"]
        if new_credentials != credentials:
            await update_connection_credentials(connection_id, new_credentials)

        created_ids = await self._create_and_introspect_sources(
            organization_id=organization_id,
            user_id=user_id,
            connection_id=connection_id,
            kind=kind,
            source=source,
            credentials=new_credentials,
            resources=resources,
        )
        synced_any = await self._sync_active_sources(
            organization_id=organization_id,
            data_source_ids=created_ids,
        )
        if synced_any:
            await profile_organization(organization_id)

        return DataSourceOnboardingResult(
            data_sources=await load_data_sources_by_ids(created_ids),
            synced_any=synced_any,
        )

    async def _create_and_introspect_sources(
        self,
        *,
        organization_id: UUID,
        user_id: UUID,
        connection_id: UUID,
        kind: str,
        source: Any,
        credentials: dict[str, Any],
        resources: Sequence[ResourceLike],
    ) -> list[UUID]:
        created_ids: list[UUID] = []
        for resource in resources:
            data_source = await create_data_source(
                organization_id=organization_id,
                connection_id=connection_id,
                kind=kind,
                name=resource.name,
                config=resource_config_for(kind, resource),
                created_by_user_id=user_id,
            )
            try:
                schema = await source.introspect({**data_source.config, "credentials": credentials})
                await update_data_source_introspection(
                    data_source.id,
                    discovered_schema=_schema_to_dict(schema),
                    status=DataSourceStatus.ACTIVE,
                )
            except Exception as exc:
                await update_data_source_introspection(
                    data_source.id,
                    discovered_schema=None,
                    status=DataSourceStatus.ERROR,
                    last_error=f"introspect failed: {exc}",
                )
            created_ids.append(data_source.id)
        return created_ids

    async def _sync_active_sources(
        self,
        *,
        organization_id: UUID,
        data_source_ids: list[UUID],
    ) -> bool:
        synced_any = False
        now = datetime.now(UTC)
        for data_source_id in data_source_ids:
            pair = await load_source_with_connection(
                data_source_id,
                organization_id=organization_id,
            )
            if pair is None:
                continue
            data_source, connection = pair
            if data_source.status != DataSourceStatus.ACTIVE:
                continue
            try:
                await sync_data_source(data_source, connection)
                await mark_data_source_synced(data_source.id, synced_at=now)
                synced_any = True
            except Exception as exc:
                await mark_data_source_error(
                    data_source.id,
                    error=f"data-plane sync failed: {exc}",
                )
        return synced_any


def _schema_to_dict(schema: Any) -> dict[str, Any]:
    """Convert connector SourceSchema dataclass trees into JSON-safe dicts."""
    return {
        "tables": [
            {
                "name": table.name,
                "label": table.label,
                "row_count": table.row_count,
                "metadata": to_jsonable_python(table.metadata),
                "columns": [
                    {
                        "name": column.name,
                        "data_type": column.data_type.value,
                        "sample_values": to_jsonable_python(list(column.sample_values)),
                        "nullable": column.nullable,
                    }
                    for column in table.columns
                ],
            }
            for table in schema.tables
        ]
    }
