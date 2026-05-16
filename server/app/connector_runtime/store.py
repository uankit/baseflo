"""Persistence boundary for connections and data-source records.

Connector runtime code deals in typed records, not ORM rows. This keeps source
adapters and data-plane services from carrying SQLAlchemy objects across package
boundaries.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select

from app.core.enums import ConnectionStatus, DataSourceStatus
from app.db.models import Connection, DataSource
from app.db.session import open_session


@dataclass(frozen=True)
class ConnectionRecord:
    id: UUID
    organization_id: UUID
    kind: str
    external_account_id: str
    external_account_label: str
    credentials: dict[str, Any]
    status: ConnectionStatus
    last_error: str | None
    created_by_user_id: UUID


@dataclass(frozen=True)
class DataSourceRecord:
    id: UUID
    organization_id: UUID
    connection_id: UUID
    kind: str
    name: str
    config: dict[str, Any]
    discovered_schema: dict[str, Any] | None
    status: DataSourceStatus
    last_synced_at: datetime | None
    last_error: str | None
    created_by_user_id: UUID
    created_at: datetime


def connection_record(connection: Connection) -> ConnectionRecord:
    return ConnectionRecord(
        id=connection.id,
        organization_id=connection.organization_id,
        kind=connection.kind,
        external_account_id=connection.external_account_id,
        external_account_label=connection.external_account_label,
        credentials=dict(connection.credentials or {}),
        status=connection.status,
        last_error=connection.last_error,
        created_by_user_id=connection.created_by_user_id,
    )


def data_source_record(data_source: DataSource) -> DataSourceRecord:
    return DataSourceRecord(
        id=data_source.id,
        organization_id=data_source.organization_id,
        connection_id=data_source.connection_id,
        kind=data_source.kind,
        name=data_source.name,
        config=dict(data_source.config or {}),
        discovered_schema=data_source.discovered_schema,
        status=data_source.status,
        last_synced_at=data_source.last_synced_at,
        last_error=data_source.last_error,
        created_by_user_id=data_source.created_by_user_id,
        created_at=data_source.created_at,
    )


async def load_connection(
    connection_id: UUID,
    *,
    organization_id: UUID | None = None,
) -> ConnectionRecord | None:
    async with open_session() as session:
        connection = await session.get(Connection, connection_id)
        if connection is None:
            return None
        if organization_id is not None and connection.organization_id != organization_id:
            return None
        return connection_record(connection)


async def update_connection_credentials(connection_id: UUID, credentials: dict[str, Any]) -> None:
    async with open_session() as session:
        connection = await session.get(Connection, connection_id)
        if connection is not None:
            connection.credentials = credentials


async def upsert_oauth_connection(
    *,
    organization_id: UUID,
    user_id: UUID,
    kind: str,
    external_account_id: str,
    external_account_label: str,
    credentials: dict[str, Any],
) -> UUID:
    async with open_session() as session:
        result = await session.execute(
            select(Connection).where(
                Connection.organization_id == organization_id,
                Connection.kind == kind,
                Connection.external_account_id == external_account_id,
            )
        )
        connection = result.scalar_one_or_none()
        if connection is not None:
            connection.credentials = credentials
            connection.status = ConnectionStatus.ACTIVE
            connection.last_error = None
            connection.external_account_label = external_account_label
        else:
            connection = Connection(
                organization_id=organization_id,
                kind=kind,
                external_account_id=external_account_id,
                external_account_label=external_account_label,
                credentials=credentials,
                status=ConnectionStatus.ACTIVE,
                created_by_user_id=user_id,
            )
            session.add(connection)
            await session.flush()
        return connection.id


async def create_data_source(
    *,
    organization_id: UUID,
    connection_id: UUID,
    kind: str,
    name: str,
    config: dict[str, Any],
    created_by_user_id: UUID,
) -> DataSourceRecord:
    async with open_session() as session:
        data_source = DataSource(
            organization_id=organization_id,
            connection_id=connection_id,
            kind=kind,
            name=name,
            config=config,
            status=DataSourceStatus.ACTIVE,
            created_by_user_id=created_by_user_id,
        )
        session.add(data_source)
        await session.flush()
        return data_source_record(data_source)


async def update_data_source_introspection(
    data_source_id: UUID,
    *,
    discovered_schema: dict[str, Any] | None,
    status: DataSourceStatus,
    last_error: str | None = None,
) -> None:
    async with open_session() as session:
        data_source = await session.get(DataSource, data_source_id)
        if data_source is not None:
            data_source.discovered_schema = discovered_schema
            data_source.status = status
            data_source.last_error = last_error


async def load_data_source(
    data_source_id: UUID,
    *,
    organization_id: UUID | None = None,
) -> DataSourceRecord | None:
    async with open_session() as session:
        data_source = await session.get(DataSource, data_source_id)
        if data_source is None:
            return None
        if organization_id is not None and data_source.organization_id != organization_id:
            return None
        return data_source_record(data_source)


async def load_data_sources_by_ids(data_source_ids: list[UUID]) -> list[DataSourceRecord]:
    if not data_source_ids:
        return []
    async with open_session() as session:
        result = await session.execute(
            select(DataSource).where(DataSource.id.in_(data_source_ids))
        )
        return [data_source_record(data_source) for data_source in result.scalars().all()]


async def list_data_sources(organization_id: UUID) -> list[DataSourceRecord]:
    async with open_session() as session:
        result = await session.execute(
            select(DataSource)
            .where(DataSource.organization_id == organization_id)
            .order_by(DataSource.created_at.desc())
        )
        return [data_source_record(data_source) for data_source in result.scalars().all()]


async def load_source_with_connection(
    data_source_id: UUID,
    *,
    organization_id: UUID | None = None,
) -> tuple[DataSourceRecord, ConnectionRecord] | None:
    async with open_session() as session:
        data_source = await session.get(DataSource, data_source_id)
        if data_source is None:
            return None
        if organization_id is not None and data_source.organization_id != organization_id:
            return None
        connection = await session.get(Connection, data_source.connection_id)
        if connection is None:
            return None
        return data_source_record(data_source), connection_record(connection)


async def mark_data_source_synced(data_source_id: UUID, *, synced_at: datetime) -> None:
    async with open_session() as session:
        data_source = await session.get(DataSource, data_source_id)
        if data_source is not None:
            data_source.status = DataSourceStatus.ACTIVE
            data_source.last_error = None
            data_source.last_synced_at = synced_at


async def mark_data_source_error(data_source_id: UUID, *, error: str) -> None:
    async with open_session() as session:
        data_source = await session.get(DataSource, data_source_id)
        if data_source is not None:
            data_source.status = DataSourceStatus.ERROR
            data_source.last_error = error
