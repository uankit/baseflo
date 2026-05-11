# `CONN-SHOPIFY` — Shopify Admin API Connector

Status: M2. The first webhook-driven moat connector. Validates two-way sync against a real merchant tenant.

---

## 1. Overview

A tier-1 native connector for Shopify's Admin API. Reads via GraphQL (cheaper, richer types); writes + webhook subscriptions via REST (Shopify's GraphQL write surface is incomplete in 2026-04). Webhook ingestion is HMAC-verified per Shopify's documented signing scheme so the `/api/v1/connectors/shopify/webhooks` endpoint can trust the source on every callback.

**Resources surfaced (M2 scope):** `customers`, `orders`, `products`. Variants and inventory ride along as JSON aggregates on `products` for now; M3 splits them into separate tables.

## 2. High-Level Design

```
┌──────────────┐     OAuth2 install      ┌─────────────────┐
│ Merchant UI  │ ───────────────────────▶│  Baseflo API    │
└──────────────┘                          │   /oauth/...    │
                                          └────┬────────────┘
                                               │ token exchange
                                               ▼
                                          ┌─────────────────┐
                                          │ ShopifyConnector│
                                          │   .authenticate │
                                          └────┬────────────┘
                                               │ ConnectorToken
                                               │ (encrypted at rest in M3)
                                               ▼
                                          ┌─────────────────────────┐
   read path  ──── GraphQL Admin API ────▶│ shop.myshopify.com      │
                                          │ /admin/api/2026-04/...  │
   write path ──── REST + GraphQL  ──────▶│                         │
                                          └─────────────────────────┘
                                               │
                                               │ webhooks
                                               ▼
                                          ┌─────────────────────────┐
                                          │ POST /api/v1/connectors │
                                          │  /shopify/webhooks      │
                                          │  (HMAC verify → ingest) │
                                          └─────────────────────────┘
```

## 3. Low-Level Design

### 3.1 Module Layout

```
server/app/connectors/shopify/
├── __init__.py          # registration with ConnectorRegistry
├── connector.py         # ShopifyConnector implementing Connector Protocol
├── auth.py              # build_install_url, exchange_code_for_token, verify_install_hmac
├── api.py               # ShopifyAPIClient — httpx + GraphQL + REST + rate-limit retry
├── catalog.py           # static SourceTable defs for customers/orders/products
└── webhook.py           # verify_webhook — HMAC-SHA256 body verification
```

### 3.2 Auth

`AuthKind.OAUTH2`. The OAuth dance lives in `app/api/v1/routes/oauth/shopify.py` (M2 follow-up); the connector's `authenticate(...)` accepts a payload that's already past the dance:

```python
AuthCredentials(payload={
    "shop_domain": SecretStr("acme.myshopify.com"),
    "access_token": SecretStr("shpat_..."),
})
```

`authenticate(...)` validates by issuing the GraphQL `shop { id name }` query. On 200 it returns a `ConnectorToken` with non-secret metadata `{shop_domain, scopes_granted}`. On 401/403 it raises `BF-CONN-SHOPIFY-001`.

**App-level config** (env, set once per Baseflo deployment, not per tenant):

| Env var | Purpose |
|---|---|
| `BASEFLO_SHOPIFY_CLIENT_ID` | Shopify app's API key |
| `BASEFLO_SHOPIFY_CLIENT_SECRET` | Shopify app's shared secret. Used for OAuth exchange + webhook HMAC verification. |
| `BASEFLO_SHOPIFY_API_VERSION` | Default `2026-04`. Pinned to a quarterly Shopify version. |

### 3.3 Static Catalog

Shopify's data model is fixed per API version, so `introspect_schema` returns a deterministic catalog rather than discovering tables. Three `SourceTable`s ship M2:

| Table | Columns (selected) | Primary key |
|---|---|---|
| `customers` | `id, email, first_name, last_name, phone, verified_email, state, tags (json), note, orders_count, amount_spent_amount, amount_spent_currency_code, default_address (json), created_at, updated_at` | `id` |
| `orders` | `id, name, email, phone, customer_id (FK), total_price_amount, total_price_currency_code, subtotal_price_amount, total_tax_amount, financial_status, fulfillment_status, tags (json), line_items (json), created_at, updated_at, processed_at, cancelled_at` | `id` |
| `products` | `id, title, handle, product_type, vendor, status, tags (json), description_html, variants (json), total_inventory, created_at, updated_at, published_at` | `id` |

**Connector-native `source_type` values used:**

| `source_type` | Maps to (after agent classification) |
|---|---|
| `id_gid` | Shopify GID string (`gid://shopify/Customer/12345`); `SemanticType.IDENTITY` + `PhysicalType.VARCHAR` |
| `email` | `SemanticType.PII_EMAIL` |
| `phone` | `SemanticType.PII_PHONE` |
| `string` | `SemanticType.FREE_TEXT` or `CATEGORY` per cardinality |
| `text` | `FREE_TEXT` (long) |
| `integer` | `SemanticType.COUNT` |
| `decimal` | `SemanticType.MONEY` (paired with `_currency_code` column) |
| `boolean` | `SemanticType.BOOLEAN` |
| `datetime` | `SemanticType.TEMPORAL` |
| `enum_OrderFinancialStatus` | `SemanticType.STATUS` (enum_values populated from Shopify's documented set) |
| `json` | `PhysicalType.JSONB`; `SemanticType.DERIVED` |

### 3.4 GraphQL queries

```graphql
query Customers($cursor: String) {
  customers(first: 50, after: $cursor) {
    edges {
      node { id email firstName lastName phone verifiedEmail state
             tags note ordersCount amountSpent { amount currencyCode }
             defaultAddress { address1 city province zip country }
             createdAt updatedAt }
    }
    pageInfo { hasNextPage endCursor }
  }
}
```

Analogous queries for `orders` and `products`. Each one yields a flat row dict per node, with nested money/address objects denormalised into `_amount`/`_currency_code` pairs and lists/objects serialised as JSON-shaped `dict` / `list` cell values.

### 3.5 Pagination + rate limiting

Shopify GraphQL is cost-based: each query consumes points; `extensions.cost.throttleStatus` returns `currentlyAvailable / maximumAvailable / restoreRate`. M2 strategy:

- **Pagination**: standard cursor (`pageInfo.endCursor`). Yield one `Row` per node.
- **Rate-limit**: catch HTTP 429 + GraphQL throttle errors. Sleep `Retry-After` (or `cost.throttleStatus.currentlyAvailable / restoreRate` seconds) and retry once. Two consecutive throttles → raise `BF-CONN-SHOPIFY-004`.

### 3.6 Webhooks

`ShopifyConnector.webhook_subscribe(...)` POSTs to `/admin/api/2026-04/webhooks.json` per topic. We register one subscription per (project, topic) pair; the framework's `Subscription.id` carries Shopify's numeric webhook id as a string for later `webhook_unsubscribe`.

**Default topics for M2:**

```
customers/create, customers/update, customers/delete,
orders/create, orders/updated, orders/cancelled, orders/paid,
products/create, products/update, products/delete
```

**HMAC verification** ([`shopify.dev/docs/apps/webhooks/configuration/https`](https://shopify.dev/docs/apps/webhooks/configuration/https)):

```
expected = HMAC_SHA256(raw_request_body, app_shared_secret)
received = base64_decode(header['X-Shopify-Hmac-Sha256'])
assert hmac.compare_digest(expected, received)
```

`verify_webhook(...)` is a pure function so it's directly unit-tested. The `/api/v1/connectors/shopify/webhooks` endpoint reads the raw body once (no JSON-parsing first — the HMAC must match the bytes Shopify sent), verifies, then deserialises. Mismatch → `BF-CONN-SHOPIFY-002` and 401 response (Shopify will retry).

### 3.7 Write-back

`can_write=False` for M2 first cut. Writes deferred to M2.5 alongside the cross-source reconciliation pipeline, where `EntityReconciliationPlan.authoritative_source` decides which source receives writes for each canonical column. When writes light up, the body of `write(...)` will route create/update/delete to the matching REST mutation endpoint.

### 3.8 Health check

`health_check(token)` issues `query { shop { id name } }`. 200 → healthy with measured latency; 4xx/5xx → unhealthy with the response status in `notes`.

## 4. Design Patterns Applied

| Pattern | Where | Why |
|---|---|---|
| **Adapter** | `ShopifyConnector` | Translates Shopify's GraphQL/REST surface to the framework's typed I/O. |
| **Strategy** | Capability flags | Same protocol; `can_write=False` (M2 first cut) gates the framework's call sites. |
| **Decorator** | Rate-limit retry | Wraps `ShopifyAPIClient.execute` with deterministic backoff. |
| **Composite** | Static catalog | Per-resource builders `_customer_table()` etc. composed into one `SourceSchema`. |

## 5. Test Plan

- **Catalog tests** — every column in `customers`/`orders`/`products` has a non-empty `source_type`, primary keys are correctly tagged, money columns ship in `_amount`/`_currency_code` pairs.
- **HMAC tests** — golden vector matches; tampered body rejected; missing header rejected; case-insensitive header lookup.
- **Auth tests** — valid token exchange returns access_token; bad code raises `BF-CONN-SHOPIFY-001`; install-callback HMAC verification round-trip.
- **API client tests** — GraphQL 200 returns `data`; GraphQL 200 with `errors` raises `BF-CONN-SHOPIFY-003`; HTTP 429 is retried once after `Retry-After` then surfaces `BF-CONN-SHOPIFY-004`; `MockTransport` injection via constructor.
- **Connector tests** — `authenticate` validates via shop query; `introspect_schema` returns the static catalog; `sample_rows` cursors through one page; `read` paginates across two pages; `write` raises `BF-CONN-002`; `webhook_subscribe` POSTs the right body; `health_check` reports latency.
- **Coverage**: 90%.

## 6. Error Codes

| Code | Condition | Recovery |
|---|---|---|
| `BF-CONN-SHOPIFY-001` | Missing or invalid credentials (shop_domain / access_token) | UI prompts re-auth; nothing user-actionable from the connector. |
| `BF-CONN-SHOPIFY-002` | Webhook HMAC verification failed | 401 response; Shopify retries per its delivery policy. |
| `BF-CONN-SHOPIFY-003` | Shopify Admin API returned an error response | Surface the message to the operator; agent layer plans a retry. |
| `BF-CONN-SHOPIFY-004` | Rate limit exhausted after retry | Backoff with jitter; UI surfaces "syncing slowly" badge. |
| `BF-CONN-SHOPIFY-005` | Unknown resource requested (`sample_rows`/`read` for a table not in the catalog) | Caller error; raises 400. |

## 7. Dependencies

- [`CONN-FRAMEWORK`](CONN-FRAMEWORK.md) — connector protocol + registry.
- `httpx` — async HTTP client (already in pyproject).
- `hmac` + `hashlib` (stdlib) — webhook signature.
- Pinned Shopify Admin API version `2026-04`.

## 8. Milestone

- **M2**: full read path + webhook subscribe/verify; `can_write=False`.
- **M2.5**: write-back through `EntityReconciliationPlan` routing.
- **M3**: variants/inventory split into separate tables; metafields surfaced; cross-shop multi-tenant flows.
