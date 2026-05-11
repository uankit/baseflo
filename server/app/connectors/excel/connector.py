"""ExcelConnector — `.xlsx` file-upload connector.

Per docs/40-features/CONN-EXCEL.md. Sibling of `CSVConnector`; uses the
shared file-upload pattern (path token → re-open per call) and the same
primitive type-inference helpers via `openpyxl`-driven introspection.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from app.connectors.base import (
    AuthCredentials,
    AuthKind,
    ConnectorCapabilities,
    ConnectorMetadata,
    ConnectorToken,
    HealthStatus,
    Row,
    SourceMutation,
    SourceQuery,
    SourceSchema,
    Subscription,
    WriteResult,
)
from app.connectors.excel.parser import (
    introspect_workbook,
    iter_sheet_rows,
    sanitize_sheet_name,
)
from app.core.errors import BasefloError
from app.observability.logging import get_logger


logger = get_logger("connectors.excel")


class ExcelConnector:
    """One uploaded workbook → N source tables (one per sheet).

    The token's metadata carries:
      - `path`: filesystem path to the uploaded `.xlsx`.
      - `has_header`: optional `"true"` / `"false"` override.
    """

    metadata: ConnectorMetadata = ConnectorMetadata(
        name="excel",
        display_name="Excel Upload",
        version="1.0.0",
        protocol_version="1.0",
        auth_kind=AuthKind.FILE_UPLOAD,
        capabilities=ConnectorCapabilities(
            can_introspect=True,
            can_read=True,
            can_write=False,
            can_subscribe_webhooks=False,
            supports_pagination=True,
            supports_streaming=True,
            requires_periodic_sync=False,
            write_back_canonical_only=False,
        ),
    )

    # ----- auth -----

    async def authenticate(self, credentials: AuthCredentials) -> ConnectorToken:
        path_secret = credentials.payload.get("path")
        if path_secret is None:
            raise BasefloError(
                error_code="BF-CONN-EXCEL-001",
                message="ExcelConnector requires `path` in credentials.payload.",
                status_code=400,
            )
        path = Path(path_secret.get_secret_value())
        if not path.is_file():
            raise BasefloError(
                error_code="BF-CONN-EXCEL-001",
                message=f"Excel file not found at path: {path}",
                status_code=400,
            )

        metadata: dict[str, str] = {"path": str(path)}
        has_header = credentials.payload.get("has_header")
        if has_header is not None:
            literal = has_header.get_secret_value().strip().lower()
            if literal not in {"true", "false"}:
                raise BasefloError(
                    error_code="BF-CONN-EXCEL-001",
                    message=(
                        f"ExcelConnector `has_header` must be 'true' or 'false'; "
                        f"got {literal!r}."
                    ),
                    status_code=400,
                )
            metadata["has_header"] = literal

        # Validate by attempting to introspect now (fail-fast on bad uploads).
        introspect_workbook(path, has_header=self._parse_has_header(metadata))

        return ConnectorToken(
            connector_name=self.metadata.name,
            token_id=UUID("01970000-0000-7000-8000-000000000001"),
            metadata=metadata,
        )

    async def revoke(self, token: ConnectorToken) -> None:
        # Files persist after revocation; the Token Vault deletes the upload.
        _ = token

    # ----- introspection + sampling -----

    async def introspect_schema(self, token: ConnectorToken) -> SourceSchema:
        path = self._path_from_token(token)
        tables = introspect_workbook(
            path, has_header=self._parse_has_header(token.metadata)
        )
        return SourceSchema(
            tables=tables,
            introspected_at=datetime.now(UTC),
            notes=f"file={path.name}, sheets={len(tables)}",
        )

    async def sample_rows(
        self, token: ConnectorToken, table: str, n: int
    ) -> list[Row]:
        path = self._path_from_token(token)
        n = max(1, min(int(n), 1000))
        rows = list(
            iter_sheet_rows(
                path,
                sheet_table_name=sanitize_sheet_name(table),
                has_header=self._parse_has_header(token.metadata),
                max_rows=n,
            )
        )
        return [Row(values=r) for r in rows]

    async def read(
        self, token: ConnectorToken, query: SourceQuery
    ) -> AsyncIterator[Row]:
        return self._stream(token, query)

    async def _stream(
        self, token: ConnectorToken, query: SourceQuery
    ) -> AsyncIterator[Row]:
        path = self._path_from_token(token)
        for raw in iter_sheet_rows(
            path,
            sheet_table_name=sanitize_sheet_name(query.table),
            has_header=self._parse_has_header(token.metadata),
            max_rows=query.limit,
        ):
            yield Row(values=raw)

    # ----- writes / webhooks (unsupported by capability) -----

    async def write(
        self, token: ConnectorToken, mutation: SourceMutation
    ) -> WriteResult:
        _ = (token, mutation)
        raise BasefloError(
            error_code="BF-CONN-002",
            message="ExcelConnector is read-only; refresh by uploading a new file.",
            status_code=501,
        )

    async def webhook_subscribe(
        self,
        token: ConnectorToken,
        events: list[str],
        callback_url: str,
    ) -> Subscription:
        _ = (token, events, callback_url)
        raise BasefloError(
            error_code="BF-CONN-002",
            message="ExcelConnector does not support webhooks.",
            status_code=501,
        )

    async def webhook_unsubscribe(
        self, token: ConnectorToken, subscription: Subscription,
    ) -> None:
        _ = (token, subscription)
        raise BasefloError(
            error_code="BF-CONN-002",
            message="ExcelConnector does not support webhooks.",
            status_code=501,
        )

    # ----- health -----

    async def health_check(self, token: ConnectorToken) -> HealthStatus:
        path = self._path_from_token(token)
        ok = path.is_file()
        return HealthStatus(
            healthy=ok,
            last_checked_at=datetime.now(UTC),
            latency_ms=0,
            notes=None if ok else f"file missing: {path}",
        )

    # ----- internal -----

    def _path_from_token(self, token: ConnectorToken) -> Path:
        path = token.metadata.get("path")
        if path is None:
            raise BasefloError(
                error_code="BF-CONN-EXCEL-001",
                message="ExcelConnector token missing `path` in metadata.",
                status_code=500,
            )
        return Path(str(path))

    @staticmethod
    def _parse_has_header(metadata: Mapping[str, Any]) -> bool | None:
        literal = metadata.get("has_header")
        if literal is None:
            return None
        return str(literal) == "true"
