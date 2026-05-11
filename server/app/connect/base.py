"""Connector protocol — every source implements this."""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True, slots=True)
class ColumnSchema:
    name: str
    data_type: str  # inferred: text, number, date, boolean, money, etc.
    sample_values: list[Any] = field(default_factory=list)
    nullable: bool = True


@dataclass(frozen=True, slots=True)
class TableSchema:
    name: str
    label: str
    columns: list[ColumnSchema]
    row_count: int | None = None


@dataclass(frozen=True, slots=True)
class SourceSchema:
    tables: list[TableSchema]


@dataclass(frozen=True, slots=True)
class Row:
    values: dict[str, Any]
    source_id: str | None = None  # unique identifier within source


@dataclass(frozen=True, slots=True)
class SourceQuery:
    table: str
    limit: int | None = None
    since: str | None = None  # incremental sync cursor


class Connector(Protocol):
    """Every data source implements this interface."""

    kind: str

    async def authenticate(self, config: dict[str, Any]) -> dict[str, Any]:
        """Validate credentials and return enriched token/config."""
        ...

    async def introspect(self, config: dict[str, Any]) -> SourceSchema:
        """Return schema (tables, columns, types) without full data."""
        ...

    async def read(
        self, config: dict[str, Any], query: SourceQuery,
    ) -> AsyncIterator[Row]:
        """Stream rows from source."""
        ...

    async def health_check(self, config: dict[str, Any]) -> bool:
        """Return True if source is reachable."""
        ...
