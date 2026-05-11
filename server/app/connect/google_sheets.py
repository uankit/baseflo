"""Google Sheets connector."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.connect.base import ColumnSchema, Connector, Row, SourceQuery, SourceSchema, TableSchema
from app.config import get_settings
from app.core.errors import BasefloError

settings = get_settings()

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
SHEETS_API_BASE = "https://sheets.googleapis.com/v4/spreadsheets"
DRIVE_API_BASE = "https://www.googleapis.com/drive/v3"

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.metadata.readonly",
]


class GoogleSheetsConnector(Connector):
    """Read-only Google Sheets connector with OAuth2."""

    kind = "google_sheets"

    # ---------- OAuth helpers ----------

    def get_auth_url(self, redirect_uri: str, state: str) -> str:
        """Build the Google OAuth consent URL."""
        if not settings.google_client_id:
            raise BasefloError(
                message="Google OAuth not configured",
                error_code="BF-CONN-002",
                status_code=503,
            )

        params = {
            "client_id": settings.google_client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": " ".join(SCOPES),
            "access_type": "offline",
            "prompt": "consent",
            "state": state,
        }
        from urllib.parse import urlencode
        return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"

    async def exchange_code(self, code: str, redirect_uri: str) -> dict[str, Any]:
        """Exchange OAuth code for access + refresh tokens."""
        if not settings.google_client_id or not settings.google_client_secret:
            raise BasefloError(
                message="Google OAuth not configured",
                error_code="BF-CONN-002",
                status_code=503,
            )

        payload = {
            "code": code,
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret.get_secret_value(),
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        }

        async with httpx.AsyncClient() as client:
            resp = await client.post(GOOGLE_TOKEN_URL, data=payload)
            if resp.status_code != 200:
                raise BasefloError(
                    message=f"Google token exchange failed: {resp.text}",
                    error_code="BF-CONN-003",
                    status_code=400,
                )
            return resp.json()

    async def refresh_access_token(self, refresh_token: str) -> dict[str, Any]:
        """Refresh an expired access token."""
        if not settings.google_client_id or not settings.google_client_secret:
            raise BasefloError(
                message="Google OAuth not configured",
                error_code="BF-CONN-002",
                status_code=503,
            )

        payload = {
            "refresh_token": refresh_token,
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret.get_secret_value(),
            "grant_type": "refresh_token",
        }

        async with httpx.AsyncClient() as client:
            resp = await client.post(GOOGLE_TOKEN_URL, data=payload)
            resp.raise_for_status()
            return resp.json()

    # ---------- Connector protocol ----------

    async def authenticate(self, config: dict[str, Any]) -> dict[str, Any]:
        """Validate credentials. Refresh if expired."""
        credentials = config.get("credentials", {})
        access_token = credentials.get("access_token")
        refresh_token = credentials.get("refresh_token")
        expires_at = credentials.get("expires_at")

        # Simple expiry check (ISO string)
        from datetime import UTC, datetime
        needs_refresh = False
        if expires_at:
            try:
                dt = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
                if dt < datetime.now(UTC):
                    needs_refresh = True
            except ValueError:
                needs_refresh = True

        if needs_refresh and refresh_token:
            refreshed = await self.refresh_access_token(refresh_token)
            credentials["access_token"] = refreshed["access_token"]
            if "refresh_token" in refreshed:
                credentials["refresh_token"] = refreshed["refresh_token"]
            # Update expiry
            from datetime import timedelta
            expires_in = refreshed.get("expires_in", 3600)
            new_expires = datetime.now(UTC) + timedelta(seconds=expires_in)
            credentials["expires_at"] = new_expires.isoformat()

        return {"credentials": credentials, "valid": True}

    async def introspect(self, config: dict[str, Any]) -> SourceSchema:
        """Discover sheets and columns."""
        spreadsheet_id = config["spreadsheet_id"]
        access_token = config["credentials"]["access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}

        async with httpx.AsyncClient() as client:
            # Get spreadsheet metadata (sheet names)
            meta_url = f"{SHEETS_API_BASE}/{spreadsheet_id}?fields=properties.title,sheets.properties.title"
            resp = await client.get(meta_url, headers=headers)
            if resp.status_code != 200:
                raise BasefloError(
                    message=f"Failed to introspect spreadsheet: {resp.text}",
                    error_code="BF-CONN-SHEETS-001",
                    status_code=400,
                )
            meta = resp.json()
            sheets = meta.get("sheets", [])

            tables: list[TableSchema] = []
            for sheet in sheets:
                title = sheet["properties"]["title"]
                # Fetch first 51 rows to infer schema
                range_a1 = f"{title}!A1:Z51"
                values_url = f"{SHEETS_API_BASE}/{spreadsheet_id}/values/{range_a1}"
                vresp = await client.get(values_url, headers=headers)
                vresp.raise_for_status()
                data = vresp.json()
                values = data.get("values", [])

                if not values:
                    continue

                headers_row = values[0]
                body = values[1:]

                columns: list[ColumnSchema] = []
                for idx, h in enumerate(headers_row):
                    col_name = str(h).strip() if h else f"column_{idx + 1}"
                    sample_values = [
                        row[idx] for row in body if len(row) > idx and row[idx] not in (None, "")
                    ][:5]
                    columns.append(ColumnSchema(
                        name=col_name,
                        data_type="text",  # will be refined by DiscoveryAgent
                        sample_values=sample_values,
                        nullable=True,
                    ))

                tables.append(TableSchema(
                    name=title.lower().replace(" ", "_").replace("-", "_")[:63],
                    label=title,
                    columns=columns,
                    row_count=None,  # would need separate count call
                ))

            return SourceSchema(tables=tables)

    async def read(
        self, config: dict[str, Any], query: SourceQuery,
    ) -> AsyncIterator[Row]:
        """Stream all rows from a sheet."""
        spreadsheet_id = config["spreadsheet_id"]
        access_token = config["credentials"]["access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}

        # query.table is the sanitized sheet name; we need the original title
        # For MVP, assume sanitized == original lowercased/underscored
        # In production, we'd store the mapping
        sheet_title = query.table.replace("_", " ").title()

        async with httpx.AsyncClient() as client:
            # Get all values (no limit for MVP; Google Sheets has 5M cell limit anyway)
            range_a1 = f"{sheet_title}"
            values_url = f"{SHEETS_API_BASE}/{spreadsheet_id}/values/{range_a1}"
            resp = await client.get(values_url, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            values = data.get("values", [])

            if not values:
                return

            header_row = values[0]
            col_names = [
                str(h).strip() if h else f"column_{i + 1}"
                for i, h in enumerate(header_row)
            ]

            for idx, row in enumerate(values[1:], start=1):
                cells = {
                    col_names[i]: row[i] if i < len(row) else None
                    for i in range(len(col_names))
                }
                yield Row(values=cells, source_id=str(idx))

    async def health_check(self, config: dict[str, Any]) -> bool:
        """Ping the spreadsheet metadata endpoint."""
        try:
            spreadsheet_id = config["spreadsheet_id"]
            access_token = config["credentials"]["access_token"]
            headers = {"Authorization": f"Bearer {access_token}"}
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{SHEETS_API_BASE}/{spreadsheet_id}?fields=spreadsheetId",
                    headers=headers,
                )
                return resp.status_code == 200
        except Exception:
            return False
