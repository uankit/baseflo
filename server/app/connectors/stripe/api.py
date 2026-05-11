"""Stripe REST API client — async httpx + cursor pagination + 429 retry.

Per docs/40-features/CONN-STRIPE.md §6. Single client per (account, request);
no pooling across accounts.
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx

from app.connectors.stripe.catalog import API_VERSION
from app.core.errors import BasefloError
from app.observability.logging import get_logger


__all__ = ["StripeAPIClient"]


logger = get_logger("connectors.stripe.api")


_BASE_URL = "https://api.stripe.com"


class StripeAPIClient:
    """Async HTTP client for one Stripe account.

    The merchant's restricted secret key is HTTP Basic-auth username; Stripe
    expects an empty password.
    """

    _MAX_RETRIES_ON_THROTTLE = 1

    def __init__(
        self,
        *,
        api_key: str,
        api_version: str = API_VERSION,
        transport: httpx.BaseTransport | None = None,
        timeout: float = 30.0,
    ) -> None:
        self._api_key = api_key
        self._api_version = api_version
        self._transport = transport
        self._timeout = timeout

    async def get(
        self, path: str, *, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        return await self._request("GET", path, params=params, json=None, form=None)

    async def post_form(
        self, path: str, *, form: dict[str, str]
    ) -> dict[str, Any]:
        """Stripe expects `application/x-www-form-urlencoded` bodies for writes."""
        return await self._request("POST", path, params=None, json=None, form=form)

    async def delete(self, path: str) -> dict[str, Any]:
        return await self._request("DELETE", path, params=None, json=None, form=None)

    async def get_account(self) -> dict[str, Any]:
        """Convenience: GET /v1/account. Returns the merchant's account object."""
        return await self.get("/v1/account")

    async def list_paginated(
        self,
        path: str,
        *,
        page_size: int = 100,
        starting_after: str | None = None,
    ) -> dict[str, Any]:
        """Single page fetch using Stripe's `starting_after` + `limit` cursor.

        Returns the raw response dict including `data`, `has_more`. The caller
        decides whether to fetch the next page.
        """
        params: dict[str, Any] = {"limit": min(max(int(page_size), 1), 100)}
        if starting_after is not None:
            params["starting_after"] = starting_after
        return await self.get(path, params=params)

    # ---------- internal ----------

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None,
        json: dict[str, Any] | None,
        form: dict[str, str] | None,
    ) -> dict[str, Any]:
        url = f"{_BASE_URL}{path}"
        for attempt in range(self._MAX_RETRIES_ON_THROTTLE + 1):
            response = await self._send(method, url, params=params, json=json, form=form)
            if response.status_code != 429:
                return self._handle_response(response, method=method, path=path)

            if attempt >= self._MAX_RETRIES_ON_THROTTLE:
                raise BasefloError(
                    error_code="BF-CONN-STRIPE-004",
                    message="Stripe rate limit exhausted after retry.",
                    status_code=429,
                )
            retry_after = _parse_retry_after(response.headers.get("Retry-After"))
            logger.warning("stripe_rate_limited", retry_after=retry_after)
            await asyncio.sleep(retry_after)

        raise BasefloError(  # pragma: no cover — defensive
            error_code="BF-CONN-STRIPE-004",
            message="Stripe retry loop exited unexpectedly.",
            status_code=500,
        )

    async def _send(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, Any] | None,
        json: dict[str, Any] | None,
        form: dict[str, str] | None,
    ) -> httpx.Response:
        client_kwargs: dict[str, object] = {"timeout": self._timeout}
        if self._transport is not None:
            client_kwargs["transport"] = self._transport
        headers = {
            "Stripe-Version": self._api_version,
            "Accept": "application/json",
        }
        try:
            async with httpx.AsyncClient(**client_kwargs) as client:  # type: ignore[arg-type]
                return await client.request(
                    method,
                    url,
                    params=params,
                    json=json,
                    data=form,
                    headers=headers,
                    auth=(self._api_key, ""),
                )
        except httpx.HTTPError as exc:
            raise BasefloError(
                error_code="BF-CONN-STRIPE-003",
                message=f"Stripe transport error: {exc!r}",
                status_code=502,
                cause=exc,
            ) from exc

    def _handle_response(
        self, response: httpx.Response, *, method: str, path: str
    ) -> dict[str, Any]:
        if response.status_code == 401:
            raise BasefloError(
                error_code="BF-CONN-STRIPE-001",
                message="Stripe rejected the API key (401).",
                status_code=401,
            )
        if response.status_code >= 400:
            raise BasefloError(
                error_code="BF-CONN-STRIPE-003",
                message=(
                    f"Stripe {method} {path} returned status={response.status_code}."
                ),
                status_code=502,
                details={"status": response.status_code, "body": response.text[:500]},
            )
        try:
            data: dict[str, Any] = response.json()
        except ValueError as exc:
            raise BasefloError(
                error_code="BF-CONN-STRIPE-003",
                message="Stripe response was not JSON.",
                status_code=502,
                cause=exc,
            ) from exc
        return data


def _parse_retry_after(value: str | None) -> float:
    if not value:
        return 1.0
    try:
        seconds = float(value)
    except ValueError:
        return 1.0
    return max(0.1, min(seconds, 60.0))
