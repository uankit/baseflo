"""Per-provider webhook parsers — translate raw payload + headers → IngestedEvent[].

Each provider sends a different shape; this module is where their idioms
get normalised. The output is always a typed `IngestedEvent`. Errors
on malformed payloads raise typed `BF-CONN-{provider}-003`.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from app.core.errors import BasefloError
from app.services.webhook_ingest.types import (
    IngestedEvent,
    IngestedEventOp,
    ProviderName,
)


__all__ = [
    "parse_sheets_change",
    "parse_shopify_event",
    "parse_stripe_event",
]


# ---------- Shopify ----------


# Shopify topics → (canonical source table, op).
_SHOPIFY_TOPIC_MAP: dict[str, tuple[str, IngestedEventOp]] = {
    "customers/create":  ("customers", IngestedEventOp.CREATE),
    "customers/update":  ("customers", IngestedEventOp.UPDATE),
    "customers/delete":  ("customers", IngestedEventOp.DELETE),
    "orders/create":     ("orders", IngestedEventOp.CREATE),
    "orders/updated":    ("orders", IngestedEventOp.UPDATE),
    "orders/cancelled":  ("orders", IngestedEventOp.UPDATE),
    "orders/paid":       ("orders", IngestedEventOp.UPDATE),
    "products/create":   ("products", IngestedEventOp.CREATE),
    "products/update":   ("products", IngestedEventOp.UPDATE),
    "products/delete":   ("products", IngestedEventOp.DELETE),
}


def parse_shopify_event(
    *, raw_body: bytes, topic: str
) -> IngestedEvent:
    """Translate one Shopify webhook delivery to a typed event.

    `topic` is the value of `X-Shopify-Topic`. Body is the JSON resource.
    Unknown topics surface as `BF-CONN-SHOPIFY-003` so they're visible in
    logs rather than silently dropped.
    """
    mapping = _SHOPIFY_TOPIC_MAP.get(topic)
    if mapping is None:
        raise BasefloError(
            error_code="BF-CONN-SHOPIFY-003",
            message=f"Unrecognised Shopify webhook topic: {topic!r}.",
            status_code=400,
        )
    table, op = mapping

    try:
        body = json.loads(raw_body.decode("utf-8")) if raw_body else {}
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BasefloError(
            error_code="BF-CONN-SHOPIFY-003",
            message=f"Shopify webhook body was not JSON: {exc!r}",
            status_code=400,
            cause=exc,
        ) from exc

    source_id = _shopify_id(body)
    return IngestedEvent(
        provider=ProviderName.SHOPIFY,
        source_table=table,
        op=op,
        source_id=source_id,
        occurred_at=datetime.now(UTC),
        raw=body if isinstance(body, dict) else {},
    )


def _shopify_id(body: Any) -> str | None:
    """Shopify webhook payloads carry a numeric `id` for each resource."""
    if not isinstance(body, dict):
        return None
    raw_id = body.get("id")
    return str(raw_id) if raw_id is not None else None


# ---------- Stripe ----------


# Stripe event-type prefixes → (canonical source table, op).
# Stripe uses `customer.created` / `customer.updated` / `customer.deleted`,
# `customer.subscription.*`, `invoice.*`, `charge.*`.
_STRIPE_PREFIX_MAP: tuple[tuple[str, str], ...] = (
    ("customer.subscription.", "subscriptions"),
    ("customer.", "customers"),
    ("invoice.", "invoices"),
    ("charge.", "charges"),
)

_STRIPE_OP_SUFFIX: dict[str, IngestedEventOp] = {
    "created": IngestedEventOp.CREATE,
    "deleted": IngestedEventOp.DELETE,
    # Everything else (`updated`, `paid`, `refunded`, `failed`, …) is UPDATE.
}


def parse_stripe_event(*, raw_body: bytes) -> IngestedEvent:
    """Translate one Stripe event envelope to a typed event."""
    try:
        body = json.loads(raw_body.decode("utf-8")) if raw_body else {}
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BasefloError(
            error_code="BF-CONN-STRIPE-003",
            message=f"Stripe webhook body was not JSON: {exc!r}",
            status_code=400,
            cause=exc,
        ) from exc

    if not isinstance(body, dict):
        raise BasefloError(
            error_code="BF-CONN-STRIPE-003",
            message="Stripe webhook body was not a JSON object.",
            status_code=400,
        )

    event_type = body.get("type")
    if not isinstance(event_type, str):
        raise BasefloError(
            error_code="BF-CONN-STRIPE-003",
            message="Stripe event missing `type` field.",
            status_code=400,
        )

    table = _stripe_table_from_type(event_type)
    if table is None:
        raise BasefloError(
            error_code="BF-CONN-STRIPE-003",
            message=f"Unrecognised Stripe event type: {event_type!r}.",
            status_code=400,
        )

    op = _stripe_op_from_type(event_type)
    obj = ((body.get("data") or {}).get("object") if isinstance(body.get("data"), dict) else None) or {}
    source_id = obj.get("id") if isinstance(obj, dict) else None
    occurred_at = _stripe_occurred_at(body)
    return IngestedEvent(
        provider=ProviderName.STRIPE,
        source_table=table,
        op=op,
        source_id=str(source_id) if source_id is not None else None,
        occurred_at=occurred_at,
        raw=body,
    )


def _stripe_table_from_type(event_type: str) -> str | None:
    for prefix, table in _STRIPE_PREFIX_MAP:
        if event_type.startswith(prefix):
            return table
    return None


def _stripe_op_from_type(event_type: str) -> IngestedEventOp:
    suffix = event_type.rsplit(".", 1)[-1]
    return _STRIPE_OP_SUFFIX.get(suffix, IngestedEventOp.UPDATE)


def _stripe_occurred_at(body: dict[str, Any]) -> datetime:
    created = body.get("created")
    if not isinstance(created, (int, float, str)):
        return datetime.now(UTC)
    try:
        return datetime.fromtimestamp(int(created), tz=UTC)
    except (TypeError, ValueError):
        return datetime.now(UTC)


# ---------- Google Sheets (Drive Push Notifications) ----------


def parse_sheets_change(
    *,
    headers: dict[str, str],
    spreadsheet_id: str,
) -> IngestedEvent | None:
    """Translate a Drive Push Notification into a refetch event.

    Drive notifications arrive with no body — they're a "something changed,
    re-read"-style signal. Headers we read:

      - `X-Goog-Channel-ID` — our channel id
      - `X-Goog-Resource-State` — `sync` / `update` / `trash` / `untrash`
      - `X-Goog-Resource-ID`, `X-Goog-Message-Number`

    `sync` is a one-shot setup confirmation; we drop it (return None).
    Everything else becomes a REFETCH event the reconciler acts on.
    """
    state = headers.get("X-Goog-Resource-State", "").lower()
    if state == "sync":
        return None
    if not state:
        raise BasefloError(
            error_code="BF-CONN-SHEETS-003",
            message="Sheets webhook missing `X-Goog-Resource-State` header.",
            status_code=400,
        )
    return IngestedEvent(
        provider=ProviderName.GOOGLE_SHEETS,
        source_table="*",  # whole-spreadsheet granularity; reconciler enumerates sheets
        op=IngestedEventOp.REFETCH,
        source_id=spreadsheet_id,
        occurred_at=datetime.now(UTC),
        raw={"resource_state": state, "channel_id": headers.get("X-Goog-Channel-ID")},
    )
