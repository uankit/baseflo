"""Google Sheets API v4 client — Bearer auth + 429 retry.

Per docs/40-features/CONN-SHEETS.md §5 + §6. The client only knows about
HTTP; refresh-on-expiry happens at the connector layer (so the connector
can persist the new token).
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx

from app.core.errors import BasefloError
from app.observability.logging import get_logger


__all__ = ["SheetsAPIClient"]


logger = get_logger("connectors.google_sheets.api")


_BASE_URL = "https://sheets.googleapis.com"


class SheetsAPIClient:
    """Async HTTP client for Google Sheets API v4."""

    _MAX_RETRIES_ON_THROTTLE = 1

    def __init__(
        self,
        *,
        access_token: str,
        transport: httpx.BaseTransport | None = None,
        timeout: float = 30.0,
    ) -> None:
        self._token = access_token
        self._transport = transport
        self._timeout = timeout

    async def get_spreadsheet(
        self, spreadsheet_id: str, *, fields: str | None = None
    ) -> dict[str, Any]:
        """`GET /v4/spreadsheets/{id}` — returns sheet list + grid dimensions."""
        params: dict[str, Any] = {}
        if fields is not None:
            params["fields"] = fields
        return await self._get(f"/v4/spreadsheets/{spreadsheet_id}", params=params)

    async def get_values(
        self,
        spreadsheet_id: str,
        *,
        range_a1: str,
        major_dimension: str = "ROWS",
    ) -> dict[str, Any]:
        """`GET /v4/spreadsheets/{id}/values/{range}` — returns the cell grid."""
        params = {"majorDimension": major_dimension}
        return await self._get(
            f"/v4/spreadsheets/{spreadsheet_id}/values/{range_a1}",
            params=params,
        )

    async def update_values(
        self,
        spreadsheet_id: str,
        *,
        range_a1: str,
        values: list[list[Any]],
        value_input_option: str = "USER_ENTERED",
    ) -> dict[str, Any]:
        """`PUT /v4/spreadsheets/{id}/values/{range}` — replace cells in the
        target range with `values` (a 2-D list of cell values).
        """
        return await self._request(
            "PUT",
            f"/v4/spreadsheets/{spreadsheet_id}/values/{range_a1}",
            params={"valueInputOption": value_input_option},
            json={"range": range_a1, "majorDimension": "ROWS", "values": values},
            base_url="https://sheets.googleapis.com",
        )

    async def append_values(
        self,
        spreadsheet_id: str,
        *,
        range_a1: str,
        values: list[list[Any]],
        value_input_option: str = "USER_ENTERED",
    ) -> dict[str, Any]:
        """`POST /v4/spreadsheets/{id}/values/{range}:append` — add rows."""
        return await self._request(
            "POST",
            f"/v4/spreadsheets/{spreadsheet_id}/values/{range_a1}:append",
            params={
                "valueInputOption": value_input_option,
                "insertDataOption": "INSERT_ROWS",
            },
            json={"range": range_a1, "majorDimension": "ROWS", "values": values},
            base_url="https://sheets.googleapis.com",
        )

    async def drive_files_watch(
        self,
        file_id: str,
        *,
        channel_id: str,
        callback_url: str,
        token: str | None = None,
        ttl_seconds: int | None = None,
    ) -> dict[str, Any]:
        """Subscribe to Drive change notifications for a file.

        `POST https://www.googleapis.com/drive/v3/files/{fileId}/watch`.
        Channels expire after at most one week; the caller is responsible
        for renewing before `expiration`.
        """
        body: dict[str, Any] = {
            "id": channel_id,
            "type": "web_hook",
            "address": callback_url,
        }
        if token is not None:
            body["token"] = token
        if ttl_seconds is not None:
            body["params"] = {"ttl": str(int(ttl_seconds))}
        return await self._request(
            "POST",
            f"/drive/v3/files/{file_id}/watch",
            params=None,
            json=body,
            base_url="https://www.googleapis.com",
        )

    async def drive_channels_stop(
        self, *, channel_id: str, resource_id: str,
    ) -> None:
        """`POST https://www.googleapis.com/drive/v3/channels/stop` — release
        a Drive change subscription."""
        await self._request(
            "POST",
            "/drive/v3/channels/stop",
            params=None,
            json={"id": channel_id, "resourceId": resource_id},
            base_url="https://www.googleapis.com",
            allow_no_body=True,
        )

    # ---------- internal ----------

    async def _get(
        self, path: str, *, params: dict[str, Any] | None
    ) -> dict[str, Any]:
        return await self._request("GET", path, params=params, json=None)

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None,
        json: dict[str, Any] | None,
        base_url: str = _BASE_URL,
        allow_no_body: bool = False,
    ) -> dict[str, Any]:
        url = f"{base_url}{path}"
        for attempt in range(self._MAX_RETRIES_ON_THROTTLE + 1):
            response = await self._send_once(method, url, params=params, json=json)
            if response.status_code != 429:
                return self._handle_response(
                    response, method=method, path=path,
                    allow_no_body=allow_no_body,
                )

            if attempt >= self._MAX_RETRIES_ON_THROTTLE:
                raise BasefloError(
                    error_code="BF-CONN-SHEETS-004",
                    message="Google Sheets rate limit exhausted after retry.",
                    status_code=429,
                )
            retry_after = _parse_retry_after(response.headers.get("Retry-After"))
            logger.warning("sheets_rate_limited", retry_after=retry_after)
            await asyncio.sleep(retry_after)

        raise BasefloError(  # pragma: no cover — defensive
            error_code="BF-CONN-SHEETS-004",
            message="Sheets retry loop exited unexpectedly.",
            status_code=500,
        )

    async def _send_once(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, Any] | None,
        json: dict[str, Any] | None = None,
    ) -> httpx.Response:
        client_kwargs: dict[str, object] = {"timeout": self._timeout}
        if self._transport is not None:
            client_kwargs["transport"] = self._transport
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/json",
        }
        try:
            async with httpx.AsyncClient(**client_kwargs) as client:  # type: ignore[arg-type]
                return await client.request(
                    method, url, params=params, json=json, headers=headers,
                )
        except httpx.HTTPError as exc:
            raise BasefloError(
                error_code="BF-CONN-SHEETS-003",
                message=f"Google Sheets transport error: {exc!r}",
                status_code=502,
                cause=exc,
            ) from exc

    def _handle_response(
        self, response: httpx.Response, *, method: str, path: str,
        allow_no_body: bool = False,
    ) -> dict[str, Any]:
        if response.status_code == 401:
            raise BasefloError(
                error_code="BF-CONN-SHEETS-001",
                message="Google Sheets rejected the access token (401).",
                status_code=401,
            )
        if response.status_code >= 400:
            raise BasefloError(
                error_code="BF-CONN-SHEETS-003",
                message=(
                    f"Google Sheets {method} {path} returned status="
                    f"{response.status_code}."
                ),
                status_code=502,
                details={"status": response.status_code, "body": response.text[:500]},
            )
        if allow_no_body and not response.content:
            return {}
        try:
            data: dict[str, Any] = response.json()
        except ValueError as exc:
            if allow_no_body:
                return {}
            raise BasefloError(
                error_code="BF-CONN-SHEETS-003",
                message="Google Sheets response was not JSON.",
                status_code=502,
                cause=exc,
            ) from exc
        return data


def _parse_retry_after(value: str | None) -> float:
    if not value:
        return 1.0
    try:
        return max(0.1, min(float(value), 60.0))
    except ValueError:
        return 1.0
