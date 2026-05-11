"""Shopify Admin API HTTP client — GraphQL + REST + rate-limit retry.

Per docs/40-features/CONN-SHOPIFY.md §3.4 + §3.5. Shopify exposes both:

  - GraphQL Admin API at `/admin/api/{version}/graphql.json` — preferred for
    reads (richer types, fewer requests). Cost-based throttling.
  - REST Admin API at `/admin/api/{version}/{resource}.json` — used for
    webhook subscription management (REST is the safer fallback when GraphQL
    coverage lags for a given resource).

A single `ShopifyAPIClient` wraps both transports, shares the access token
+ rate-limit retry logic. `transport` is constructor-injectable so tests
plug in `httpx.MockTransport` without monkey-patching httpx.AsyncClient.
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx

from app.connectors.shopify.catalog import API_VERSION
from app.core.errors import BasefloError
from app.observability.logging import get_logger


__all__ = ["ShopifyAPIClient"]


logger = get_logger("connectors.shopify.api")


class ShopifyAPIClient:
    """Async HTTP client for one Shopify shop.

    Holds the access token + rate-limit retry behaviour. One instance per
    (shop, request) is fine — there's no connection pooling across shops
    intentionally because per-shop rate budgets are independent.
    """

    _MAX_RETRIES_ON_THROTTLE = 1

    def __init__(
        self,
        *,
        shop_domain: str,
        access_token: str,
        api_version: str = API_VERSION,
        transport: httpx.BaseTransport | None = None,
        timeout: float = 30.0,
    ) -> None:
        self._shop = shop_domain
        self._token = access_token
        self._version = api_version
        self._transport = transport
        self._timeout = timeout

    # ---------- public API ----------

    async def graphql(
        self, query: str, *, variables: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Execute a GraphQL query. Returns the `data` block from the response.

        Raises `BF-CONN-SHOPIFY-003` on `errors` arrays, `BF-CONN-SHOPIFY-004`
        on rate-limit exhaustion (after one retry).
        """
        url = f"https://{self._shop}/admin/api/{self._version}/graphql.json"
        body: dict[str, Any] = {"query": query}
        if variables is not None:
            body["variables"] = variables

        response = await self._post_with_retry(url, json=body)

        try:
            payload = response.json()
        except ValueError as exc:
            raise BasefloError(
                error_code="BF-CONN-SHOPIFY-003",
                message="Shopify GraphQL response was not JSON.",
                status_code=502,
                cause=exc,
            ) from exc

        if "errors" in payload and payload["errors"]:
            raise BasefloError(
                error_code="BF-CONN-SHOPIFY-003",
                message=f"Shopify GraphQL returned errors: {payload['errors']!r}",
                status_code=502,
                details={"errors": payload["errors"]},
            )
        data = payload.get("data")
        if not isinstance(data, dict):
            raise BasefloError(
                error_code="BF-CONN-SHOPIFY-003",
                message="Shopify GraphQL response missing `data` block.",
                status_code=502,
            )
        return data

    async def rest_get(self, path: str) -> dict[str, Any]:
        return await self._rest_request("GET", path, json=None)

    async def rest_post(self, path: str, *, json: dict[str, Any]) -> dict[str, Any]:
        return await self._rest_request("POST", path, json=json)

    async def rest_request_put(
        self, path: str, *, json: dict[str, Any]
    ) -> dict[str, Any]:
        return await self._rest_request("PUT", path, json=json)

    async def rest_delete(self, path: str) -> None:
        url = self._rest_url(path)
        response = await self._send_with_retry("DELETE", url, json=None)
        if response.status_code not in {200, 204}:
            raise BasefloError(
                error_code="BF-CONN-SHOPIFY-003",
                message=(
                    f"Shopify REST DELETE {path} returned status={response.status_code}."
                ),
                status_code=502,
            )

    # ---------- internal ----------

    def _rest_url(self, path: str) -> str:
        # `path` is always relative to the version prefix (e.g., "webhooks.json").
        return f"https://{self._shop}/admin/api/{self._version}/{path.lstrip('/')}"

    async def _rest_request(
        self, method: str, path: str, *, json: dict[str, Any] | None
    ) -> dict[str, Any]:
        url = self._rest_url(path)
        response = await self._send_with_retry(method, url, json=json)
        if response.status_code >= 400:
            raise BasefloError(
                error_code="BF-CONN-SHOPIFY-003",
                message=(
                    f"Shopify REST {method} {path} returned status={response.status_code}."
                ),
                status_code=502,
                details={"status": response.status_code, "body": response.text[:500]},
            )
        try:
            data: dict[str, Any] = response.json()
        except ValueError as exc:
            raise BasefloError(
                error_code="BF-CONN-SHOPIFY-003",
                message="Shopify REST response was not JSON.",
                status_code=502,
                cause=exc,
            ) from exc
        return data

    async def _post_with_retry(
        self, url: str, *, json: dict[str, Any]
    ) -> httpx.Response:
        return await self._send_with_retry("POST", url, json=json)

    async def _send_with_retry(
        self,
        method: str,
        url: str,
        *,
        json: dict[str, Any] | None,
    ) -> httpx.Response:
        """Send a request; retry once on HTTP 429.

        Two consecutive 429s → BF-CONN-SHOPIFY-004. Real production rate
        limiting (token bucket, predictive throttle from
        `extensions.cost.throttleStatus`) is optional polish.
        """
        for attempt in range(self._MAX_RETRIES_ON_THROTTLE + 1):
            response = await self._send_once(method, url, json=json)
            if response.status_code != 429:
                return response

            if attempt >= self._MAX_RETRIES_ON_THROTTLE:
                raise BasefloError(
                    error_code="BF-CONN-SHOPIFY-004",
                    message="Shopify rate limit exhausted after retry.",
                    status_code=429,
                    details={"shop_domain": self._shop},
                )
            retry_after = _parse_retry_after(response.headers.get("Retry-After"))
            logger.warning(
                "shopify_rate_limited",
                shop_domain=self._shop,
                retry_after=retry_after,
            )
            await asyncio.sleep(retry_after)

        # Unreachable: the loop either returns or raises.
        raise BasefloError(  # pragma: no cover — defensive
            error_code="BF-CONN-SHOPIFY-004",
            message="Shopify retry loop exited unexpectedly.",
            status_code=500,
        )

    async def _send_once(
        self, method: str, url: str, *, json: dict[str, Any] | None
    ) -> httpx.Response:
        client_kwargs: dict[str, object] = {"timeout": self._timeout}
        if self._transport is not None:
            client_kwargs["transport"] = self._transport
        headers = {
            "X-Shopify-Access-Token": self._token,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        try:
            async with httpx.AsyncClient(**client_kwargs) as client:  # type: ignore[arg-type]
                return await client.request(method, url, json=json, headers=headers)
        except httpx.HTTPError as exc:
            raise BasefloError(
                error_code="BF-CONN-SHOPIFY-003",
                message=f"Shopify transport error: {exc!r}",
                status_code=502,
                cause=exc,
            ) from exc


def _parse_retry_after(value: str | None) -> float:
    """Parse a `Retry-After` header value in seconds. Defaults to 2.0s."""
    if not value:
        return 2.0
    try:
        seconds = float(value)
    except ValueError:
        return 2.0
    return max(0.1, min(seconds, 60.0))
