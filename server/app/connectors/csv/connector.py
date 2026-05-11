"""CSVConnector — file-upload-driven introspection + read.

Per docs/40-features/CONN-CSV.md.

v1 ships with local-filesystem token paths so the saga + tests can drive it.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

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
from app.connectors.csv.parser import (
    infer_source_type,
    parse_text,
)
from app.core.errors import BasefloError
from app.observability.logging import get_logger

logger = get_logger("connectors.csv")


class CSVConnector:
    """Upload-driven CSV ingestion. One uploaded file → one source table.

    The token's metadata carries:
      - `path`: local filesystem path to the uploaded file (M1).
      - `table_name`: the canonical table name to expose. Defaults to the
        file stem (sanitised).
    """

    metadata: ConnectorMetadata = ConnectorMetadata(
        name="csv",
        display_name="CSV / Excel Upload",
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

    _SAMPLE_FOR_TYPE_INFERENCE = 200

    # ----- auth -----

    async def authenticate(self, credentials: AuthCredentials) -> ConnectorToken:
        path_secret = credentials.payload.get("path")
        if path_secret is None:
            raise BasefloError(
                error_code="BF-CONN-CSV-001",
                message="CSVConnector requires `path` in credentials.payload.",
                status_code=400,
            )
        path = Path(path_secret.get_secret_value())
        if not path.is_file():
            raise BasefloError(
                error_code="BF-CONN-CSV-001",
                message=f"CSV file not found at path: {path}",
                status_code=400,
            )

        metadata: dict[str, str] = {
            "path": str(path),
            "table_name": path.stem.lower().replace("-", "_"),
        }
        # `has_header` is an opt-in override per CONN-CSV.md §5. When absent,
        # the parser auto-detects via the deterministic comparison detector
        # and surfaces BF-CONN-CSV-005 if it can't decide.
        has_header = credentials.payload.get("has_header")
        if has_header is not None:
            literal = has_header.get_secret_value().strip().lower()
            if literal not in {"true", "false"}:
                raise BasefloError(
                    error_code="BF-CONN-CSV-001",
                    message=(
                        "CSVConnector `has_header` must be 'true' or 'false' "
                        f"if supplied; got {literal!r}."
                    ),
                    status_code=400,
                )
            metadata["has_header"] = literal

        return ConnectorToken(
            connector_name=self.metadata.name,
            token_id=UUID("01970000-0000-7000-8000-000000000000"),
            metadata=metadata,
        )

    async def revoke(self, token: ConnectorToken) -> None:
        # Files persist after revocation; the Token Vault deletes the upload.
        # The connector itself has no provider-side revocation step.
        _ = token

    # ----- introspection + sampling -----

    async def introspect_schema(self, token: ConnectorToken) -> SourceSchema:
        path = self._path_from_token(token)
        text = path.read_text(encoding=self._detect_encoding(path))
        headers, rows = parse_text(
            text,
            has_header=self._has_header_from_token(token),
            max_rows=self._SAMPLE_FOR_TYPE_INFERENCE,
        )

        if not headers:
            return SourceSchema(
                tables=[],
                introspected_at=datetime.now(UTC),
                notes="Empty CSV file; no columns introspected.",
            )

        columns: list[SourceColumn] = []
        for col in headers:
            values = [r.get(col) for r in rows]
            non_null = [v for v in values if v is not None]
            columns.append(
                SourceColumn(
                    name=col,
                    source_type=infer_source_type(values),
                    nullable=any(v is None for v in values),
                    sample_values=non_null[:30],
                    description=None,
                    primary_key_member=False,
                )
            )

        table_name = token.metadata.get("table_name") or path.stem
        return SourceSchema(
            tables=[
                SourceTable(
                    name=str(table_name),
                    columns=columns,
                    estimated_row_count=len(rows),
                    primary_key=[],
                )
            ],
            introspected_at=datetime.now(UTC),
            notes=f"file={path.name}, sampled={len(rows)} rows",
        )

    async def sample_rows(
        self, token: ConnectorToken, table: str, n: int
    ) -> list[Row]:
        # CSV connector exposes only one table per upload; we ignore `table`
        # but verify the caller asked for the right one.
        expected = token.metadata.get("table_name")
        if expected is not None and table != expected:
            raise BasefloError(
                error_code="BF-CONN-CSV-001",
                message=(
                    f"CSVConnector only exposes table {expected!r} for this token; "
                    f"got {table!r}."
                ),
                status_code=400,
            )
        path = self._path_from_token(token)
        text = path.read_text(encoding=self._detect_encoding(path))
        _, rows = parse_text(
            text,
            has_header=self._has_header_from_token(token),
            max_rows=max(1, min(int(n), 1000)),
        )
        return [Row(values=r) for r in rows]

    async def read(
        self, token: ConnectorToken, query: SourceQuery
    ) -> AsyncIterator[Row]:
        return self._stream_rows(token, query)

    async def _stream_rows(
        self, token: ConnectorToken, query: SourceQuery
    ) -> AsyncIterator[Row]:
        path = self._path_from_token(token)
        text = path.read_text(encoding=self._detect_encoding(path))
        _, rows = parse_text(
            text,
            has_header=self._has_header_from_token(token),
            max_rows=query.limit,
        )
        for row in rows:
            yield Row(values=row)

    # ----- writes / webhooks (unsupported by capability) -----

    async def write(
        self, token: ConnectorToken, mutation: SourceMutation
    ) -> WriteResult:
        _ = (token, mutation)
        raise BasefloError(
            error_code="BF-CONN-002",
            message="CSVConnector is read-only; refresh by uploading a new file.",
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
            message="CSVConnector does not support webhooks.",
            status_code=501,
        )

    async def webhook_unsubscribe(
        self, token: ConnectorToken, subscription: Subscription,
    ) -> None:
        _ = (token, subscription)
        raise BasefloError(
            error_code="BF-CONN-002",
            message="CSVConnector does not support webhooks.",
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
                error_code="BF-CONN-CSV-001",
                message="CSVConnector token missing `path` in metadata.",
                status_code=500,
            )
        return Path(str(path))

    @staticmethod
    def _has_header_from_token(token: ConnectorToken) -> bool | None:
        """Return the explicit override if present, else None to auto-detect.

        `metadata` carries the literal ``"true"`` / ``"false"`` set by
        `authenticate`; absent value means "let the parser decide".
        """
        literal = token.metadata.get("has_header")
        if literal is None:
            return None
        return bool(str(literal) == "true")

    @staticmethod
    def _detect_encoding(path: Path) -> str:
        """Best-effort encoding detection. We try UTF-8 first; fall back to
        latin-1 (which never raises)."""
        try:
            with path.open("r", encoding="utf-8") as f:
                f.read(1024)
            return "utf-8"
        except UnicodeDecodeError:
            return "latin-1"
