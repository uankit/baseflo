from __future__ import annotations

import hashlib
import hmac
import logging
import re
from collections.abc import AsyncIterator, Iterable, Mapping
from typing import Any
from urllib.parse import urlencode, urlparse

import httpx
from pydantic import BaseModel

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
from connectors.errors import AuthError, ConfigError, IntrospectError, ReadError
from connectors.registry import register_source
from connectors.types import AuthMethod, Capability, DataType

logger = logging.getLogger("connectors.shopify")

SHOP_DOMAIN_RE = re.compile(r"^[a-z0-9][a-z0-9-]*\.myshopify\.com$")

DEFAULT_READ_SCOPES = [
    "read_analytics",
    "read_assigned_fulfillment_orders",
    "read_customer_events",
    "read_all_cart_transforms",
    "read_validations",
    "read_cash_tracking",
    "read_checkout_branding_settings",
    "read_checkouts",
    "read_custom_fulfillment_services",
    "read_customers",
    "read_customer_merge",
    "read_price_rules",
    "read_discounts",
    "read_discovery",
    "read_draft_orders",
    "read_fulfillments",
    "read_gift_card_transactions",
    "read_gift_cards",
    "read_inventory",
    "read_inventory_shipments",
    "read_inventory_shipments_received_items",
    "read_inventory_transfers",
    "read_locations",
    "read_marketing_integrated_campaigns",
    "read_marketing_events",
    "read_merchant_managed_fulfillment_orders",
    "read_orders",
    "read_payment_terms",
    "read_product_listings",
    "read_products",
    "read_returns",
    "read_shipping",
    "read_content",
    "read_third_party_fulfillment_orders",
    "customer_read_companies",
    "customer_read_draft_orders",
    "customer_read_markets",
    "customer_read_orders",
    "customer_read_quick_sale",
]


class ShopifyCredentials(BaseModel):
    access_token: str
    shop_domain: str
    scope: str | None = None


class ShopifyConfig(BaseModel):
    resource: str
    credentials: ShopifyCredentials


SPEC = SourceSpec(
    kind="shopify",
    display_name="Shopify",
    description="Read commerce, customer, catalog, inventory, and fulfillment data from Shopify.",
    auth_method=AuthMethod.OAUTH2,
    capabilities=frozenset({
        Capability.INTROSPECT,
        Capability.READ,
        Capability.LIST_RESOURCES,
    }),
    config_schema=ShopifyConfig,
)


RESOURCE_METADATA: dict[str, dict[str, Any]] = {
    "orders": {
        "name": "Shopify Orders",
        "description": "Revenue, order status, fulfillment, and customer linkage.",
        "required_scopes": ["read_orders"],
    },
    "order_line_items": {
        "name": "Shopify Order Line Items",
        "description": "SKU/product-level revenue, quantity, discount, and fulfillment state.",
        "required_scopes": ["read_orders"],
    },
    "customers": {
        "name": "Shopify Customers",
        "description": "Customer identity, order count, tags, and lifetime spend.",
        "required_scopes": ["read_customers"],
    },
    "products": {
        "name": "Shopify Products",
        "description": "Catalog, product status, vendor, tags, inventory, and price range.",
        "required_scopes": ["read_products"],
    },
    "product_variants": {
        "name": "Shopify Product Variants",
        "description": "Variant SKUs, prices, inventory item ids, and product linkage.",
        "required_scopes": ["read_products"],
    },
    "locations": {
        "name": "Shopify Locations",
        "description": "Store and fulfillment locations used for inventory and shipping analysis.",
        "required_scopes": ["read_locations"],
    },
    "inventory_levels": {
        "name": "Shopify Inventory Levels",
        "description": "Available inventory by inventory item and location.",
        "required_scopes": ["read_inventory", "read_locations"],
    },
    "transactions": {
        "name": "Shopify Transactions",
        "description": "Payment, refund, capture, and gateway transaction records.",
        "required_scopes": ["read_orders"],
    },
    "fulfillments": {
        "name": "Shopify Fulfillments",
        "description": "Shipment status, tracking, service, and location data.",
        "required_scopes": ["read_orders"],
    },
    "returns": {
        "name": "Shopify Returns",
        "description": "Return status, quantity, approval, and order linkage.",
        "required_scopes": ["read_returns"],
    },
    "return_line_items": {
        "name": "Shopify Return Line Items",
        "description": "Returned items, reasons, notes, and product linkage.",
        "required_scopes": ["read_returns"],
    },
}

SCHEMAS: dict[str, list[ColumnSchema]] = {
    "orders": [
        ColumnSchema("id", DataType.TEXT, nullable=False),
        ColumnSchema("name", DataType.TEXT),
        ColumnSchema("email", DataType.EMAIL),
        ColumnSchema("customer_id", DataType.TEXT),
        ColumnSchema("financial_status", DataType.TEXT),
        ColumnSchema("fulfillment_status", DataType.TEXT),
        ColumnSchema("total_price", DataType.MONEY),
        ColumnSchema("subtotal_price", DataType.MONEY),
        ColumnSchema("currency", DataType.TEXT),
        ColumnSchema("line_items_quantity", DataType.INTEGER),
        ColumnSchema("created_at", DataType.DATETIME),
        ColumnSchema("updated_at", DataType.DATETIME),
        ColumnSchema("processed_at", DataType.DATETIME),
    ],
    "order_line_items": [
        ColumnSchema("id", DataType.TEXT, nullable=False),
        ColumnSchema("order_id", DataType.TEXT),
        ColumnSchema("order_name", DataType.TEXT),
        ColumnSchema("order_created_at", DataType.DATETIME),
        ColumnSchema("product_id", DataType.TEXT),
        ColumnSchema("variant_id", DataType.TEXT),
        ColumnSchema("sku", DataType.TEXT),
        ColumnSchema("name", DataType.TEXT),
        ColumnSchema("title", DataType.TEXT),
        ColumnSchema("vendor", DataType.TEXT),
        ColumnSchema("quantity", DataType.INTEGER),
        ColumnSchema("current_quantity", DataType.INTEGER),
        ColumnSchema("fulfillable_quantity", DataType.INTEGER),
        ColumnSchema("fulfillment_status", DataType.TEXT),
        ColumnSchema("unit_price", DataType.MONEY),
        ColumnSchema("discounted_total", DataType.MONEY),
        ColumnSchema("currency", DataType.TEXT),
    ],
    "customers": [
        ColumnSchema("id", DataType.TEXT, nullable=False),
        ColumnSchema("email", DataType.EMAIL),
        ColumnSchema("first_name", DataType.TEXT),
        ColumnSchema("last_name", DataType.TEXT),
        ColumnSchema("phone", DataType.TEXT),
        ColumnSchema("state", DataType.TEXT),
        ColumnSchema("verified_email", DataType.BOOLEAN),
        ColumnSchema("orders_count", DataType.INTEGER),
        ColumnSchema("total_spent", DataType.MONEY),
        ColumnSchema("currency", DataType.TEXT),
        ColumnSchema("tags", DataType.TEXT),
        ColumnSchema("created_at", DataType.DATETIME),
        ColumnSchema("updated_at", DataType.DATETIME),
    ],
    "products": [
        ColumnSchema("id", DataType.TEXT, nullable=False),
        ColumnSchema("title", DataType.TEXT),
        ColumnSchema("vendor", DataType.TEXT),
        ColumnSchema("product_type", DataType.TEXT),
        ColumnSchema("status", DataType.TEXT),
        ColumnSchema("min_price", DataType.MONEY),
        ColumnSchema("max_price", DataType.MONEY),
        ColumnSchema("currency", DataType.TEXT),
        ColumnSchema("total_inventory", DataType.INTEGER),
        ColumnSchema("tags", DataType.TEXT),
        ColumnSchema("created_at", DataType.DATETIME),
        ColumnSchema("updated_at", DataType.DATETIME),
        ColumnSchema("published_at", DataType.DATETIME),
    ],
    "product_variants": [
        ColumnSchema("id", DataType.TEXT, nullable=False),
        ColumnSchema("product_id", DataType.TEXT),
        ColumnSchema("product_title", DataType.TEXT),
        ColumnSchema("title", DataType.TEXT),
        ColumnSchema("sku", DataType.TEXT),
        ColumnSchema("barcode", DataType.TEXT),
        ColumnSchema("price", DataType.MONEY),
        ColumnSchema("compare_at_price", DataType.MONEY),
        ColumnSchema("inventory_quantity", DataType.INTEGER),
        ColumnSchema("inventory_item_id", DataType.TEXT),
        ColumnSchema("inventory_tracked", DataType.BOOLEAN),
        ColumnSchema("created_at", DataType.DATETIME),
        ColumnSchema("updated_at", DataType.DATETIME),
    ],
    "locations": [
        ColumnSchema("id", DataType.TEXT, nullable=False),
        ColumnSchema("name", DataType.TEXT),
        ColumnSchema("is_active", DataType.BOOLEAN),
        ColumnSchema("fulfills_online_orders", DataType.BOOLEAN),
        ColumnSchema("has_active_inventory", DataType.BOOLEAN),
        ColumnSchema("ships_inventory", DataType.BOOLEAN),
        ColumnSchema("country", DataType.TEXT),
        ColumnSchema("country_code", DataType.TEXT),
        ColumnSchema("province", DataType.TEXT),
        ColumnSchema("province_code", DataType.TEXT),
        ColumnSchema("city", DataType.TEXT),
        ColumnSchema("zip", DataType.TEXT),
    ],
    "inventory_levels": [
        ColumnSchema("location_id", DataType.TEXT),
        ColumnSchema("location_name", DataType.TEXT),
        ColumnSchema("inventory_item_id", DataType.TEXT),
        ColumnSchema("quantity_name", DataType.TEXT),
        ColumnSchema("quantity", DataType.INTEGER),
    ],
    "transactions": [
        ColumnSchema("id", DataType.TEXT, nullable=False),
        ColumnSchema("order_id", DataType.TEXT),
        ColumnSchema("order_name", DataType.TEXT),
        ColumnSchema("kind", DataType.TEXT),
        ColumnSchema("status", DataType.TEXT),
        ColumnSchema("gateway", DataType.TEXT),
        ColumnSchema("formatted_gateway", DataType.TEXT),
        ColumnSchema("amount", DataType.MONEY),
        ColumnSchema("currency", DataType.TEXT),
        ColumnSchema("test", DataType.BOOLEAN),
        ColumnSchema("parent_transaction_id", DataType.TEXT),
        ColumnSchema("created_at", DataType.DATETIME),
    ],
    "fulfillments": [
        ColumnSchema("id", DataType.TEXT, nullable=False),
        ColumnSchema("order_id", DataType.TEXT),
        ColumnSchema("order_name", DataType.TEXT),
        ColumnSchema("status", DataType.TEXT),
        ColumnSchema("location_id", DataType.TEXT),
        ColumnSchema("service_handle", DataType.TEXT),
        ColumnSchema("tracking_company", DataType.TEXT),
        ColumnSchema("tracking_number", DataType.TEXT),
        ColumnSchema("tracking_url", DataType.URL),
        ColumnSchema("estimated_delivery_at", DataType.DATETIME),
        ColumnSchema("created_at", DataType.DATETIME),
        ColumnSchema("updated_at", DataType.DATETIME),
    ],
    "returns": [
        ColumnSchema("id", DataType.TEXT, nullable=False),
        ColumnSchema("order_id", DataType.TEXT),
        ColumnSchema("order_name", DataType.TEXT),
        ColumnSchema("name", DataType.TEXT),
        ColumnSchema("status", DataType.TEXT),
        ColumnSchema("total_quantity", DataType.INTEGER),
        ColumnSchema("created_at", DataType.DATETIME),
        ColumnSchema("approved_at", DataType.DATETIME),
        ColumnSchema("closed_at", DataType.DATETIME),
    ],
    "return_line_items": [
        ColumnSchema("id", DataType.TEXT, nullable=False),
        ColumnSchema("return_id", DataType.TEXT),
        ColumnSchema("return_name", DataType.TEXT),
        ColumnSchema("order_id", DataType.TEXT),
        ColumnSchema("order_name", DataType.TEXT),
        ColumnSchema("line_item_id", DataType.TEXT),
        ColumnSchema("product_id", DataType.TEXT),
        ColumnSchema("variant_id", DataType.TEXT),
        ColumnSchema("sku", DataType.TEXT),
        ColumnSchema("name", DataType.TEXT),
        ColumnSchema("quantity", DataType.INTEGER),
        ColumnSchema("return_reason", DataType.TEXT),
        ColumnSchema("return_reason_note", DataType.TEXT),
        ColumnSchema("customer_note", DataType.TEXT),
    ],
}


SHOP_QUERY = """
query BasefloShopInfo {
  shop {
    id
    name
    myshopifyDomain
    email
    currencyCode
  }
}
"""

PRODUCTS_QUERY = """
query BasefloProducts($first: Int!, $after: String) {
  products(first: $first, after: $after) {
    nodes {
      id
      title
      vendor
      productType
      status
      totalInventory
      tags
      createdAt
      updatedAt
      publishedAt
      priceRangeV2 {
        minVariantPrice {
          amount
          currencyCode
        }
        maxVariantPrice {
          amount
          currencyCode
        }
      }
      variants(first: 100) {
        nodes {
          id
          title
          sku
          barcode
          price
          compareAtPrice
          inventoryQuantity
          inventoryItem {
            id
            tracked
          }
          createdAt
          updatedAt
        }
      }
    }
    pageInfo {
      hasNextPage
      endCursor
    }
  }
}
"""

CUSTOMERS_QUERY = """
query BasefloCustomers($first: Int!, $after: String) {
  customers(first: $first, after: $after) {
    nodes {
      id
      firstName
      lastName
      defaultEmailAddress {
        emailAddress
      }
      defaultPhoneNumber {
        phoneNumber
      }
      state
      verifiedEmail
      numberOfOrders
      amountSpent {
        amount
        currencyCode
      }
      tags
      createdAt
      updatedAt
    }
    pageInfo {
      hasNextPage
      endCursor
    }
  }
}
"""

ORDERS_QUERY = """
query BasefloOrders($first: Int!, $after: String) {
  orders(first: $first, after: $after, query: "status:any") {
    nodes {
      id
      name
      email
      customer {
        id
      }
      displayFinancialStatus
      displayFulfillmentStatus
      totalPriceSet {
        shopMoney {
          amount
          currencyCode
        }
      }
      subtotalPriceSet {
        shopMoney {
          amount
          currencyCode
        }
      }
      subtotalLineItemsQuantity
      createdAt
      updatedAt
      processedAt
    }
    pageInfo {
      hasNextPage
      endCursor
    }
  }
}
"""

ORDERS_LINE_ITEMS_QUERY = """
query BasefloOrderLineItems($first: Int!, $after: String) {
  orders(first: $first, after: $after, query: "status:any") {
    nodes {
      id
      name
      createdAt
      lineItems(first: 100) {
        nodes {
          id
          name
          title
          sku
          vendor
          quantity
          currentQuantity
          fulfillableQuantity
          fulfillmentStatus
          product {
            id
          }
          variant {
            id
          }
          originalUnitPriceSet {
            shopMoney {
              amount
              currencyCode
            }
          }
          discountedTotalSet {
            shopMoney {
              amount
              currencyCode
            }
          }
        }
      }
    }
    pageInfo {
      hasNextPage
      endCursor
    }
  }
}
"""

ORDERS_TRANSACTIONS_QUERY = """
query BasefloOrderTransactions($first: Int!, $after: String) {
  orders(first: $first, after: $after, query: "status:any") {
    nodes {
      id
      name
      transactions(first: 100) {
        id
        kind
        status
        gateway
        formattedGateway
        test
        createdAt
        parentTransaction {
          id
        }
        amountSet {
          shopMoney {
            amount
            currencyCode
          }
        }
      }
    }
    pageInfo {
      hasNextPage
      endCursor
    }
  }
}
"""

ORDERS_FULFILLMENTS_QUERY = """
query BasefloOrderFulfillments($first: Int!, $after: String) {
  orders(first: $first, after: $after, query: "status:any") {
    nodes {
      id
      name
      fulfillments(first: 50) {
        id
        status
        createdAt
        updatedAt
        estimatedDeliveryAt
        location {
          id
        }
        service {
          handle
        }
        trackingInfo(first: 10) {
          company
          number
          url
        }
      }
    }
    pageInfo {
      hasNextPage
      endCursor
    }
  }
}
"""

ORDERS_RETURNS_QUERY = """
query BasefloOrderReturns($first: Int!, $after: String) {
  orders(first: $first, after: $after, query: "status:any") {
    nodes {
      id
      name
      returns(first: 5) {
        nodes {
          id
          name
          status
          totalQuantity
          createdAt
          requestApprovedAt
          closedAt
          returnLineItems(first: 10) {
            nodes {
              ... on ReturnLineItem {
                id
                quantity
                returnReason
                returnReasonNote
                customerNote
                fulfillmentLineItem {
                  lineItem {
                    id
                    name
                    sku
                    product {
                      id
                    }
                    variant {
                      id
                    }
                  }
                }
              }
            }
          }
        }
      }
    }
    pageInfo {
      hasNextPage
      endCursor
    }
  }
}
"""

LOCATIONS_QUERY = """
query BasefloLocations($first: Int!, $after: String) {
  locations(first: $first, after: $after) {
    nodes {
      id
      name
      fulfillsOnlineOrders
      hasActiveInventory
      isActive
      shipsInventory
      address {
        city
        country
        countryCode
        province
        provinceCode
        zip
      }
    }
    pageInfo {
      hasNextPage
      endCursor
    }
  }
}
"""

LOCATIONS_INVENTORY_QUERY = """
query BasefloInventoryLevels($first: Int!, $after: String) {
  locations(first: $first, after: $after) {
    nodes {
      id
      name
      inventoryLevels(first: 100) {
        nodes {
          item {
            id
          }
          quantities(names: ["available", "committed", "incoming", "on_hand", "reserved"]) {
            name
            quantity
          }
        }
      }
    }
    pageInfo {
      hasNextPage
      endCursor
    }
  }
}
"""


@register_source
class ShopifySource(Source):
    """Read-only Shopify Admin connector using OAuth and GraphQL Admin API."""

    spec = SPEC

    def __init__(
        self,
        *,
        client_id: str,
        client_secret: str,
        api_version: str = "2026-04",
        scopes: Iterable[str] | None = None,
        max_rows_per_resource: int = 5000,
    ) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._api_version = api_version
        self._scopes = list(scopes or DEFAULT_READ_SCOPES)
        self._max_rows_per_resource = max_rows_per_resource

    @staticmethod
    def normalize_shop_domain(raw: str) -> str:
        value = raw.strip().lower()
        if not value:
            raise ConfigError(
                message="Shopify shop domain is required",
                code="SHOPIFY_SHOP_REQUIRED",
                status_hint=400,
            )

        parsed = urlparse(value if "://" in value else f"https://{value}")
        host = parsed.netloc or parsed.path.split("/", 1)[0]
        if host == "admin.shopify.com":
            parts = [part for part in parsed.path.split("/") if part]
            if len(parts) >= 2 and parts[0] == "store":
                host = f"{parts[1]}.myshopify.com"
        host = host.removeprefix("admin.").strip("/")
        if "." not in host:
            host = f"{host}.myshopify.com"

        if not SHOP_DOMAIN_RE.fullmatch(host):
            raise ConfigError(
                message="Shopify shop must be a myshopify.com domain",
                code="SHOPIFY_SHOP_INVALID",
                status_hint=400,
            )
        return host

    def authorize_url(
        self, *, redirect_uri: str, state: str, shop_domain: str,
    ) -> str:
        shop = self.normalize_shop_domain(shop_domain)
        params = {
            "client_id": self._client_id,
            "scope": ",".join(self._scopes),
            "redirect_uri": redirect_uri,
            "state": state,
        }
        return f"https://{shop}/admin/oauth/authorize?{urlencode(params)}"

    def verify_callback_hmac(self, params: Mapping[str, Any]) -> bool:
        hmac_value = str(params.get("hmac") or "")
        if not hmac_value:
            return False

        pairs = [
            (key, str(value))
            for key, value in params.items()
            if key not in {"hmac", "signature"}
        ]
        message = "&".join(f"{key}={value}" for key, value in sorted(pairs))
        digest = hmac.new(
            self._client_secret.encode("utf-8"),
            message.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(digest, hmac_value)

    async def exchange_code(
        self,
        *,
        code: str,
        redirect_uri: str,
        shop_domain: str,
    ) -> dict[str, Any]:
        del redirect_uri
        shop = self.normalize_shop_domain(shop_domain)
        payload = {
            "client_id": self._client_id,
            "client_secret": self._client_secret,
            "code": code,
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"https://{shop}/admin/oauth/access_token", data=payload,
            )
        if resp.status_code != 200:
            raise AuthError(
                message=f"Shopify OAuth token exchange failed: {resp.text}",
                code="SHOPIFY_OAUTH_EXCHANGE_FAILED",
                status_hint=400,
            )
        data = resp.json()
        data["shop_domain"] = shop
        return data

    async def authenticate(self, config: dict[str, Any]) -> dict[str, Any]:
        credentials = dict(config.get("credentials") or {})
        access_token = credentials.get("access_token")
        shop_domain = credentials.get("shop_domain")
        if not access_token or not shop_domain:
            raise AuthError(
                message="Shopify credentials are missing an access token or shop domain",
                code="SHOPIFY_CREDENTIALS_INVALID",
                status_hint=401,
            )
        credentials["shop_domain"] = self.normalize_shop_domain(str(shop_domain))
        return {**config, "credentials": credentials}

    async def introspect(self, config: dict[str, Any]) -> SourceSchema:
        resource = self._resource_name(config.get("resource"))
        metadata = RESOURCE_METADATA[resource]
        return SourceSchema(
            tables=[
                TableSchema(
                    name=resource,
                    label=metadata["name"],
                    columns=SCHEMAS[resource],
                    row_count=None,
                )
            ]
        )

    async def read(
        self, config: dict[str, Any], query: SourceQuery,
    ) -> AsyncIterator[Row]:
        resource = self._resource_name(config.get("resource") or query.table)
        credentials = dict(config["credentials"])
        limit = query.limit or self._max_rows_per_resource

        async with httpx.AsyncClient(timeout=45.0) as client:
            if resource == "orders":
                async for node in self._paginate(
                    client, credentials, "orders", ORDERS_QUERY, limit,
                ):
                    yield Row(values=self._flatten_order(node), source_id=node.get("id"))
            elif resource == "order_line_items":
                async for order in self._paginate(
                    client, credentials, "orders", ORDERS_LINE_ITEMS_QUERY, limit,
                ):
                    for node in self._connection_nodes(order.get("lineItems")):
                        values = self._flatten_order_line_item(order, node)
                        yield Row(values=values, source_id=values.get("id"))
            elif resource == "customers":
                async for node in self._paginate(
                    client, credentials, "customers", CUSTOMERS_QUERY, limit,
                ):
                    yield Row(
                        values=self._flatten_customer(node), source_id=node.get("id"),
                    )
            elif resource == "products":
                async for node in self._paginate(
                    client, credentials, "products", PRODUCTS_QUERY, limit,
                ):
                    yield Row(
                        values=self._flatten_product(node), source_id=node.get("id"),
                    )
            elif resource == "product_variants":
                async for product in self._paginate(
                    client, credentials, "products", PRODUCTS_QUERY, limit,
                ):
                    for node in self._connection_nodes(product.get("variants")):
                        values = self._flatten_product_variant(product, node)
                        yield Row(values=values, source_id=values.get("id"))
            elif resource == "locations":
                async for node in self._paginate(
                    client, credentials, "locations", LOCATIONS_QUERY, limit,
                ):
                    yield Row(values=self._flatten_location(node), source_id=node.get("id"))
            elif resource == "inventory_levels":
                async for location in self._paginate(
                    client, credentials, "locations", LOCATIONS_INVENTORY_QUERY, limit,
                ):
                    for node in self._connection_nodes(location.get("inventoryLevels")):
                        for values in self._flatten_inventory_level(location, node):
                            yield Row(
                                values=values,
                                source_id=(
                                    f"{values.get('location_id')}:"
                                    f"{values.get('inventory_item_id')}:"
                                    f"{values.get('quantity_name')}"
                                ),
                            )
            elif resource == "transactions":
                async for order in self._paginate(
                    client, credentials, "orders", ORDERS_TRANSACTIONS_QUERY, limit,
                ):
                    for node in order.get("transactions") or []:
                        values = self._flatten_transaction(order, node)
                        yield Row(values=values, source_id=values.get("id"))
            elif resource == "fulfillments":
                async for order in self._paginate(
                    client, credentials, "orders", ORDERS_FULFILLMENTS_QUERY, limit,
                ):
                    for node in order.get("fulfillments") or []:
                        values = self._flatten_fulfillment(order, node)
                        yield Row(values=values, source_id=values.get("id"))
            elif resource in {"returns", "return_line_items"}:
                async for order in self._paginate(
                    client, credentials, "orders", ORDERS_RETURNS_QUERY, limit, page_size=10,
                ):
                    for node in self._connection_nodes(order.get("returns")):
                        if resource == "returns":
                            values = self._flatten_return(order, node)
                            yield Row(values=values, source_id=values.get("id"))
                        else:
                            for line_item in self._connection_nodes(node.get("returnLineItems")):
                                values = self._flatten_return_line_item(
                                    order, node, line_item,
                                )
                                yield Row(values=values, source_id=values.get("id"))

    async def get_account_info(self, credentials: dict[str, Any]) -> AccountInfo:
        data = await self._graphql(dict(credentials), SHOP_QUERY, {})
        shop = data.get("shop") or {}
        domain = shop.get("myshopifyDomain") or credentials.get("shop_domain")
        external_id = shop.get("id") or domain
        if not external_id:
            raise AuthError(
                message="Shopify shop info did not include an account id",
                code="SHOPIFY_ACCOUNT_INFO_INVALID",
                status_hint=401,
            )
        name = shop.get("name") or domain or "Shopify store"
        label = f"{name} ({domain})" if domain else name
        return AccountInfo(
            external_id=external_id,
            label=label,
            metadata={
                "shop_domain": domain,
                "email": shop.get("email"),
                "currency": shop.get("currencyCode"),
            },
        )

    async def list_resources(
        self, credentials: dict[str, Any],
    ) -> list[AvailableResource]:
        granted = self._granted_scopes(credentials)
        resources: list[AvailableResource] = []
        for external_id, metadata in RESOURCE_METADATA.items():
            required = metadata["required_scopes"]
            if granted and not all(self._scope_granted(granted, scope) for scope in required):
                continue
            resources.append(
                AvailableResource(
                    external_id=external_id,
                    name=metadata["name"],
                    metadata={
                        "description": metadata["description"],
                        "required_scopes": required,
                    },
                )
            )
        return resources

    async def health_check(self, config: dict[str, Any]) -> bool:
        try:
            credentials = dict(config["credentials"])
            await self._graphql(credentials, SHOP_QUERY, {})
            return True
        except Exception:
            return False

    async def _paginate(
        self,
        client: httpx.AsyncClient,
        credentials: dict[str, Any],
        field: str,
        query: str,
        limit: int,
        page_size: int = 100,
    ) -> AsyncIterator[dict[str, Any]]:
        after: str | None = None
        seen = 0
        while seen < limit:
            first = min(page_size, limit - seen)
            data = await self._graphql(
                credentials,
                query,
                {"first": first, "after": after},
                client=client,
            )
            connection = data.get(field) or {}
            for node in connection.get("nodes") or []:
                seen += 1
                yield node
                if seen >= limit:
                    return

            page_info = connection.get("pageInfo") or {}
            if not page_info.get("hasNextPage"):
                return
            after = page_info.get("endCursor")
            if not after:
                return

    async def _graphql(
        self,
        credentials: dict[str, Any],
        query: str,
        variables: dict[str, Any],
        *,
        client: httpx.AsyncClient | None = None,
    ) -> dict[str, Any]:
        access_token = credentials["access_token"]
        shop_domain = self.normalize_shop_domain(str(credentials["shop_domain"]))
        url = f"https://{shop_domain}/admin/api/{self._api_version}/graphql.json"
        headers = {
            "Content-Type": "application/json",
            "X-Shopify-Access-Token": access_token,
        }

        owns_client = client is None
        active_client = client or httpx.AsyncClient(timeout=45.0)
        try:
            resp = await active_client.post(
                url,
                headers=headers,
                json={"query": query, "variables": variables},
            )
        finally:
            if owns_client:
                await active_client.aclose()

        if resp.status_code in {401, 403}:
            raise AuthError(
                message=f"Shopify rejected the request: {resp.text}",
                code="SHOPIFY_AUTH_FAILED",
                status_hint=resp.status_code,
            )
        if resp.status_code != 200:
            raise ReadError(
                message=f"Shopify GraphQL request failed: {resp.text}",
                code="SHOPIFY_GRAPHQL_FAILED",
                status_hint=resp.status_code,
            )

        payload = resp.json()
        if payload.get("errors"):
            raise ReadError(
                message=f"Shopify GraphQL returned errors: {payload['errors']}",
                code="SHOPIFY_GRAPHQL_ERRORS",
                status_hint=400,
            )
        data = payload.get("data")
        if not isinstance(data, dict):
            raise ReadError(
                message="Shopify GraphQL response did not include data",
                code="SHOPIFY_GRAPHQL_NO_DATA",
                status_hint=502,
            )
        return data

    @staticmethod
    def _resource_name(value: Any) -> str:
        resource = str(value or "").strip().lower()
        if resource not in RESOURCE_METADATA:
            raise IntrospectError(
                message=f"Unsupported Shopify resource: {resource or '<missing>'}",
                code="SHOPIFY_RESOURCE_UNSUPPORTED",
                status_hint=400,
            )
        return resource

    @staticmethod
    def _granted_scopes(credentials: dict[str, Any]) -> set[str]:
        raw = credentials.get("scope")
        if not raw:
            return set()
        return {
            scope.strip()
            for scope in str(raw).replace(" ", ",").split(",")
            if scope.strip()
        }

    @staticmethod
    def _scope_granted(granted: set[str], required: str) -> bool:
        if required in granted:
            return True
        if required.startswith("read_"):
            write_scope = required.replace("read_", "write_", 1)
            return write_scope in granted
        return False

    @staticmethod
    def _money_amount(money: dict[str, Any] | None) -> str | None:
        if not money:
            return None
        amount = money.get("amount")
        return str(amount) if amount is not None else None

    @staticmethod
    def _money_currency(money: dict[str, Any] | None) -> str | None:
        if not money:
            return None
        currency = money.get("currencyCode")
        return str(currency) if currency is not None else None

    @staticmethod
    def _tags(tags: Any) -> str | None:
        if isinstance(tags, list):
            return ", ".join(str(tag) for tag in tags if tag)
        if tags is None:
            return None
        return str(tags)

    @staticmethod
    def _connection_nodes(connection: Any) -> list[dict[str, Any]]:
        if not isinstance(connection, dict):
            return []
        nodes = connection.get("nodes")
        if isinstance(nodes, list):
            return [node for node in nodes if isinstance(node, dict)]
        edges = connection.get("edges")
        if isinstance(edges, list):
            return [
                edge.get("node")
                for edge in edges
                if isinstance(edge, dict) and isinstance(edge.get("node"), dict)
            ]
        return []

    def _flatten_order(self, node: dict[str, Any]) -> dict[str, Any]:
        total = (node.get("totalPriceSet") or {}).get("shopMoney") or {}
        subtotal = (node.get("subtotalPriceSet") or {}).get("shopMoney") or {}
        customer = node.get("customer") or {}
        return {
            "id": node.get("id"),
            "name": node.get("name"),
            "email": node.get("email"),
            "customer_id": customer.get("id"),
            "financial_status": node.get("displayFinancialStatus"),
            "fulfillment_status": node.get("displayFulfillmentStatus"),
            "total_price": self._money_amount(total),
            "subtotal_price": self._money_amount(subtotal),
            "currency": self._money_currency(total) or self._money_currency(subtotal),
            "line_items_quantity": node.get("subtotalLineItemsQuantity"),
            "created_at": node.get("createdAt"),
            "updated_at": node.get("updatedAt"),
            "processed_at": node.get("processedAt"),
        }

    def _flatten_order_line_item(
        self, order: dict[str, Any], node: dict[str, Any],
    ) -> dict[str, Any]:
        unit_price = (node.get("originalUnitPriceSet") or {}).get("shopMoney") or {}
        discounted_total = (
            (node.get("discountedTotalSet") or {}).get("shopMoney") or {}
        )
        product = node.get("product") or {}
        variant = node.get("variant") or {}
        return {
            "id": node.get("id"),
            "order_id": order.get("id"),
            "order_name": order.get("name"),
            "order_created_at": order.get("createdAt"),
            "product_id": product.get("id"),
            "variant_id": variant.get("id"),
            "sku": node.get("sku"),
            "name": node.get("name"),
            "title": node.get("title"),
            "vendor": node.get("vendor"),
            "quantity": node.get("quantity"),
            "current_quantity": node.get("currentQuantity"),
            "fulfillable_quantity": node.get("fulfillableQuantity"),
            "fulfillment_status": node.get("fulfillmentStatus"),
            "unit_price": self._money_amount(unit_price),
            "discounted_total": self._money_amount(discounted_total),
            "currency": (
                self._money_currency(unit_price)
                or self._money_currency(discounted_total)
            ),
        }

    def _flatten_customer(self, node: dict[str, Any]) -> dict[str, Any]:
        amount_spent = node.get("amountSpent") or {}
        return {
            "id": node.get("id"),
            "email": (node.get("defaultEmailAddress") or {}).get("emailAddress"),
            "first_name": node.get("firstName"),
            "last_name": node.get("lastName"),
            "phone": (node.get("defaultPhoneNumber") or {}).get("phoneNumber"),
            "state": node.get("state"),
            "verified_email": node.get("verifiedEmail"),
            "orders_count": node.get("numberOfOrders"),
            "total_spent": self._money_amount(amount_spent),
            "currency": self._money_currency(amount_spent),
            "tags": self._tags(node.get("tags")),
            "created_at": node.get("createdAt"),
            "updated_at": node.get("updatedAt"),
        }

    def _flatten_product(self, node: dict[str, Any]) -> dict[str, Any]:
        price_range = node.get("priceRangeV2") or {}
        min_price = price_range.get("minVariantPrice") or {}
        max_price = price_range.get("maxVariantPrice") or {}
        return {
            "id": node.get("id"),
            "title": node.get("title"),
            "vendor": node.get("vendor"),
            "product_type": node.get("productType"),
            "status": node.get("status"),
            "min_price": self._money_amount(min_price),
            "max_price": self._money_amount(max_price),
            "currency": self._money_currency(min_price) or self._money_currency(max_price),
            "total_inventory": node.get("totalInventory"),
            "tags": self._tags(node.get("tags")),
            "created_at": node.get("createdAt"),
            "updated_at": node.get("updatedAt"),
            "published_at": node.get("publishedAt"),
        }

    def _flatten_product_variant(
        self, product: dict[str, Any], node: dict[str, Any],
    ) -> dict[str, Any]:
        inventory_item = node.get("inventoryItem") or {}
        return {
            "id": node.get("id"),
            "product_id": product.get("id"),
            "product_title": product.get("title"),
            "title": node.get("title"),
            "sku": node.get("sku"),
            "barcode": node.get("barcode"),
            "price": node.get("price"),
            "compare_at_price": node.get("compareAtPrice"),
            "inventory_quantity": node.get("inventoryQuantity"),
            "inventory_item_id": inventory_item.get("id"),
            "inventory_tracked": inventory_item.get("tracked"),
            "created_at": node.get("createdAt"),
            "updated_at": node.get("updatedAt"),
        }

    @staticmethod
    def _flatten_location(node: dict[str, Any]) -> dict[str, Any]:
        address = node.get("address") or {}
        return {
            "id": node.get("id"),
            "name": node.get("name"),
            "is_active": node.get("isActive"),
            "fulfills_online_orders": node.get("fulfillsOnlineOrders"),
            "has_active_inventory": node.get("hasActiveInventory"),
            "ships_inventory": node.get("shipsInventory"),
            "country": address.get("country"),
            "country_code": address.get("countryCode"),
            "province": address.get("province"),
            "province_code": address.get("provinceCode"),
            "city": address.get("city"),
            "zip": address.get("zip"),
        }

    @staticmethod
    def _flatten_inventory_level(
        location: dict[str, Any], node: dict[str, Any],
    ) -> list[dict[str, Any]]:
        item = node.get("item") or {}
        rows: list[dict[str, Any]] = []
        for quantity in node.get("quantities") or []:
            rows.append(
                {
                    "location_id": location.get("id"),
                    "location_name": location.get("name"),
                    "inventory_item_id": item.get("id"),
                    "quantity_name": quantity.get("name"),
                    "quantity": quantity.get("quantity"),
                }
            )
        return rows

    def _flatten_transaction(
        self, order: dict[str, Any], node: dict[str, Any],
    ) -> dict[str, Any]:
        amount = (node.get("amountSet") or {}).get("shopMoney") or {}
        parent = node.get("parentTransaction") or {}
        return {
            "id": node.get("id"),
            "order_id": order.get("id"),
            "order_name": order.get("name"),
            "kind": node.get("kind"),
            "status": node.get("status"),
            "gateway": node.get("gateway"),
            "formatted_gateway": node.get("formattedGateway"),
            "amount": self._money_amount(amount),
            "currency": self._money_currency(amount),
            "test": node.get("test"),
            "parent_transaction_id": parent.get("id"),
            "created_at": node.get("createdAt"),
        }

    @staticmethod
    def _flatten_fulfillment(
        order: dict[str, Any], node: dict[str, Any],
    ) -> dict[str, Any]:
        location = node.get("location") or {}
        service = node.get("service") or {}
        tracking = (node.get("trackingInfo") or [{}])[0] or {}
        return {
            "id": node.get("id"),
            "order_id": order.get("id"),
            "order_name": order.get("name"),
            "status": node.get("status"),
            "location_id": location.get("id"),
            "service_handle": service.get("handle"),
            "tracking_company": tracking.get("company"),
            "tracking_number": tracking.get("number"),
            "tracking_url": tracking.get("url"),
            "estimated_delivery_at": node.get("estimatedDeliveryAt"),
            "created_at": node.get("createdAt"),
            "updated_at": node.get("updatedAt"),
        }

    @staticmethod
    def _flatten_return(order: dict[str, Any], node: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": node.get("id"),
            "order_id": order.get("id"),
            "order_name": order.get("name"),
            "name": node.get("name"),
            "status": node.get("status"),
            "total_quantity": node.get("totalQuantity"),
            "created_at": node.get("createdAt"),
            "approved_at": node.get("requestApprovedAt"),
            "closed_at": node.get("closedAt"),
        }

    @staticmethod
    def _flatten_return_line_item(
        order: dict[str, Any],
        return_node: dict[str, Any],
        node: dict[str, Any],
    ) -> dict[str, Any]:
        fulfillment_line_item = node.get("fulfillmentLineItem") or {}
        line_item = fulfillment_line_item.get("lineItem") or {}
        product = line_item.get("product") or {}
        variant = line_item.get("variant") or {}
        return {
            "id": node.get("id"),
            "return_id": return_node.get("id"),
            "return_name": return_node.get("name"),
            "order_id": order.get("id"),
            "order_name": order.get("name"),
            "line_item_id": line_item.get("id"),
            "product_id": product.get("id"),
            "variant_id": variant.get("id"),
            "sku": line_item.get("sku"),
            "name": line_item.get("name"),
            "quantity": node.get("quantity"),
            "return_reason": node.get("returnReason"),
            "return_reason_note": node.get("returnReasonNote"),
            "customer_note": node.get("customerNote"),
        }
