"""StripeConnector — REST + cursor pagination + webhook signature verification.

Per docs/40-features/CONN-STRIPE.md. The Stripe pattern is simpler than
Shopify: no OAuth dance (merchant pastes a restricted API key), REST-only,
cursor pagination via `starting_after`.
"""

from __future__ import annotations

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
from app.connectors.stripe.api import StripeAPIClient
from app.connectors.stripe.catalog import (
    API_VERSION,
    TABLE_NAMES,
    build_catalog,
    table_by_name,
)
from app.core.errors import BasefloError
from app.observability.logging import get_logger


logger = get_logger("connectors.stripe")


_PATH_BY_TABLE: dict[str, str] = {
    "customers": "/v1/customers",
    "subscriptions": "/v1/subscriptions",
    "invoices": "/v1/invoices",
    "charges": "/v1/charges",
}


# Default events Baseflo subscribes to per docs/40-features/CONN-STRIPE.md §7.
# Covers the lifecycle for the four resources we surface; the merchant can
_DEFAULT_STRIPE_EVENTS: tuple[str, ...] = (
    "customer.created", "customer.updated", "customer.deleted",
    "customer.subscription.created", "customer.subscription.updated",
    "customer.subscription.deleted",
    "invoice.created", "invoice.paid", "invoice.payment_failed",
    "charge.succeeded", "charge.failed", "charge.refunded",
)


class StripeConnector:
    """Stripe REST API connector. One instance per registration; per-account
    state arrives via `ConnectorToken.metadata`."""

    metadata: ConnectorMetadata = ConnectorMetadata(
        name="stripe",
        display_name="Stripe",
        version="1.0.0",
        protocol_version="1.0",
        auth_kind=AuthKind.API_KEY,
        capabilities=ConnectorCapabilities(
            can_introspect=True,
            can_read=True,
            can_write=False,
            can_subscribe_webhooks=True,
            supports_pagination=True,
            supports_streaming=True,
            requires_periodic_sync=False,
            write_back_canonical_only=True,
        ),
        required_scopes=[
            "rak_customer_read", "rak_subscription_read",
            "rak_invoice_read", "rak_charge_read",
        ],
        docs_url="https://stripe.com/docs/api",
    )

    # ---------- auth ----------

    async def authenticate(self, credentials: AuthCredentials) -> ConnectorToken:
        api_key_secret = credentials.payload.get("api_key")
        if api_key_secret is None:
            raise BasefloError(
                error_code="BF-CONN-STRIPE-001",
                message="Stripe connector requires `api_key` in credentials.payload.",
                status_code=400,
            )
        api_key = api_key_secret.get_secret_value()

        client = StripeAPIClient(
            api_key=api_key, transport=_transport_from_creds(credentials),
        )
        try:
            account = await client.get_account()
        except BasefloError as exc:
            raise BasefloError(
                error_code="BF-CONN-STRIPE-001",
                message="Stripe authentication failed; api_key rejected.",
                status_code=401,
                cause=exc,
            ) from exc

        account_id = str(account.get("id") or "unknown")
        test_mode = not bool(account.get("livemode", False))
        return ConnectorToken(
            connector_name=self.metadata.name,
            token_id=UUID("01970000-0000-7000-8000-000000000002"),
            metadata={
                "account_id": account_id,
                "api_version": API_VERSION,
                "test_mode": test_mode,
                "_api_key": api_key,
            },
        )

    async def revoke(self, token: ConnectorToken) -> None:
        # Stripe API keys are revoked via the merchant's dashboard. No
        # provider-side action required by the connector — the Token Vault
        # zeroises the encrypted bytes on storage delete.
        _ = token

    # ---------- introspection + sampling ----------

    async def introspect_schema(self, token: ConnectorToken) -> SourceSchema:
        account_id = token.metadata.get("account_id")
        return build_catalog(account_id=str(account_id) if account_id else None)

    async def sample_rows(
        self, token: ConnectorToken, table: str, n: int
    ) -> list[Row]:
        if table_by_name(table) is None:
            raise BasefloError(
                error_code="BF-CONN-STRIPE-005",
                message=(
                    f"Stripe connector does not expose table {table!r}. "
                    f"Known tables: {sorted(TABLE_NAMES)}."
                ),
                status_code=400,
            )
        n = max(1, min(int(n), 100))
        client = self._client(token)
        response = await client.list_paginated(
            _PATH_BY_TABLE[table], page_size=n,
        )
        data = response.get("data") or []
        if not isinstance(data, list):
            raise BasefloError(
                error_code="BF-CONN-STRIPE-003",
                message=f"Stripe {table!r} response missing `data` array.",
                status_code=502,
            )
        return [Row(values=_flatten_node(table, item)) for item in data if isinstance(item, dict)]

    async def read(
        self, token: ConnectorToken, query: SourceQuery
    ) -> AsyncIterator[Row]:
        if table_by_name(query.table) is None:
            raise BasefloError(
                error_code="BF-CONN-STRIPE-005",
                message=(
                    f"Stripe connector does not expose table {query.table!r}. "
                    f"Known tables: {sorted(TABLE_NAMES)}."
                ),
                status_code=400,
            )
        return self._stream(token, query)

    async def _stream(
        self, token: ConnectorToken, query: SourceQuery
    ) -> AsyncIterator[Row]:
        client = self._client(token)
        starting_after: str | None = query.cursor
        emitted = 0
        page_size = min(int(query.limit) if query.limit else 100, 100)
        limit = int(query.limit) if query.limit else None

        while True:
            response = await client.list_paginated(
                _PATH_BY_TABLE[query.table],
                page_size=page_size,
                starting_after=starting_after,
            )
            data = response.get("data") or []
            if not isinstance(data, list):
                raise BasefloError(
                    error_code="BF-CONN-STRIPE-003",
                    message=f"Stripe {query.table!r} response missing `data` array.",
                    status_code=502,
                )
            for item in data:
                if not isinstance(item, dict):
                    continue
                yield Row(values=_flatten_node(query.table, item))
                emitted += 1
                if limit is not None and emitted >= limit:
                    return
            if not response.get("has_more"):
                return
            if not data:
                return
            last = data[-1]
            if not isinstance(last, dict):
                return
            next_cursor = last.get("id")
            if not isinstance(next_cursor, str):
                return
            starting_after = next_cursor


    async def write(
        self, token: ConnectorToken, mutation: SourceMutation
    ) -> WriteResult:
        """REST-based write-back per docs/40-features/CONN-STRIPE.md §11.

        Stripe uses POST for both create + update; DELETE for deletes. The
        The write router consults the EntityReconciliationPlan to decide
        which connector receives each canonical-column write.
        """
        if table_by_name(mutation.table) is None:
            raise BasefloError(
                error_code="BF-CONN-STRIPE-005",
                message=(
                    f"StripeConnector.write does not expose table {mutation.table!r}. "
                    f"Known tables: {sorted(TABLE_NAMES)}."
                ),
                status_code=400,
            )
        client = self._client(token)
        base_path = _PATH_BY_TABLE[mutation.table]

        if mutation.op == "create":
            if mutation.values is None:
                raise BasefloError(
                    error_code="BF-CONN-STRIPE-003",
                    message="Stripe create requires `values`.",
                    status_code=400,
                )
            response = await client.post_form(
                base_path, form=_flatten_for_form(mutation.values),
            )
            return WriteResult(
                success=True, affected_rows=1, new_id=_id_from_response(response),
            )

        if mutation.op == "update":
            if not mutation.where or "id" not in mutation.where:
                raise BasefloError(
                    error_code="BF-CONN-STRIPE-003",
                    message="Stripe update requires `where['id']`.",
                    status_code=400,
                )
            if mutation.values is None:
                raise BasefloError(
                    error_code="BF-CONN-STRIPE-003",
                    message="Stripe update requires `values`.",
                    status_code=400,
                )
            row_id = mutation.where["id"]
            response = await client.post_form(
                f"{base_path}/{row_id}", form=_flatten_for_form(mutation.values),
            )
            return WriteResult(success=True, affected_rows=1, new_id=str(row_id))

        if mutation.op == "delete":
            if not mutation.where or "id" not in mutation.where:
                raise BasefloError(
                    error_code="BF-CONN-STRIPE-003",
                    message="Stripe delete requires `where['id']`.",
                    status_code=400,
                )
            row_id = mutation.where["id"]
            await client.delete(f"{base_path}/{row_id}")
            return WriteResult(success=True, affected_rows=1, new_id=None)

        raise BasefloError(
            error_code="BF-CONN-STRIPE-003",
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
        """Create a webhook endpoint via `POST /v1/webhook_endpoints`.

        Per Stripe's API: a single endpoint subscribes to N event types via the
        `enabled_events[]` array. We surface the endpoint id as
        `Subscription.id` so `webhook_unsubscribe` can DELETE it.

        The endpoint's signing secret (`whsec_…`) is returned ONLY on this
        create call. The route uses `BASEFLO_STRIPE_WEBHOOK_SECRET` per deployment.
        """
        topics = events or list(_DEFAULT_STRIPE_EVENTS)
        client = self._client(token)
        form = {"url": callback_url}
        for i, topic in enumerate(topics):
            form[f"enabled_events[{i}]"] = topic
        response = await client.post_form("/v1/webhook_endpoints", form=form)
        endpoint_id = response.get("id")
        if not isinstance(endpoint_id, str):
            raise BasefloError(
                error_code="BF-CONN-STRIPE-003",
                message="Stripe webhook_endpoints response missing `id`.",
                status_code=502,
            )
        logger.info(
            "stripe_webhook_subscribed",
            account_id=str(token.metadata.get("account_id")),
            endpoint_id=endpoint_id,
            topic_count=len(topics),
        )
        return Subscription(
            id=endpoint_id,
            events=topics,
            callback_url=callback_url,
            expires_at=None,
        )

    async def webhook_unsubscribe(
        self, token: ConnectorToken, subscription: Subscription,
    ) -> None:
        """DELETE the Stripe webhook endpoint."""
        if not subscription.id:
            return
        client = self._client(token)
        try:
            await client.delete(f"/v1/webhook_endpoints/{subscription.id}")
        except BasefloError as exc:
            if "404" in (exc.message or ""):
                return  # already gone — idempotent
            raise
        logger.info(
            "stripe_webhook_unsubscribed",
            account_id=str(token.metadata.get("account_id")),
            endpoint_id=subscription.id,
        )

    # ---------- health ----------

    async def health_check(self, token: ConnectorToken) -> HealthStatus:
        import time  # noqa: PLC0415

        client = self._client(token)
        started = time.perf_counter()
        try:
            await client.get_account()
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

    def _client(self, token: ConnectorToken) -> StripeAPIClient:
        api_key = token.metadata.get("_api_key")
        if not isinstance(api_key, str):
            raise BasefloError(
                error_code="BF-CONN-STRIPE-001",
                message=(
                    "Stripe token missing `_api_key` in metadata. Token Vault "
                    "must populate this at call time."
                ),
                status_code=500,
            )
        api_version_value = token.metadata.get("api_version")
        api_version = (
            str(api_version_value) if isinstance(api_version_value, str) else API_VERSION
        )
        transport = token.metadata.get("_transport")
        return StripeAPIClient(
            api_key=api_key,
            api_version=api_version,
            transport=transport if isinstance(transport, httpx.BaseTransport) else None,
        )


# ---------- module-level helpers ----------


def _id_from_response(response: dict[str, Any]) -> str | None:
    """Stripe create/update responses are flat (no envelope) and carry `id`."""
    new_id = response.get("id")
    return str(new_id) if isinstance(new_id, str) else None


def _flatten_for_form(values: dict[str, Any]) -> dict[str, str]:
    """Stripe accepts form-encoded bodies; nested dicts use `key[sub]` notation.

    One level of nesting is sufficient for typical customer/subscription fields.
    """
    out: dict[str, str] = {}
    for k, v in values.items():
        if v is None:
            continue
        if isinstance(v, dict):
            for sub_k, sub_v in v.items():
                if sub_v is not None:
                    out[f"{k}[{sub_k}]"] = str(sub_v)
        elif isinstance(v, list):
            for i, item in enumerate(v):
                if item is not None:
                    out[f"{k}[{i}]"] = str(item)
        else:
            out[k] = str(v)
    return out


def _transport_from_creds(creds: AuthCredentials) -> httpx.BaseTransport | None:
    """Test seam — production never sets this."""
    return getattr(creds, "_transport", None)


# ---------- node flatteners ----------


def _flatten_node(table: str, node: dict[str, Any]) -> dict[str, Any]:
    if table == "customers":
        return _flatten_customer(node)
    if table == "subscriptions":
        return _flatten_subscription(node)
    if table == "invoices":
        return _flatten_invoice(node)
    if table == "charges":
        return _flatten_charge(node)
    raise BasefloError(
        error_code="BF-CONN-STRIPE-005",
        message=f"Unknown table for flatten: {table!r}",
        status_code=500,
    )


def _flatten_customer(n: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": n.get("id"),
        "email": n.get("email"),
        "name": n.get("name"),
        "phone": n.get("phone"),
        "description": n.get("description"),
        "currency": n.get("currency"),
        "default_source_id": n.get("default_source"),
        "metadata": n.get("metadata") or {},
        "created": _ts_to_iso(n.get("created")),
        "test_mode": not bool(n.get("livemode", True)),
    }


def _flatten_subscription(n: dict[str, Any]) -> dict[str, Any]:
    plan = n.get("plan") or {}
    items = (n.get("items") or {}).get("data") or []
    return {
        "id": n.get("id"),
        "customer_id": n.get("customer"),
        "status": n.get("status"),
        "current_period_start": _ts_to_iso(n.get("current_period_start")),
        "current_period_end": _ts_to_iso(n.get("current_period_end")),
        "cancel_at_period_end": bool(n.get("cancel_at_period_end", False)),
        "canceled_at": _ts_to_iso(n.get("canceled_at")),
        "latest_invoice_id": n.get("latest_invoice"),
        "plan_amount": plan.get("amount"),
        "plan_currency": plan.get("currency"),
        "plan_interval": plan.get("interval"),
        "items": items,
        "created": _ts_to_iso(n.get("created")),
        "test_mode": not bool(n.get("livemode", True)),
    }


def _flatten_invoice(n: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": n.get("id"),
        "customer_id": n.get("customer"),
        "subscription_id": n.get("subscription"),
        "status": n.get("status"),
        "amount_due": n.get("amount_due", 0),
        "amount_paid": n.get("amount_paid", 0),
        "amount_remaining": n.get("amount_remaining", 0),
        "currency": n.get("currency"),
        "paid": bool(n.get("paid", False)),
        "period_start": _ts_to_iso(n.get("period_start")),
        "period_end": _ts_to_iso(n.get("period_end")),
        "due_date": _ts_to_iso(n.get("due_date")),
        "created": _ts_to_iso(n.get("created")),
        "test_mode": not bool(n.get("livemode", True)),
    }


def _flatten_charge(n: dict[str, Any]) -> dict[str, Any]:
    refunds = (n.get("refunds") or {}).get("data") or []
    return {
        "id": n.get("id"),
        "customer_id": n.get("customer"),
        "invoice_id": n.get("invoice"),
        "status": n.get("status"),
        "amount": n.get("amount", 0),
        "currency": n.get("currency"),
        "captured": bool(n.get("captured", False)),
        "paid": bool(n.get("paid", False)),
        "refunded": bool(n.get("refunded", False)),
        "refunds": refunds,
        "failure_code": n.get("failure_code"),
        "failure_message": n.get("failure_message"),
        "created": _ts_to_iso(n.get("created")),
        "test_mode": not bool(n.get("livemode", True)),
    }


def _ts_to_iso(value: Any) -> str | None:
    """Stripe emits datetimes as Unix epoch integers; we surface them as
    ISO 8601 strings so the agent's TEMPORAL classifier sees a stable shape
    matching what other connectors emit."""
    if value is None:
        return None
    try:
        ts = int(value)
    except (TypeError, ValueError):
        return None
    return datetime.fromtimestamp(ts, tz=UTC).isoformat()
