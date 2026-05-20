from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import quote

import httpx
from pydantic import BaseModel

from connectors.auth import OAuth2Config, OAuth2Helper
from connectors.base import (
    AccountInfo,
    AvailableResource,
    ColumnSchema,
    Row,
    Source,
    SourceQuery,
    SourceSchema,
    SourceSpec,
    TableSchema,
)
from connectors.errors import AuthError, IntrospectError, ReadError
from connectors.registry import register_source
from connectors.spreadsheet_preprocessor import (
    PreprocessedTable,
    preview_rows,
    preprocess_grid,
)
from connectors.types import AuthMethod, Capability, DataType

logger = logging.getLogger("connectors.google_sheets")

SHEETS_API_BASE = "https://sheets.googleapis.com/v4/spreadsheets"
DRIVE_API_BASE = "https://www.googleapis.com/drive/v3"
USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"
VALUES_PARAMS = {
    "majorDimension": "ROWS",
    "valueRenderOption": "FORMATTED_VALUE",
    "dateTimeRenderOption": "FORMATTED_STRING",
}


def _table_schema_from_preprocessed(table: PreprocessedTable) -> TableSchema:
    columns: list[ColumnSchema] = []
    for idx, col_name in enumerate(table.columns):
        sample_values = [
            row[idx]
            for row in table.rows
            if len(row) > idx and row[idx] not in (None, "")
        ][:5]
        columns.append(
            ColumnSchema(
                name=col_name,
                data_type=DataType.TEXT,
                sample_values=sample_values,
                nullable=True,
            )
        )
    return TableSchema(
        name=table.name[:63],
        label=table.sheet_name,
        columns=columns,
        row_count=len(table.rows),
        metadata={
            **table.metadata,
            "source": table.source,
            "logical_label": table.label,
            "preview_rows": preview_rows(table),
        },
    )


def _row_from_preprocessed(
    table: PreprocessedTable,
    row: list[Any],
    source_id: str,
) -> Row:
    cells = {
        table.columns[idx]: row[idx] if idx < len(row) else None
        for idx in range(len(table.columns))
    }
    return Row(values=cells, source_id=source_id)


def _sheet_range(sheet_title: str) -> str:
    escaped = sheet_title.replace("'", "''")
    return f"'{escaped}'"


def _values_url(spreadsheet_id: str, range_a1: str) -> str:
    return f"{SHEETS_API_BASE}/{spreadsheet_id}/values/{quote(range_a1, safe='')}"


# ---------- Config ----------

class OAuth2Credentials(BaseModel):
    access_token: str
    refresh_token: str | None = None
    expires_at: str | None = None


class GoogleSheetsConfig(BaseModel):
    spreadsheet_id: str
    credentials: OAuth2Credentials


# ---------- Spec ----------

SPEC = SourceSpec(
    kind="google_sheets",
    display_name="Google Sheets",
    description="Read tabs and rows from a Google Sheets spreadsheet.",
    auth_method=AuthMethod.OAUTH2,
    capabilities=frozenset({
        Capability.INTROSPECT,
        Capability.READ,
        Capability.LIST_RESOURCES,
    }),
    config_schema=GoogleSheetsConfig,
)


# ---------- Runtime ----------

_OAUTH = OAuth2Helper(
    OAuth2Config(
        authorize_url="https://accounts.google.com/o/oauth2/v2/auth",
        token_url="https://oauth2.googleapis.com/token",
        scopes=[
            "openid",
            "email",
            "profile",
            "https://www.googleapis.com/auth/spreadsheets.readonly",
            "https://www.googleapis.com/auth/drive.metadata.readonly",
        ],
    )
)


@register_source
class GoogleSheetsSource(Source):
    """Read-only Google Sheets source via OAuth2."""

    spec = SPEC

    def __init__(self, *, client_id: str, client_secret: str) -> None:
        self._client_id = client_id
        self._client_secret = client_secret

    # ---- OAuth flow ----

    def authorize_url(self, *, redirect_uri: str, state: str) -> str:
        return _OAUTH.authorize_url(
            client_id=self._client_id,
            redirect_uri=redirect_uri,
            state=state,
            extra_params={"access_type": "offline", "prompt": "consent"},
        )

    async def exchange_code(self, *, code: str, redirect_uri: str) -> dict[str, Any]:
        return await _OAUTH.exchange_code(
            code=code,
            client_id=self._client_id,
            client_secret=self._client_secret,
            redirect_uri=redirect_uri,
        )

    # ---- Source protocol ----

    async def authenticate(self, config: dict[str, Any]) -> dict[str, Any]:
        credentials = dict(config.get("credentials") or {})
        refresh_token = credentials.get("refresh_token")
        expires_at = credentials.get("expires_at")

        needs_refresh = False
        if expires_at:
            try:
                dt = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
                if dt < datetime.now(UTC):
                    needs_refresh = True
            except ValueError:
                needs_refresh = True

        if needs_refresh:
            if not refresh_token:
                raise AuthError(
                    message="Access token expired and no refresh token available",
                    code="OAUTH_NO_REFRESH_TOKEN",
                    status_hint=401,
                )
            refreshed = await _OAUTH.refresh(
                refresh_token=refresh_token,
                client_id=self._client_id,
                client_secret=self._client_secret,
            )
            credentials["access_token"] = refreshed["access_token"]
            if "refresh_token" in refreshed:
                credentials["refresh_token"] = refreshed["refresh_token"]
            expires_in = int(refreshed.get("expires_in", 3600))
            credentials["expires_at"] = (
                datetime.now(UTC) + timedelta(seconds=expires_in)
            ).isoformat()

        return {**config, "credentials": credentials}

    async def introspect(self, config: dict[str, Any]) -> SourceSchema:
        spreadsheet_id = config["spreadsheet_id"]
        access_token = config["credentials"]["access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}

        async with httpx.AsyncClient(timeout=30.0) as client:
            meta_url = (
                f"{SHEETS_API_BASE}/{spreadsheet_id}"
                "?fields=properties.title,sheets.properties.title"
            )
            resp = await client.get(meta_url, headers=headers)
            if resp.status_code != 200:
                raise IntrospectError(
                    message=f"Failed to introspect spreadsheet: {resp.text}",
                    code="SHEETS_INTROSPECT_FAILED",
                    status_hint=resp.status_code,
                )
            sheets = resp.json().get("sheets", [])

            tables: list[TableSchema] = []
            for sheet in sheets:
                title = sheet["properties"]["title"]
                range_a1 = _sheet_range(title)
                values_url = _values_url(spreadsheet_id, range_a1)
                vresp = await client.get(
                    values_url,
                    headers=headers,
                    params=VALUES_PARAMS,
                )
                if vresp.status_code != 200:
                    raise IntrospectError(
                        message=f"Failed to read sheet '{title}': {vresp.text}",
                        code="SHEETS_INTROSPECT_FAILED",
                        status_hint=vresp.status_code,
                    )
                values = vresp.json().get("values", [])

                tables.extend(
                    _table_schema_from_preprocessed(table)
                    for table in preprocess_grid(
                        title,
                        values,
                        source="google_sheets_canonical_grid",
                    )
                )

        return SourceSchema(tables=tables)

    async def read(
        self, config: dict[str, Any], query: SourceQuery,
    ) -> AsyncIterator[Row]:
        spreadsheet_id = config["spreadsheet_id"]
        access_token = config["credentials"]["access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}

        sheet_title = query.label or query.table.replace("_", " ").title()

        async with httpx.AsyncClient(timeout=30.0) as client:
            range_a1 = _sheet_range(sheet_title)
            values_url = _values_url(spreadsheet_id, range_a1)
            resp = await client.get(
                values_url,
                headers=headers,
                params=VALUES_PARAMS,
            )
            if resp.status_code != 200:
                logger.error(
                    "Google Sheets read failed: %s %s — %s",
                    resp.status_code, values_url, resp.text,
                )
                raise ReadError(
                    message=f"Failed to read sheet '{sheet_title}': {resp.text}",
                    code="SHEETS_READ_FAILED",
                    status_hint=resp.status_code,
                )
            values = resp.json().get("values", [])

        if not values:
            return

        tables = preprocess_grid(
            sheet_title,
            values,
            source="google_sheets_canonical_grid",
        )
        if not tables:
            return

        table = next(
            (candidate for candidate in tables if candidate.name[:63] == query.table),
            tables[0],
        )
        for idx, row in enumerate(table.rows, start=1):
            source_row_number = (
                table.source_row_numbers[idx - 1]
                if idx - 1 < len(table.source_row_numbers)
                else idx
            )
            yield _row_from_preprocessed(
                table,
                row,
                source_id=str(source_row_number),
            )

    async def get_account_info(self, credentials: dict[str, Any]) -> AccountInfo:
        access_token = credentials["access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(USERINFO_URL, headers=headers)
        if resp.status_code != 200:
            raise AuthError(
                message=f"Failed to fetch Google account info: {resp.text}",
                code="USERINFO_FAILED",
                status_hint=resp.status_code,
            )
        info = resp.json()
        return AccountInfo(
            external_id=info["sub"],
            label=info.get("email", "unknown@google"),
            metadata={
                "name": info.get("name"),
                "picture": info.get("picture"),
                "verified_email": info.get("email_verified"),
            },
        )

    async def list_resources(
        self, credentials: dict[str, Any],
    ) -> list[AvailableResource]:
        access_token = credentials["access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}

        resources: list[AvailableResource] = []
        page_token: str | None = None
        async with httpx.AsyncClient(timeout=30.0) as client:
            while True:
                params: dict[str, Any] = {
                    "q": (
                        "mimeType='application/vnd.google-apps.spreadsheet'"
                        " and trashed=false"
                    ),
                    "fields": (
                        "nextPageToken, files(id, name, modifiedTime,"
                        " owners(emailAddress))"
                    ),
                    "pageSize": 100,
                }
                if page_token:
                    params["pageToken"] = page_token
                resp = await client.get(
                    f"{DRIVE_API_BASE}/files", headers=headers, params=params,
                )
                if resp.status_code != 200:
                    raise ReadError(
                        message=f"Failed to list spreadsheets: {resp.text}",
                        code="DRIVE_LIST_FAILED",
                        status_hint=resp.status_code,
                    )
                data = resp.json()
                for f in data.get("files", []):
                    resources.append(
                        AvailableResource(
                            external_id=f["id"],
                            name=f.get("name", "Untitled"),
                            metadata={
                                "modified_at": f.get("modifiedTime"),
                                "owners": [
                                    o.get("emailAddress")
                                    for o in f.get("owners", [])
                                ],
                            },
                        )
                    )
                page_token = data.get("nextPageToken")
                if not page_token:
                    break
        return resources

    async def health_check(self, config: dict[str, Any]) -> bool:
        try:
            spreadsheet_id = config["spreadsheet_id"]
            access_token = config["credentials"]["access_token"]
            headers = {"Authorization": f"Bearer {access_token}"}
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(
                    f"{SHEETS_API_BASE}/{spreadsheet_id}?fields=spreadsheetId",
                    headers=headers,
                )
            return resp.status_code == 200
        except Exception:
            return False
