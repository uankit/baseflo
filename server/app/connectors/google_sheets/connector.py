"""GoogleSheetsConnector — OAuth2 + dynamic catalog + cell-grid streaming.

Per docs/40-features/CONN-SHEETS.md.

The connector handles refresh-on-expiry transparently: a token within 60s
of expiry triggers a refresh via `refresh_access_token` before any API call.
The new access_token is plumbed back via `_renewed_access_token` so the
saga (or token vault) can persist it.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import httpx

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
from app.connectors.google_sheets.api import SheetsAPIClient
from app.connectors.google_sheets.auth import refresh_access_token
from app.connectors.google_sheets.catalog import (
    build_table_from_grid,
    sanitize_sheet_title,
    sheets_from_spreadsheet_response,
)
from app.core.config import get_config
from app.core.errors import BasefloError
from app.core.ids import new_uuid7
from app.observability.logging import get_logger


logger = get_logger("connectors.google_sheets")


_INTROSPECT_FIELDS = "sheets(properties(title,sheetId,gridProperties))"
_INTROSPECT_SAMPLE_RANGE = "A1:Z51"
_REFRESH_THRESHOLD_SECONDS = 60


class GoogleSheetsConnector:
    """Read-only Google Sheets connector.

    Token state arrives via `ConnectorToken.metadata`:

      - `spreadsheet_id`: the Sheet's id (also visible in the URL).
      - `_access_token`: current bearer token.
      - `_refresh_token`: long-lived refresh token.
      - `_expires_at_iso`: ISO 8601 expiry of the current access_token.
      - `has_header`: optional `"true"` / `"false"` global override.
    """

    metadata: ConnectorMetadata = ConnectorMetadata(
        name="google_sheets",
        display_name="Google Sheets",
        version="1.0.0",
        protocol_version="1.0",
        auth_kind=AuthKind.OAUTH2,
        capabilities=ConnectorCapabilities(
            can_introspect=True,
            can_read=True,
            can_write=True,                   # writes via spreadsheets scope
            can_subscribe_webhooks=True,      # Drive push notifications
            supports_pagination=True,
            supports_streaming=True,
            requires_periodic_sync=False,
            write_back_canonical_only=False,
        ),
        required_scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive.metadata.readonly",
        ],
        docs_url="https://developers.google.com/sheets/api",
    )

    # ---------- auth ----------

    async def authenticate(self, credentials: AuthCredentials) -> ConnectorToken:
        spreadsheet = _required(credentials, "spreadsheet_id")
        access_token = _required(credentials, "access_token")
        refresh_token = _required(credentials, "refresh_token")
        expires_at = credentials.payload.get("expires_at")
        expires_at_str = (
            expires_at.get_secret_value() if expires_at is not None else _default_expiry()
        )

        # Validate by hitting the spreadsheet metadata endpoint.
        client = SheetsAPIClient(
            access_token=access_token,
            transport=_transport_from_creds(credentials),
        )
        try:
            await client.get_spreadsheet(spreadsheet, fields="spreadsheetId")
        except BasefloError as exc:
            raise BasefloError(
                error_code="BF-CONN-SHEETS-001",
                message=(
                    "Google Sheets authentication failed; access_token rejected. "
                    "If the token expired, supply `refresh_token`."
                ),
                status_code=401,
                cause=exc,
            ) from exc

        metadata: dict[str, Any] = {
            "spreadsheet_id": spreadsheet,
            "_access_token": access_token,
            "_refresh_token": refresh_token,
            "_expires_at_iso": expires_at_str,
        }
        has_header = credentials.payload.get("has_header")
        if has_header is not None:
            literal = has_header.get_secret_value().strip().lower()
            if literal not in {"true", "false"}:
                raise BasefloError(
                    error_code="BF-CONN-SHEETS-001",
                    message=(
                        "GoogleSheetsConnector `has_header` must be 'true' or 'false'."
                    ),
                    status_code=400,
                )
            metadata["has_header"] = literal

        return ConnectorToken(
            connector_name=self.metadata.name,
            token_id=UUID("01970000-0000-7000-8000-000000000003"),
            metadata=metadata,
        )

    async def revoke(self, token: ConnectorToken) -> None:
        _ = token

    # ---------- introspection + sampling ----------

    async def introspect_schema(self, token: ConnectorToken) -> SourceSchema:
        spreadsheet_id = self._spreadsheet_id(token)
        has_header = self._has_header_from_token(token.metadata)
        client = await self._client(token)

        spreadsheet = await client.get_spreadsheet(
            spreadsheet_id, fields=_INTROSPECT_FIELDS
        )
        sheet_props_list = sheets_from_spreadsheet_response(spreadsheet)
        tables = []
        for props in sheet_props_list:
            title = props.get("title")
            if not isinstance(title, str):
                continue
            range_a1 = f"'{title}'!{_INTROSPECT_SAMPLE_RANGE}"
            grid = await client.get_values(spreadsheet_id, range_a1=range_a1)
            values = grid.get("values") or []
            table = build_table_from_grid(
                sheet_properties=props,
                grid_values=values if isinstance(values, list) else [],
                has_header=True if has_header is None else has_header,
            )
            if table is not None:
                tables.append(table)

        return SourceSchema(
            tables=tables,
            introspected_at=datetime.now(UTC),
            notes=f"spreadsheet_id={spreadsheet_id}",
        )

    async def sample_rows(
        self, token: ConnectorToken, table: str, n: int
    ) -> list[Row]:
        spreadsheet_id = self._spreadsheet_id(token)
        sheet_title = await self._resolve_sheet_title(token, table)
        n = max(1, min(int(n), 1000))
        client = await self._client(token)

        range_a1 = f"'{sheet_title}'!A1:Z{n + 1}"
        grid = await client.get_values(spreadsheet_id, range_a1=range_a1)
        values = grid.get("values") or []
        if not isinstance(values, list) or not values:
            return []
        return list(self._rows_from_grid(values, has_header=self._has_header_or_default(token)))

    async def read(
        self, token: ConnectorToken, query: SourceQuery
    ) -> AsyncIterator[Row]:
        if query.table is None or not query.table:
            raise BasefloError(
                error_code="BF-CONN-SHEETS-005",
                message="GoogleSheetsConnector.read requires `query.table`.",
                status_code=400,
            )
        return self._stream(token, query)

    async def _stream(
        self, token: ConnectorToken, query: SourceQuery
    ) -> AsyncIterator[Row]:
        spreadsheet_id = self._spreadsheet_id(token)
        sheet_title = await self._resolve_sheet_title(token, query.table)
        client = await self._client(token)
        has_header = self._has_header_or_default(token)
        limit = int(query.limit) if query.limit else None

        range_a1 = f"'{sheet_title}'"  # full sheet
        grid = await client.get_values(spreadsheet_id, range_a1=range_a1)
        values = grid.get("values") or []
        if not isinstance(values, list):
            return

        emitted = 0
        for row in self._rows_from_grid(values, has_header=has_header):
            yield row
            emitted += 1
            if limit is not None and emitted >= limit:
                return

    # ---------- write ----------

    async def write(
        self, token: ConnectorToken, mutation: SourceMutation
    ) -> WriteResult:
        """Write-back via `values.update` (op=update) and `values.append`
        (op=create). Requires the `spreadsheets` scope.

        Validate `mutation.values` / `mutation.where` BEFORE the introspection
        round-trip so client errors don't waste a Sheets API call.
        """
        if mutation.op == "create" and mutation.values is None:
            raise BasefloError(
                error_code="BF-CONN-SHEETS-003",
                message="Sheets create requires `values`.",
                status_code=400,
            )
        if mutation.op == "update":
            if not mutation.where or "row" not in mutation.where:
                raise BasefloError(
                    error_code="BF-CONN-SHEETS-003",
                    message=(
                        "Sheets update requires `where['row']` (1-indexed sheet row)."
                    ),
                    status_code=400,
                )
            if mutation.values is None:
                raise BasefloError(
                    error_code="BF-CONN-SHEETS-003",
                    message="Sheets update requires `values`.",
                    status_code=400,
                )

        spreadsheet_id = self._spreadsheet_id(token)
        sheet_title = await self._resolve_sheet_title(token, mutation.table)
        client = await self._client(token)

        if mutation.op == "create":
            assert mutation.values is not None  # guarded above
            row = [_serialise_cell(v) for v in mutation.values.values()]
            await client.append_values(
                spreadsheet_id, range_a1=f"'{sheet_title}'!A1", values=[row],
            )
            return WriteResult(success=True, affected_rows=1, new_id=None)

        if mutation.op == "update":
            assert mutation.where is not None and mutation.values is not None
            row_index = int(mutation.where["row"])
            row = [_serialise_cell(v) for v in mutation.values.values()]
            await client.update_values(
                spreadsheet_id,
                range_a1=f"'{sheet_title}'!A{row_index}",
                values=[row],
            )
            return WriteResult(success=True, affected_rows=1, new_id=str(row_index))

        if mutation.op == "delete":
            # Sheets API doesn't have a row-delete via values.* — needs the
            # the broader sheets-write feature.
            raise BasefloError(
                error_code="BF-CONN-002",
                message=(
                    "Sheets row-delete requires `batchUpdate.deleteDimension`; "
                    "Not available in v1."
                ),
                status_code=501,
            )

        raise BasefloError(
            error_code="BF-CONN-SHEETS-003",
            message=f"Unsupported mutation op: {mutation.op!r}.",
            status_code=400,
        )

    # ---------- webhooks (Drive Push Notifications) ----------

    async def webhook_subscribe(
        self,
        token: ConnectorToken,
        events: list[str],
        callback_url: str,
    ) -> Subscription:
        """Subscribe to Drive change notifications for the spreadsheet.

        Drive watch returns `{ id, resourceId, expiration }`. Channels expire
        after at most one week; the saga renews before `expires_at`.
        `Subscription.id` is `<channel_id>:<resource_id>` so
        `webhook_unsubscribe` has the data to call channels.stop.
        """
        spreadsheet_id = self._spreadsheet_id(token)
        client = await self._client(token)
        channel_id = f"baseflo-{spreadsheet_id}-{new_uuid7()}"

        # `token=spreadsheet_id` rides along on the channel — Drive echoes it
        # back as `X-Goog-Channel-Token` on every push, so the webhook route
        # can identify which spreadsheet refetches without a DB lookup.
        response = await client.drive_files_watch(
            spreadsheet_id,
            channel_id=channel_id,
            callback_url=callback_url,
            token=spreadsheet_id,
        )
        resource_id = response.get("resourceId")
        if not isinstance(resource_id, str):
            raise BasefloError(
                error_code="BF-CONN-SHEETS-003",
                message="Drive watch response missing `resourceId`.",
                status_code=502,
            )
        expires_at: datetime | None = None
        expiration_raw = response.get("expiration")
        if isinstance(expiration_raw, (int, str)):
            try:
                expires_ms = int(expiration_raw)
                expires_at = datetime.fromtimestamp(expires_ms / 1000, tz=UTC)
            except (TypeError, ValueError):
                expires_at = None

        logger.info(
            "sheets_drive_watch_started",
            spreadsheet_id=spreadsheet_id,
            channel_id=channel_id,
            expires_at=expires_at.isoformat() if expires_at else None,
        )
        return Subscription(
            id=f"{channel_id}:{resource_id}",
            events=events or ["drive.changes"],
            callback_url=callback_url,
            expires_at=expires_at,
        )

    async def webhook_unsubscribe(
        self, token: ConnectorToken, subscription: Subscription,
    ) -> None:
        """Stop the Drive change channel via channels.stop. Idempotent."""
        if not subscription.id or ":" not in subscription.id:
            return
        channel_id, _, resource_id = subscription.id.partition(":")
        if not channel_id or not resource_id:
            return
        client = await self._client(token)
        try:
            await client.drive_channels_stop(
                channel_id=channel_id, resource_id=resource_id,
            )
        except BasefloError as exc:
            if "404" in (exc.message or ""):
                return  # already stopped — idempotent
            raise
        logger.info(
            "sheets_drive_channel_stopped",
            spreadsheet_id=str(token.metadata.get("spreadsheet_id")),
            channel_id=channel_id,
        )

    # ---------- health ----------

    async def health_check(self, token: ConnectorToken) -> HealthStatus:
        import time  # noqa: PLC0415

        spreadsheet_id = self._spreadsheet_id(token)
        client = await self._client(token)
        started = time.perf_counter()
        try:
            await client.get_spreadsheet(spreadsheet_id, fields="spreadsheetId")
        except BasefloError as exc:
            return HealthStatus(
                healthy=False,
                last_checked_at=datetime.now(UTC),
                latency_ms=int((time.perf_counter() - started) * 1000),
                notes=f"{exc.error_code}: {exc.message}",
            )
        return HealthStatus(
            healthy=True,
            last_checked_at=datetime.now(UTC),
            latency_ms=int((time.perf_counter() - started) * 1000),
            notes=None,
        )

    # ---------- internal ----------

    async def _client(self, token: ConnectorToken) -> SheetsAPIClient:
        access_token = await self._fresh_access_token(token)
        transport = token.metadata.get("_transport")
        return SheetsAPIClient(
            access_token=access_token,
            transport=transport if isinstance(transport, httpx.BaseTransport) else None,
        )

    async def _fresh_access_token(self, token: ConnectorToken) -> str:
        access_token = _metadata_str(token.metadata, "_access_token", "access_token")
        refresh_token = _metadata_str(token.metadata, "_refresh_token", "refresh_token")
        expires_at_iso = _metadata_str(token.metadata, "_expires_at_iso", "expires_at")

        if access_token is None or refresh_token is None:
            raise BasefloError(
                error_code="BF-CONN-SHEETS-001",
                message=(
                    "Google Sheets token missing access_token / refresh_token "
                    "in metadata."
                ),
                status_code=500,
            )
        token.metadata["_access_token"] = access_token
        token.metadata["_refresh_token"] = refresh_token
        if expires_at_iso is not None:
            token.metadata["_expires_at_iso"] = expires_at_iso

        if expires_at_iso is not None:
            try:
                expires_at = datetime.fromisoformat(expires_at_iso.replace("Z", "+00:00"))
            except ValueError:
                expires_at = datetime.now(UTC) - timedelta(seconds=1)
        else:
            expires_at = datetime.now(UTC) - timedelta(seconds=1)

        if expires_at - datetime.now(UTC) > timedelta(seconds=_REFRESH_THRESHOLD_SECONDS):
            return access_token

        config = get_config()
        if config.google_client_id is None or config.google_client_secret is None:
            raise BasefloError(
                error_code="BF-CONN-SHEETS-002",
                message=(
                    "Google OAuth client credentials are not configured. Set "
                    "BASEFLO_GOOGLE_CLIENT_ID + BASEFLO_GOOGLE_CLIENT_SECRET."
                ),
                status_code=503,
            )
        transport = token.metadata.get("_transport")
        result = await refresh_access_token(
            refresh_token=refresh_token,
            client_id=config.google_client_id,
            client_secret=config.google_client_secret.get_secret_value(),
            transport=transport if isinstance(transport, httpx.BaseTransport) else None,
        )
        # Mutate token metadata in-place so subsequent calls in the same saga
        # don't re-trigger refresh; persistence to `connector_tokens` is the
        token.metadata["_access_token"] = result.access_token
        new_expiry = datetime.now(UTC) + timedelta(seconds=result.expires_in)
        token.metadata["_expires_at_iso"] = new_expiry.isoformat()
        if result.refresh_token is not None:
            token.metadata["_refresh_token"] = result.refresh_token
        logger.info(
            "google_sheets_token_refreshed",
            spreadsheet_id=str(token.metadata.get("spreadsheet_id")),
            new_expiry=token.metadata["_expires_at_iso"],
        )
        return result.access_token

    def _spreadsheet_id(self, token: ConnectorToken) -> str:
        sid = token.metadata.get("spreadsheet_id")
        if not isinstance(sid, str):
            raise BasefloError(
                error_code="BF-CONN-SHEETS-001",
                message="Google Sheets token missing `spreadsheet_id` in metadata.",
                status_code=500,
            )
        return sid

    async def _resolve_sheet_title(
        self, token: ConnectorToken, sanitized_name: str
    ) -> str:
        """Map a sanitized table name back to the spreadsheet's actual sheet title.

        Required because we sanitize titles for the catalog ("Customer List" →
        "customer_list") but the API needs the original title.
        """
        client = await self._client(token)
        spreadsheet = await client.get_spreadsheet(
            self._spreadsheet_id(token), fields=_INTROSPECT_FIELDS,
        )
        for props in sheets_from_spreadsheet_response(spreadsheet):
            title = props.get("title")
            if isinstance(title, str) and sanitize_sheet_title(title) == sanitized_name:
                return title
        raise BasefloError(
            error_code="BF-CONN-SHEETS-005",
            message=f"Spreadsheet does not contain a sheet matching {sanitized_name!r}.",
            status_code=400,
        )

    def _has_header_from_token(self, metadata: Mapping[str, Any]) -> bool | None:
        literal = metadata.get("has_header")
        if literal is None:
            return None
        return str(literal) == "true"

    def _has_header_or_default(self, token: ConnectorToken) -> bool:
        v = self._has_header_from_token(token.metadata)
        return True if v is None else v

    def _rows_from_grid(
        self, values: list[Any], *, has_header: bool
    ) -> list[Row]:
        if not values:
            return []
        first_row = values[0]
        if not isinstance(first_row, list):
            return []
        if has_header:
            headers = [
                str(c).strip() if c not in (None, "") else f"column_{i + 1}"
                for i, c in enumerate(first_row)
            ]
            body = values[1:]
        else:
            headers = [f"column_{i + 1}" for i in range(len(first_row))]
            body = values

        out: list[Row] = []
        for raw in body:
            if not isinstance(raw, list):
                continue
            cells: dict[str, Any] = {}
            for i, header in enumerate(headers):
                if i < len(raw):
                    v = raw[i]
                    cells[header] = None if v == "" else v
                else:
                    cells[header] = None
            out.append(Row(values=cells))
        return out


# ---------- module-level helpers ----------


def _serialise_cell(value: Any) -> Any:
    """Sheets API accepts JSON primitives + ISO strings for datetimes; convert
    Python `datetime` → ISO 8601 so the merchant's spreadsheet sees a
    consistent format across writes."""
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def _required(creds: AuthCredentials, key: str) -> str:
    secret = creds.payload.get(key)
    if secret is None:
        raise BasefloError(
            error_code="BF-CONN-SHEETS-001",
            message=f"Google Sheets connector requires `{key}` in credentials.payload.",
            status_code=400,
        )
    return secret.get_secret_value()


def _default_expiry() -> str:
    """Used only when `expires_at` is omitted (test path); production
    OAuth callback always supplies the real expiry."""
    return (datetime.now(UTC) + timedelta(seconds=3600)).isoformat()


def _metadata_str(metadata: Mapping[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = metadata.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return None


def _transport_from_creds(creds: AuthCredentials) -> httpx.BaseTransport | None:
    return getattr(creds, "_transport", None)
