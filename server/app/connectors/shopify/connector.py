"""ShopifyConnector — implements the Connector Protocol against the Admin API.

Per docs/40-features/CONN-SHOPIFY.md.

Construction takes no required args (the registry's no-args check). Per-shop
state — `shop_domain`, `access_token`, optional `httpx.BaseTransport` for
tests — flows through `ConnectorToken.metadata` and is composed into a
`ShopifyAPIClient` per call.

Reads use GraphQL (richer types, fewer requests). Webhook subscription
management uses REST (safer fallback where GraphQL coverage lags per resource).
Writes are not available in v1.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime
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
from app.connectors.shopify.api import ShopifyAPIClient
from app.connectors.shopify.catalog import (
    API_VERSION,
    TABLE_NAMES,
    build_catalog,
    table_by_name,
)
from app.core.errors import BasefloError
from app.observability.logging import get_logger


logger = get_logger("connectors.shopify")


# Cursor-based GraphQL queries. Pinned to `catalog.API_VERSION`. Response fields
# match the catalog's column names after the `_graphql_node_to_row_*` helpers
# flatten nested money/address objects.

_QUERY_CUSTOMERS = """
query Customers($cursor: String, $first: Int!) {
  customers(first: $first, after: $cursor) {
    edges {
      cursor
      node {
        id
        email
        firstName
        lastName
        phone
        verifiedEmail
        state
        tags
        note
        ordersCount
        amountSpent { amount currencyCode }
        defaultAddress { address1 city province zip country }
        createdAt
        updatedAt
      }
    }
    pageInfo { hasNextPage endCursor }
  }
}
"""

_QUERY_ORDERS = """
query Orders($cursor: String, $first: Int!) {
  orders(first: $first, after: $cursor) {
    edges {
      cursor
      node {
        id
        name
        email
        phone
        customer { id }
        totalPriceSet { shopMoney { amount currencyCode } }
        subtotalPriceSet { shopMoney { amount } }
        totalTaxSet { shopMoney { amount } }
        displayFinancialStatus
        displayFulfillmentStatus
        tags
        lineItems(first: 50) {
          edges { node { title quantity } }
        }
        createdAt
        updatedAt
        processedAt
        cancelledAt
      }
    }
    pageInfo { hasNextPage endCursor }
  }
}
"""

_QUERY_PRODUCTS = """
query Products($cursor: String, $first: Int!) {
  products(first: $first, after: $cursor) {
    edges {
      cursor
      node {
        id
        title
        handle
        productType
        vendor
        status
        tags
        descriptionHtml
        totalInventory
        variants(first: 100) {
          edges { node { id title sku price inventoryQuantity } }
        }
        createdAt
        updatedAt
        publishedAt
      }
    }
    pageInfo { hasNextPage endCursor }
  }
}
"""

_QUERY_HEALTH = "query Health { shop { id name } }"


_QUERY_BY_TABLE: dict[str, str] = {
    "customers": _QUERY_CUSTOMERS,
    "orders": _QUERY_ORDERS,
    "products": _QUERY_PRODUCTS,
}


# Webhook topics subscribed by default per docs/40-features/CONN-SHOPIFY.md §3.6.
_DEFAULT_WEBHOOK_TOPICS: tuple[str, ...] = (
    "customers/create", "customers/update", "customers/delete",
    "orders/create", "orders/updated", "orders/cancelled", "orders/paid",
    "products/create", "products/update", "products/delete",
)


class ShopifyConnector:
    """Shopify Admin API connector. One instance per registration; per-shop
    state arrives via `ConnectorToken.metadata`."""

    metadata: ConnectorMetadata = ConnectorMetadata(
        name="shopify",
        display_name="Shopify",
        version="1.0.0",
        protocol_version="1.0",
        auth_kind=AuthKind.OAUTH2,
        capabilities=ConnectorCapabilities(
            can_introspect=True,
            can_read=True,
            can_write=False,
            can_subscribe_webhooks=True,
            supports_pagination=True,
            supports_streaming=True,
            requires_periodic_sync=False,        # webhooks are real-time
            write_back_canonical_only=True,
        ),
        required_scopes=[
            "read_customers", "read_orders", "read_products",
        ],
        optional_scopes=[
            "read_inventory",
            "write_customers", "write_orders", "write_products",
        ],
        docs_url="https://shopify.dev/docs/api/admin-graphql",
    )

    # ---------- auth ----------

    async def authenticate(self, credentials: AuthCredentials) -> ConnectorToken:
        shop_secret = credentials.payload.get("shop_domain")
        token_secret = credentials.payload.get("access_token")
        if shop_secret is None or token_secret is None:
            raise BasefloError(
                error_code="BF-CONN-SHOPIFY-001",
                message=(
                    "Shopify connector requires `shop_domain` and `access_token` "
                    "in credentials.payload."
                ),
                status_code=400,
            )
        shop_domain = shop_secret.get_secret_value()
        access_token = token_secret.get_secret_value()

        # Validate the credentials by issuing the cheapest query Shopify offers.
        client = ShopifyAPIClient(
            shop_domain=shop_domain,
            access_token=access_token,
            transport=_transport_from_payload(credentials),
        )
        try:
            await client.graphql(_QUERY_HEALTH)
        except BasefloError as exc:
            # Surface as auth-specific code; the underlying API error is preserved
            # via `cause` for log correlation.
            raise BasefloError(
                error_code="BF-CONN-SHOPIFY-001",
                message="Shopify authentication failed; access_token rejected.",
                status_code=401,
                details={"shop_domain": shop_domain},
                cause=exc,
            ) from exc

        return ConnectorToken(
            connector_name=self.metadata.name,
            token_id=UUID("01970000-0000-7000-8000-000000000000"),
            metadata={
                "shop_domain": shop_domain,
                "api_version": API_VERSION,
                # Token persistence: the Token Vault re-stamps `token_id` on
                # save and stores the access_token encrypted-at-rest with the
                # `credentials.payload["access_token"]` for every call.
                "_access_token": access_token,
            },
        )

    async def revoke(self, token: ConnectorToken) -> None:
        # Shopify has no provider-side revoke; uninstalling the app on the
        # merchant's end is what invalidates the token. The connector's
        # responsibility is to drop the cached token; the Token Vault
        # zeroises the encrypted bytes on storage delete.
        _ = token

    # ---------- introspection + sampling ----------

    async def introspect_schema(self, token: ConnectorToken) -> SourceSchema:
        shop_domain = token.metadata.get("shop_domain")
        return build_catalog(shop_domain=str(shop_domain) if shop_domain else None)

    async def sample_rows(
        self, token: ConnectorToken, table: str, n: int
    ) -> list[Row]:
        if table_by_name(table) is None:
            raise BasefloError(
                error_code="BF-CONN-SHOPIFY-005",
                message=(
                    f"Shopify connector does not expose table {table!r}. "
                    f"Known tables: {sorted(TABLE_NAMES)}."
                ),
                status_code=400,
            )
        n = max(1, min(int(n), 250))  # Shopify caps at 250 per page
        client = self._client(token)
        data = await client.graphql(
            _QUERY_BY_TABLE[table], variables={"cursor": None, "first": n}
        )
        edges = _edges_from_data(data, table)
        return [Row(values=_flatten_node(table, edge["node"])) for edge in edges]

    async def read(
        self, token: ConnectorToken, query: SourceQuery
    ) -> AsyncIterator[Row]:
        if table_by_name(query.table) is None:
            raise BasefloError(
                error_code="BF-CONN-SHOPIFY-005",
                message=(
                    f"Shopify connector does not expose table {query.table!r}. "
                    f"Known tables: {sorted(TABLE_NAMES)}."
                ),
                status_code=400,
            )
        return self._stream(token, query)

    async def _stream(
        self, token: ConnectorToken, query: SourceQuery
    ) -> AsyncIterator[Row]:
        client = self._client(token)
        cursor: str | None = query.cursor
        page_size = min(int(query.limit) if query.limit else 50, 250)
        emitted = 0
        limit = int(query.limit) if query.limit else None

        while True:
            data = await client.graphql(
                _QUERY_BY_TABLE[query.table],
                variables={"cursor": cursor, "first": page_size},
            )
            edges = _edges_from_data(data, query.table)
            for edge in edges:
                yield Row(values=_flatten_node(query.table, edge["node"]))
                emitted += 1
                if limit is not None and emitted >= limit:
                    return

            page_info = _page_info_from_data(data, query.table)
            if not page_info.get("hasNextPage"):
                return
            next_cursor = page_info.get("endCursor")
            if not isinstance(next_cursor, str):
                return
            cursor = next_cursor


    async def write(
        self, token: ConnectorToken, mutation: SourceMutation
    ) -> WriteResult:
        """REST-based write-back per docs/40-features/CONN-SHOPIFY.md §3.7.

        Routes by `mutation.table` to the right Shopify resource. The
        The write router consults the EntityReconciliationPlan to decide
        which connector receives the write.
        """
        if table_by_name(mutation.table) is None:
            raise BasefloError(
                error_code="BF-CONN-SHOPIFY-005",
                message=(
                    f"ShopifyConnector.write does not expose table {mutation.table!r}. "
                    f"Known tables: {sorted(TABLE_NAMES)}."
                ),
                status_code=400,
            )
        client = self._client(token)
        path = f"{mutation.table}.json"

        if mutation.op == "create":
            if mutation.values is None:
                raise BasefloError(
                    error_code="BF-CONN-SHOPIFY-003",
                    message="Shopify create requires `values`.",
                    status_code=400,
                )
            singular = mutation.table.rstrip("s")
            response = await client.rest_post(
                path, json={singular: dict(mutation.values)},
            )
            new_id = _id_from_response(response, singular)
            return WriteResult(success=True, affected_rows=1, new_id=new_id)

        if mutation.op == "update":
            if not mutation.where or "id" not in mutation.where:
                raise BasefloError(
                    error_code="BF-CONN-SHOPIFY-003",
                    message="Shopify update requires `where['id']` (numeric Shopify id).",
                    status_code=400,
                )
            if mutation.values is None:
                raise BasefloError(
                    error_code="BF-CONN-SHOPIFY-003",
                    message="Shopify update requires `values`.",
                    status_code=400,
                )
            row_id = mutation.where["id"]
            singular = mutation.table.rstrip("s")
            update_path = f"{mutation.table}/{row_id}.json"
            response = await client.rest_request_put(
                update_path, json={singular: dict(mutation.values)},
            )
            return WriteResult(success=True, affected_rows=1, new_id=str(row_id))

        if mutation.op == "delete":
            if not mutation.where or "id" not in mutation.where:
                raise BasefloError(
                    error_code="BF-CONN-SHOPIFY-003",
                    message="Shopify delete requires `where['id']`.",
                    status_code=400,
                )
            row_id = mutation.where["id"]
            await client.rest_delete(f"{mutation.table}/{row_id}.json")
            return WriteResult(success=True, affected_rows=1, new_id=None)

        raise BasefloError(
            error_code="BF-CONN-SHOPIFY-003",
            message=f"Unsupported mutation op: {mutation.op!r}.",
            status_code=400,
        )

    # ---------- webhooks ----------

    async def webhook_subscribe(
        self,
        token: ConnectorToken,
        events: list[str],
        callback_url: str,
    ) -> Subscription:
        topics = events or list(_DEFAULT_WEBHOOK_TOPICS)
        client = self._client(token)
        subscription_ids: list[str] = []
        for topic in topics:
            body = {
                "webhook": {
                    "topic": topic,
                    "address": callback_url,
                    "format": "json",
                }
            }
            response = await client.rest_post("webhooks.json", json=body)
            wh_id = _webhook_id(response)
            subscription_ids.append(wh_id)
            logger.info(
                "shopify_webhook_subscribed",
                shop_domain=str(token.metadata.get("shop_domain")),
                topic=topic,
                webhook_id=wh_id,
            )

        # The framework's `Subscription.id` carries the comma-joined webhook ids;
        # `webhook_unsubscribe` splits + DELETEs each.
        return Subscription(
            id=",".join(subscription_ids),
            events=topics,
            callback_url=callback_url,
            expires_at=None,
        )

    async def webhook_unsubscribe(
        self, token: ConnectorToken, subscription: Subscription,
    ) -> None:
        """DELETE every webhook id carried in `subscription.id` (comma-joined).

        Idempotent: missing ids are tolerated (Shopify also auto-removes
        webhooks when the app is uninstalled).
        """
        if not subscription.id:
            return
        client = self._client(token)
        for raw_id in subscription.id.split(","):
            wh_id = raw_id.strip()
            if not wh_id:
                continue
            try:
                await client.rest_delete(f"webhooks/{wh_id}.json")
            except BasefloError as exc:
                if "404" in (exc.message or ""):
                    continue
                raise
            logger.info(
                "shopify_webhook_unsubscribed",
                shop_domain=str(token.metadata.get("shop_domain")),
                webhook_id=wh_id,
            )

    # ---------- health ----------

    async def health_check(self, token: ConnectorToken) -> HealthStatus:
        import time  # noqa: PLC0415 — local to keep top-of-file imports tight

        client = self._client(token)
        started = time.perf_counter()
        try:
            await client.graphql(_QUERY_HEALTH)
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

    def _client(self, token: ConnectorToken) -> ShopifyAPIClient:
        shop_domain = token.metadata.get("shop_domain")
        access_token = token.metadata.get("_access_token")
        if not isinstance(shop_domain, str) or not isinstance(access_token, str):
            raise BasefloError(
                error_code="BF-CONN-SHOPIFY-001",
                message=(
                    "Shopify token missing `shop_domain` / `_access_token` in metadata. "
                    "Token Vault must populate these at call time."
                ),
                status_code=500,
            )
        api_version_value = token.metadata.get("api_version")
        api_version = (
            str(api_version_value) if isinstance(api_version_value, str) else API_VERSION
        )
        transport = token.metadata.get("_transport")
        return ShopifyAPIClient(
            shop_domain=shop_domain,
            access_token=access_token,
            api_version=api_version,
            transport=transport if isinstance(transport, httpx.BaseTransport) else None,
        )


# ---------- module-level helpers ----------


def _transport_from_payload(creds: AuthCredentials) -> httpx.BaseTransport | None:
    """Tests inject a `MockTransport` via `payload["_transport"]` — a dict-of-
    SecretStr can't carry an arbitrary object, so we look it up off the model
    via attribute access. Production callers never supply this key; it's a
    test seam, not a public field."""
    return getattr(creds, "_transport", None)


def _edges_from_data(data: dict[str, Any], table: str) -> list[dict[str, Any]]:
    block = data.get(table)
    if not isinstance(block, dict):
        raise BasefloError(
            error_code="BF-CONN-SHOPIFY-003",
            message=f"Shopify GraphQL response missing `{table}` block.",
            status_code=502,
        )
    edges = block.get("edges") or []
    if not isinstance(edges, list):
        raise BasefloError(
            error_code="BF-CONN-SHOPIFY-003",
            message=f"Shopify GraphQL `{table}.edges` is not a list.",
            status_code=502,
        )
    return [e for e in edges if isinstance(e, dict)]


def _page_info_from_data(data: dict[str, Any], table: str) -> dict[str, Any]:
    block = data.get(table)
    if not isinstance(block, dict):
        return {}
    page_info = block.get("pageInfo")
    return page_info if isinstance(page_info, dict) else {}


def _id_from_response(response: dict[str, Any], singular: str) -> str | None:
    """Extract the new resource id from a Shopify create response.

    Shape: `{"customer": {"id": 12345, ...}}` for `customers.json`.
    """
    body = response.get(singular)
    if not isinstance(body, dict):
        return None
    new_id = body.get("id")
    return str(new_id) if new_id is not None else None


def _webhook_id(response: dict[str, Any]) -> str:
    """Extract the webhook id from Shopify's REST response shape:
    `{"webhook": {"id": 1234567, …}}`. Stringified for the framework's
    `Subscription.id: str` contract."""
    wh = response.get("webhook")
    if not isinstance(wh, dict):
        raise BasefloError(
            error_code="BF-CONN-SHOPIFY-003",
            message="Shopify webhook subscription response missing `webhook` key.",
            status_code=502,
        )
    wh_id = wh.get("id")
    if wh_id is None:
        raise BasefloError(
            error_code="BF-CONN-SHOPIFY-003",
            message="Shopify webhook subscription response missing `webhook.id`.",
            status_code=502,
        )
    return str(wh_id)


# ---------- node → row flatteners ----------


def _flatten_node(table: str, node: dict[str, Any]) -> dict[str, Any]:
    """Map Shopify's GraphQL node shape to our flat catalog row shape.

    Per docs/40-features/CONN-SHOPIFY.md §3.4: nested money objects
    (`amountSpent { amount currencyCode }`) become two columns
    (`amount_spent_amount`, `amount_spent_currency_code`); nested objects
    that don't decompose (addresses, line items) ride along as JSON cell
    values so the agent layer can decide downstream.
    """
    if table == "customers":
        return _flatten_customer(node)
    if table == "orders":
        return _flatten_order(node)
    if table == "products":
        return _flatten_product(node)
    raise BasefloError(  # defensive — table_by_name gates this above
        error_code="BF-CONN-SHOPIFY-005",
        message=f"Unknown table for flatten: {table!r}",
        status_code=500,
    )


def _flatten_customer(n: dict[str, Any]) -> dict[str, Any]:
    amount = n.get("amountSpent") or {}
    return {
        "id": n.get("id"),
        "email": n.get("email"),
        "first_name": n.get("firstName"),
        "last_name": n.get("lastName"),
        "phone": n.get("phone"),
        "verified_email": bool(n.get("verifiedEmail", False)),
        "state": _norm_lower_or_none(n.get("state")),
        "tags": list(n.get("tags") or []),
        "note": n.get("note"),
        "orders_count": int(n.get("ordersCount") or 0),
        "amount_spent_amount": amount.get("amount"),
        "amount_spent_currency_code": amount.get("currencyCode"),
        "default_address": n.get("defaultAddress"),
        "created_at": n.get("createdAt"),
        "updated_at": n.get("updatedAt"),
    }


def _flatten_order(n: dict[str, Any]) -> dict[str, Any]:
    total = (n.get("totalPriceSet") or {}).get("shopMoney") or {}
    subtotal = (n.get("subtotalPriceSet") or {}).get("shopMoney") or {}
    tax = (n.get("totalTaxSet") or {}).get("shopMoney") or {}
    customer = n.get("customer") or {}
    line_items_block = n.get("lineItems") or {}
    line_items = [edge["node"] for edge in line_items_block.get("edges", []) if isinstance(edge, dict)]
    return {
        "id": n.get("id"),
        "name": n.get("name"),
        "email": n.get("email"),
        "phone": n.get("phone"),
        "customer_id": customer.get("id"),
        "total_price_amount": total.get("amount"),
        "total_price_currency_code": total.get("currencyCode"),
        "subtotal_price_amount": subtotal.get("amount"),
        "total_tax_amount": tax.get("amount"),
        "financial_status": _norm_lower_or_none(n.get("displayFinancialStatus")),
        "fulfillment_status": _norm_lower_or_none(n.get("displayFulfillmentStatus")),
        "tags": list(n.get("tags") or []),
        "line_items": line_items,
        "created_at": n.get("createdAt"),
        "updated_at": n.get("updatedAt"),
        "processed_at": n.get("processedAt"),
        "cancelled_at": n.get("cancelledAt"),
    }


def _flatten_product(n: dict[str, Any]) -> dict[str, Any]:
    variants_block = n.get("variants") or {}
    variants = [edge["node"] for edge in variants_block.get("edges", []) if isinstance(edge, dict)]
    return {
        "id": n.get("id"),
        "title": n.get("title"),
        "handle": n.get("handle"),
        "product_type": n.get("productType"),
        "vendor": n.get("vendor"),
        "status": _norm_lower_or_none(n.get("status")),
        "tags": list(n.get("tags") or []),
        "description_html": n.get("descriptionHtml"),
        "variants": variants,
        "total_inventory": n.get("totalInventory"),
        "created_at": n.get("createdAt"),
        "updated_at": n.get("updatedAt"),
        "published_at": n.get("publishedAt"),
    }


def _norm_lower_or_none(value: Any) -> str | None:
    """Shopify GraphQL emits enum values like `PAID`; the catalog's enum
    declarations are lower-case (`paid`). Normalise here so downstream
    `ColumnClassifier` sees stable values."""
    if value is None:
        return None
    return str(value).lower()


_ = json
