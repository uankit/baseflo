"""PostgresConnector — direct asyncpg implementation of the Connector protocol.

Per docs/40-features/CONN-PG.md.

Capabilities: introspect, read, write, paginate, stream.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import asyncpg

from app.connectors.base import (
    AuthCredentials,
    AuthKind,
    ConnectorCapabilities,
    ConnectorMetadata,
    ConnectorToken,
    HealthStatus,
    Row,
    SourceColumn,
    SourceMutation,
    SourceQuery,
    SourceSchema,
    SourceTable,
    Subscription,
    WriteResult,
)
from app.core.errors import BasefloError
from app.engines.schema.ddl.identifiers import (
    is_safe_identifier,
    quote_identifier,
)
from app.observability.logging import get_logger

logger = get_logger("connectors.postgres")


_INTROSPECT_TABLES_SQL = """
SELECT table_schema, table_name
FROM information_schema.tables
WHERE table_type = 'BASE TABLE'
  AND table_schema NOT IN ('pg_catalog', 'information_schema')
  AND ($1::text IS NULL OR table_schema = $1)
ORDER BY table_schema, table_name;
"""

_INTROSPECT_COLUMNS_SQL = """
SELECT
  column_name,
  data_type,
  is_nullable,
  column_default
FROM information_schema.columns
WHERE table_schema = $1 AND table_name = $2
ORDER BY ordinal_position;
"""

_INTROSPECT_PK_SQL = """
SELECT a.attname AS column_name
FROM pg_index i
JOIN pg_attribute a
  ON a.attrelid = i.indrelid
 AND a.attnum = ANY(i.indkey)
JOIN pg_class c ON c.oid = i.indrelid
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = $1 AND c.relname = $2 AND i.indisprimary;
"""

_ROW_COUNT_ESTIMATE_SQL = """
SELECT n_live_tup
FROM pg_stat_user_tables
WHERE schemaname = $1 AND relname = $2;
"""


class PostgresConnector:
    """Direct Postgres connection via asyncpg.

    Construction takes no required args so the registry can satisfy the
    no-args constructor check. The DSN arrives via `authenticate(...)`.
    """

    metadata: ConnectorMetadata = ConnectorMetadata(
        name="postgres",
        display_name="Postgres",
        version="1.0.0",
        protocol_version="1.0",
        auth_kind=AuthKind.DB_URL,
        capabilities=ConnectorCapabilities(
            can_introspect=True,
            can_read=True,
            can_write=True,
            can_subscribe_webhooks=False,
            supports_pagination=True,
            supports_streaming=True,
            requires_periodic_sync=False,
            write_back_canonical_only=True,
        ),
        required_scopes=["SELECT"],
        optional_scopes=["INSERT", "UPDATE", "DELETE", "TRIGGER", "LISTEN"],
    )

    # ----- auth -----

    async def authenticate(self, credentials: AuthCredentials) -> ConnectorToken:
        dsn_secret = credentials.payload.get("dsn")
        if dsn_secret is None:
            raise BasefloError(
                error_code="BF-CONN-PG-001",
                message="Postgres connector requires `dsn` in credentials.payload.",
                status_code=400,
            )
        dsn = dsn_secret.get_secret_value()

        try:
            conn = await asyncpg.connect(dsn=dsn, timeout=10.0)
        except (asyncpg.PostgresError, OSError, TimeoutError) as exc:
            # Surface a typed connector error for the API layer.
            raise BasefloError(
                error_code="BF-CONN-008",
                message=f"Postgres authentication failed: {exc}",
                status_code=400,
                cause=exc,
            ) from exc

        # We keep only the schema name the user is targeting (default 'public').
        target_schema = "public"
        try:
            row = await conn.fetchrow("SELECT current_database() AS db, current_user AS u")
            metadata: dict[str, Any] = {
                "schema": target_schema,
                "database": row["db"] if row else None,
                "user": row["u"] if row else None,
            }
        finally:
            await conn.close()

        # The token id is allocated by the Token Vault when persisted; here we
        # return a transient one. The vault re-stamps `token_id` on save.
        return ConnectorToken(
            connector_name=self.metadata.name,
            token_id=UUID("01970000-0000-7000-8000-000000000000"),
            metadata=metadata,
        )

    async def revoke(self, token: ConnectorToken) -> None:
        # Postgres has no provider-side revoke; the Token Vault's deletion
        # of the encrypted DSN is the revoke. Connector code is a no-op.
        _ = token

    # ----- introspection + sampling -----

    async def introspect_schema(self, token: ConnectorToken) -> SourceSchema:
        dsn = self._dsn_from_token(token)
        target_schema = token.metadata.get("schema") or "public"

        async with _connection(dsn) as conn:
            tables_rows = await conn.fetch(_INTROSPECT_TABLES_SQL, target_schema)
            tables: list[SourceTable] = []
            for tr in tables_rows:
                schema_name = tr["table_schema"]
                table_name = tr["table_name"]
                cols_rows = await conn.fetch(_INTROSPECT_COLUMNS_SQL, schema_name, table_name)
                pk_rows = await conn.fetch(_INTROSPECT_PK_SQL, schema_name, table_name)
                count_row = await conn.fetchrow(_ROW_COUNT_ESTIMATE_SQL, schema_name, table_name)
                pk = [r["column_name"] for r in pk_rows]
                columns = [
                    SourceColumn(
                        name=c["column_name"],
                        source_type=str(c["data_type"]),
                        nullable=(c["is_nullable"] == "YES"),
                        sample_values=[],
                        description=None,
                        primary_key_member=c["column_name"] in pk,
                    )
                    for c in cols_rows
                ]
                tables.append(
                    SourceTable(
                        name=table_name,
                        columns=columns,
                        estimated_row_count=int(count_row["n_live_tup"]) if count_row else None,
                        primary_key=pk,
                    )
                )

        return SourceSchema(
            tables=tables,
            introspected_at=datetime.now(UTC),
            notes=f"schema={target_schema}",
        )

    async def sample_rows(
        self, token: ConnectorToken, table: str, n: int
    ) -> list[Row]:
        if not is_safe_identifier(table):
            raise BasefloError(
                error_code="BF-CONN-PG-005",
                message=f"Refusing to sample from unsafe identifier: {table!r}",
                status_code=400,
            )
        n = max(1, min(int(n), 1000))
        dsn = self._dsn_from_token(token)
        async with _connection(dsn) as conn:
            sql = f"SELECT * FROM {quote_identifier(table)} LIMIT {n}"
            rows = await conn.fetch(sql)
        return [Row(values=dict(r)) for r in rows]

    # ----- read / write -----

    async def read(
        self, token: ConnectorToken, query: SourceQuery
    ) -> AsyncIterator[Row]:
        if not is_safe_identifier(query.table):
            raise BasefloError(
                error_code="BF-CONN-PG-005",
                message=f"Refusing to read from unsafe identifier: {query.table!r}",
                status_code=400,
            )
        dsn = self._dsn_from_token(token)
        sql = f"SELECT * FROM {quote_identifier(query.table)}"
        if query.limit:
            sql += f" LIMIT {int(query.limit)}"
        async with _connection(dsn) as conn:
            async with conn.transaction():
                async for record in conn.cursor(sql):
                    yield Row(values=dict(record))

    async def write(
        self, token: ConnectorToken, mutation: SourceMutation
    ) -> WriteResult:
        _ = (token, mutation)
        raise BasefloError(
            error_code="BF-CONN-PG-001",
            message="PostgresConnector.write is not available in v1.",
            status_code=501,
        )

    # ----- webhooks -----

    async def webhook_subscribe(
        self,
        token: ConnectorToken,
        events: list[str],
        callback_url: str,
    ) -> Subscription:
        _ = (token, events, callback_url)
        raise BasefloError(
            error_code="BF-CONN-002",
            message="PostgresConnector webhook support is not available in v1.",
            status_code=501,
        )

    async def webhook_unsubscribe(
        self, token: ConnectorToken, subscription: Subscription,
    ) -> None:
        _ = (token, subscription)
        raise BasefloError(
            error_code="BF-CONN-002",
            message="webhook_unsubscribe is unsupported on this connector.",
            status_code=501,
        )

    # ----- health -----

    async def health_check(self, token: ConnectorToken) -> HealthStatus:
        import time  # noqa: PLC0415

        dsn = self._dsn_from_token(token)
        started = time.perf_counter()
        try:
            async with _connection(dsn) as conn:
                await conn.fetchval("SELECT 1")
        except Exception as exc:  # noqa: BLE001 — health check intentionally swallows
            return HealthStatus(
                healthy=False,
                last_checked_at=datetime.now(UTC),
                latency_ms=int((time.perf_counter() - started) * 1000),
                notes=str(exc),
            )
        return HealthStatus(
            healthy=True,
            last_checked_at=datetime.now(UTC),
            latency_ms=int((time.perf_counter() - started) * 1000),
            notes=None,
        )

    # ----- internal -----

    def _dsn_from_token(self, token: ConnectorToken) -> str:
        """In production the Token Vault decrypts the DSN from `connector_tokens`.
        For local dev and tests the DSN may be supplied via `token.metadata['_dsn']`.
        """
        dsn = token.metadata.get("_dsn")
        if dsn is None:
            raise BasefloError(
                error_code="BF-CONN-PG-001",
                message=(
                    "PostgresConnector token missing decrypted DSN; the Token "
                    "Vault Service must populate `_dsn` in token.metadata at call time."
                ),
                status_code=500,
            )
        return str(dsn)


# ---------- helpers ----------


from contextlib import asynccontextmanager  # noqa: E402


@asynccontextmanager
async def _connection(dsn: str) -> AsyncIterator[asyncpg.Connection]:
    conn = await asyncpg.connect(dsn=dsn, timeout=10.0)
    try:
        yield conn
    finally:
        await conn.close()
