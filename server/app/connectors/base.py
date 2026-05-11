"""Connector Protocol + typed I/O models.

Per docs/40-features/CONN-FRAMEWORK.md §3.2.

Every input and output is a strongly-typed Pydantic model — no `dict[str, Any]`
on the public surface. The protocol is `runtime_checkable` so the registry
can verify conformance at registration time.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime
from enum import StrEnum
from typing import Any, Literal, Protocol, runtime_checkable
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, SecretStr


# ---------- Auth ----------


class AuthKind(StrEnum):
    OAUTH2 = "oauth2"
    API_KEY = "api_key"
    DB_URL = "db_url"
    FILE_UPLOAD = "file_upload"
    SERVICE_ACCOUNT = "service_account"
    CUSTOM = "custom"


class AuthCredentials(BaseModel):
    """Credentials supplied by the user during OAuth callback / API-key entry.

    Secrets are wrapped in `SecretStr`; the connector authenticates against
    the source and returns a typed `ConnectorToken`. After that, only the
    token id is referenced — never the raw payload again.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)
    payload: dict[str, SecretStr]
    redirect_uri: str | None = None


class ConnectorToken(BaseModel):
    """Reference to encrypted credentials stored in `connector_tokens`.

    The actual ciphertext lives in the DB (envelope-encrypted with the tenant
    KMS key per docs/40-features/SECURITY.md §3). Connectors receive the token
    id and metadata; the Token Vault decrypts on demand for outbound calls.
    """

    model_config = ConfigDict(extra="forbid")
    connector_name: str
    token_id: UUID
    metadata: dict[str, Any] = Field(default_factory=dict)
    """Non-secret connection info (e.g., shop domain, db host, sheet id)."""


# ---------- Capabilities + metadata ----------


class ConnectorCapabilities(BaseModel):
    """Declarative capability flags. The engine plans work around these.

    Calling a method whose flag is False raises BF-CONN-002 immediately.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")
    can_introspect: bool = True
    can_read: bool = True
    can_write: bool = False
    can_subscribe_webhooks: bool = False
    supports_pagination: bool = True
    supports_streaming: bool = False
    requires_periodic_sync: bool = True
    write_back_canonical_only: bool = True
    """When True, writes route to the EntityReconciler-decided authoritative source."""


class ConnectorMetadata(BaseModel):
    """Static metadata about a connector implementation."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    name: str = Field(pattern=r"^[a-z][a-z0-9_]*$", min_length=2, max_length=64)
    display_name: str = Field(min_length=1, max_length=120)
    version: str = Field(pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$")
    """Semver, e.g., '1.0.0'."""
    protocol_version: str = Field(default="1.0", pattern=r"^[0-9]+\.[0-9]+$")
    auth_kind: AuthKind
    capabilities: ConnectorCapabilities
    required_scopes: list[str] = Field(default_factory=list)
    optional_scopes: list[str] = Field(default_factory=list)
    icon_url: str | None = None
    docs_url: str | None = None


# ---------- Source schema introspection ----------


class SourceColumn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=255)
    source_type: str = Field(min_length=1, max_length=120)
    """Connector's native type string (e.g., 'integer', 'jsonb', 'varchar')."""
    nullable: bool = True
    sample_values: list[Any] = Field(default_factory=list, max_length=50)
    description: str | None = Field(default=None, max_length=2000)
    primary_key_member: bool = False


class SourceTable(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=255)
    columns: list[SourceColumn] = Field(min_length=1)
    estimated_row_count: int | None = Field(default=None, ge=0)
    primary_key: list[str] = Field(default_factory=list)
    description: str | None = None


class SourceSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tables: list[SourceTable] = Field(default_factory=list)
    introspected_at: datetime
    notes: str | None = Field(default=None, max_length=2000)


# ---------- Read / write ----------


class Row(BaseModel):
    """One record from a source. Values are typed loosely because connectors
    expose heterogeneous shapes; downstream `ColumnClassifier` produces the
    typed semantic interpretation.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)
    values: dict[str, Any]
    source_id: str | None = None


class SourceQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")
    table: str = Field(min_length=1, max_length=255)
    filter: dict[str, Any] | None = None
    sort: list[str] | None = None
    limit: int | None = Field(default=None, ge=1, le=100_000)
    cursor: str | None = None


class SourceMutation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    table: str = Field(min_length=1, max_length=255)
    op: Literal["create", "update", "delete"]
    where: dict[str, Any] | None = None
    values: dict[str, Any] | None = None


class WriteResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    success: bool
    affected_rows: int = Field(ge=0)
    new_id: str | None = None
    errors: list[str] = Field(default_factory=list)


# ---------- Webhooks + health ----------


class Subscription(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    events: list[str]
    callback_url: str
    expires_at: datetime | None = None


class HealthStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")
    healthy: bool
    last_checked_at: datetime
    latency_ms: int = Field(ge=0)
    notes: str | None = Field(default=None, max_length=2000)


# ---------- The Protocol ----------


@runtime_checkable
class Connector(Protocol):
    """Every connector implements this protocol.

    The framework checks conformance at registration time; runtime methods
    are duck-typed but each must return the typed model declared here.
    """

    metadata: ConnectorMetadata

    async def authenticate(self, credentials: AuthCredentials) -> ConnectorToken: ...

    async def revoke(self, token: ConnectorToken) -> None: ...

    async def introspect_schema(self, token: ConnectorToken) -> SourceSchema: ...

    async def sample_rows(
        self, token: ConnectorToken, table: str, n: int
    ) -> list[Row]: ...

    async def read(
        self, token: ConnectorToken, query: SourceQuery
    ) -> AsyncIterator[Row]: ...

    async def write(
        self, token: ConnectorToken, mutation: SourceMutation
    ) -> WriteResult: ...

    async def webhook_subscribe(
        self,
        token: ConnectorToken,
        events: list[str],
        callback_url: str,
    ) -> Subscription: ...

    async def webhook_unsubscribe(
        self, token: ConnectorToken, subscription: Subscription,
    ) -> None: ...

    async def health_check(self, token: ConnectorToken) -> HealthStatus: ...
