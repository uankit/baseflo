from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any, ClassVar

from pydantic import BaseModel

from connectors.types import AuthMethod, Capability, DataType


@dataclass(frozen=True, slots=True)
class ColumnSchema:
    name: str
    data_type: DataType
    sample_values: list[Any] = field(default_factory=list)
    nullable: bool = True


@dataclass(frozen=True, slots=True)
class TableSchema:
    name: str
    label: str
    columns: list[ColumnSchema]
    row_count: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class SourceSchema:
    tables: list[TableSchema]


@dataclass(frozen=True, slots=True)
class Row:
    values: dict[str, Any]
    source_id: str | None = None


@dataclass(frozen=True, slots=True)
class SourceQuery:
    table: str
    label: str | None = None
    limit: int | None = None
    since: str | None = None


@dataclass(frozen=True, slots=True)
class AvailableResource:
    """A resource selectable under an authenticated account.

    For Google Sheets: one spreadsheet from the user's Drive.
    For Stripe (future): not used (single-resource).
    """

    external_id: str
    name: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class AccountInfo:
    """Identity of the authenticated account behind a Connection's credentials."""

    external_id: str
    label: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class SourceSpec:
    """Declarative metadata for a Source. Safe to read without instantiating the runtime."""

    kind: str
    display_name: str
    description: str
    auth_method: AuthMethod
    capabilities: frozenset[Capability]
    config_schema: type[BaseModel]


class Source(ABC):
    """Every data source implements this interface.

    `spec` is a class-level attribute that declares metadata. The registry
    indexes sources by `spec.kind`.
    """

    spec: ClassVar[SourceSpec]

    @abstractmethod
    async def authenticate(self, config: dict[str, Any]) -> dict[str, Any]:
        """Validate credentials. May refresh expired tokens. Returns updated config."""

    @abstractmethod
    async def introspect(self, config: dict[str, Any]) -> SourceSchema:
        """Discover tables and columns without pulling all data."""

    @abstractmethod
    def read(
        self, config: dict[str, Any], query: SourceQuery,
    ) -> AsyncIterator[Row]:
        """Stream rows from the source. Implementations are typically async generators."""

    @abstractmethod
    async def health_check(self, config: dict[str, Any]) -> bool:
        """Return True if the source is reachable with the given config."""

    async def get_account_info(self, credentials: dict[str, Any]) -> AccountInfo:
        """Identity of the authenticated account. Override per connector."""
        raise NotImplementedError(
            f"{type(self).__name__} does not support account info introspection"
        )

    async def list_resources(
        self, credentials: dict[str, Any],
    ) -> list[AvailableResource]:
        """List resources available under these credentials.

        Connectors that support this must declare `Capability.LIST_RESOURCES`
        in their spec and override this method.
        """
        raise NotImplementedError(
            f"{type(self).__name__} does not support listing resources"
        )
