# `CONN-STRIPE` — Stripe Connector

Status: M2. Second webhook-driven moat connector. Pairs with Shopify so the cross-source reconciliation pipeline has both an e-commerce and a payments source to unify.

---

## 1. Overview

Stripe's REST API is the canonical surface (no GraphQL). API-key auth (no OAuth dance — the merchant pastes a restricted secret key from their Stripe dashboard). Webhooks are HMAC-SHA256 signed with timestamp + payload to defeat replay; the verifier accepts one signature scheme (`v1=`) and one window (default 300 seconds).

**Resources surfaced (M2 scope):** `customers`, `subscriptions`, `invoices`, `charges`. Refunds + payouts ride along on charges as JSON aggregates; M3 splits them.

## 2. Module Layout

```
server/app/connectors/stripe/
├── __init__.py            # registration with ConnectorRegistry
├── connector.py           # StripeConnector implementing Connector Protocol
├── api.py                 # StripeAPIClient — httpx + REST + cursor pagination + 429 retry
├── catalog.py             # static SourceTable defs (customers/subscriptions/invoices/charges)
└── webhook.py             # verify_webhook — Stripe-Signature header parser + HMAC verify
```

## 3. Capabilities

```python
metadata = ConnectorMetadata(
    name="stripe",
    display_name="Stripe",
    version="1.0.0",
    auth_kind=AuthKind.API_KEY,
    capabilities=ConnectorCapabilities(
        can_introspect=True,
        can_read=True,
        can_write=False,                  # M2.5 lights up writeback
        can_subscribe_webhooks=True,
        supports_pagination=True,
        supports_streaming=True,
        requires_periodic_sync=False,     # webhooks are real-time
        write_back_canonical_only=True,
    ),
)
```

## 4. Auth

`AuthKind.API_KEY`. The merchant pastes a **restricted secret key** (`rk_live_...` or `rk_test_...`) generated from their Stripe dashboard with the minimum read scopes. We validate the key by issuing `GET /v1/customers?limit=1` — 401 → `BF-CONN-STRIPE-001`.

```python
AuthCredentials(payload={"api_key": SecretStr("rk_live_...")})
```

`authenticate(...)` returns a `ConnectorToken` with `metadata={"_api_key": "...", "_account_id": "...", "test_mode": bool}`. Account id comes from `GET /v1/account` (it's the merchant's `acct_*` identifier, used to disambiguate webhook deliveries when multiple accounts share an endpoint).

**App-level config** (env, set per Baseflo deployment):

| Env var | Purpose |
|---|---|
| `BASEFLO_STRIPE_WEBHOOK_SECRET` | Endpoint signing secret from Stripe dashboard. Used for HMAC verification on every incoming webhook. |
| `BASEFLO_STRIPE_API_VERSION` | Default `2024-11-20.acacia`. Pinned to a specific Stripe release. |

## 5. Static Catalog

| Table | Selected columns | Primary key |
|---|---|---|
| `customers` | `id, email, name, phone, description, created, currency, default_source_id, metadata (json), test_mode` | `id` |
| `subscriptions` | `id, customer_id (FK), status, current_period_start, current_period_end, cancel_at_period_end, canceled_at, items (json), latest_invoice_id, plan_amount, plan_currency, plan_interval, created, test_mode` | `id` |
| `invoices` | `id, customer_id (FK), subscription_id, status, amount_due, amount_paid, amount_remaining, currency, paid, period_start, period_end, due_date, created, test_mode` | `id` |
| `charges` | `id, customer_id (FK), invoice_id, status, amount, currency, captured, paid, refunded, refunds (json), failure_code, failure_message, created, test_mode` | `id` |

**`source_type` values:** same set as Shopify (`id_string` for Stripe object ids, `string`, `email`, `phone`, `decimal`, `integer`, `boolean`, `datetime`, `json`, `enum_*`).

## 6. Pagination + rate limiting

Stripe is cursor-paginated via `starting_after` query param; responses include `has_more` + the last item's `id`. Rate limits: 100 r/s in live, 25 r/s in test. The client retries once on 429 honoring the `Retry-After` header; second 429 → `BF-CONN-STRIPE-004`.

## 7. Webhooks

Subscription is created in the Stripe dashboard or via `POST /v1/webhook_endpoints`; the endpoint signing secret (`whsec_...`) is configured via `BASEFLO_STRIPE_WEBHOOK_SECRET`.

**Signature verification** ([`stripe.com/docs/webhooks/signatures`](https://stripe.com/docs/webhooks/signatures)):

```
header  = request.headers["Stripe-Signature"]
        = "t=1700000000,v1=abc123...,v1=def456..."
parsed  = parse_pairs(header)
signed  = f"{parsed['t']}.{raw_body.decode()}"
expected = HMAC_SHA256(signed, endpoint_secret)
for v1 in parsed.v1_signatures:
    if hmac.compare_digest(expected_hex, v1):
        accept iff (now - parsed['t']) < tolerance_seconds
        return True
```

`verify_webhook(...)` is pure (timestamp clock supplied by caller), unit-tested with golden vectors. Default tolerance: 300 seconds. Mismatch → `BF-CONN-STRIPE-002`.

## 8. Test Plan

- **Catalog tests** — every column has `source_type`; primary keys correct; FK columns named `<entity>_id`.
- **Signature tests** — golden vector verifies; tampered body rejected; replay window enforced (timestamp older than tolerance → reject); missing `t=` or `v1=` rejected.
- **API client tests** — REST GET 200; cursor pagination across 2 pages via `has_more` + `starting_after`; 429 retry-once-then-raise.
- **Connector tests** — authenticate validates via `GET /v1/customers?limit=1`; introspect returns static catalog; sample uses cursor; read paginates; write raises `BF-CONN-002`.
- **Coverage**: 90%.

## 9. Error Codes

| Code | Condition | Recovery |
|---|---|---|
| `BF-CONN-STRIPE-001` | Missing or invalid API key | UI prompts re-auth |
| `BF-CONN-STRIPE-002` | Webhook HMAC failed (tamper / replay) | 401 response; Stripe retries |
| `BF-CONN-STRIPE-003` | Stripe API returned an error | Surface the message; agent retries |
| `BF-CONN-STRIPE-004` | Rate limit exhausted after retry | Backoff with jitter |
| `BF-CONN-STRIPE-005` | Unknown resource requested | Caller error; 400 |

## 10. Dependencies

[`CONN-FRAMEWORK`](CONN-FRAMEWORK.md), `httpx`, `hmac` + `hashlib` (stdlib).

## 11. Milestone

- **M2**: read path + signature verification + webhook subscription via dashboard.
- **M2.5**: write-back through `EntityReconciliationPlan`.
- **M3**: refunds/payouts split into separate tables; multi-account flows.
