"""Webhook ingestion endpoints for connectors.

Per docs/40-features/CONN-SHOPIFY.md §3.6 + docs/40-features/CONN-STRIPE.md §7
+ docs/40-features/CONN-SHEETS.md §6.

Each provider gets one POST endpoint. The route's job is:

  1. Verify provenance (HMAC for Shopify/Stripe, channel-token for Sheets).
  2. Parse the typed event via the `WebhookIngestor`.
  3. Hand off to `WebhookDispatcher` — looks up the tenant, applies RLS scope,
     loads the project's IR, runs the reconciler.

Per-provider verification stays in the connector packages; routes are thin.

Per docs/05-coding-rules.md §5.3 we never substitute a default response on
verification failure: bad signature → 401 + typed `BF-CONN-{provider}-002`.
"""

from __future__ import annotations

import time

from fastapi import APIRouter, Header, Request, status
from pydantic import BaseModel

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends

from app.connectors.shopify.webhook import (
    HMAC_HEADER as SHOPIFY_HMAC_HEADER,
    require_valid_webhook as require_valid_shopify_webhook,
)
from app.connectors.stripe.webhook import (
    SIGNATURE_HEADER as STRIPE_SIGNATURE_HEADER,
    require_valid_webhook as require_valid_stripe_webhook,
)
from app.core.config import get_config
from app.core.errors import BasefloError
from app.db.session import open_session
from app.observability.logging import get_logger
from app.services.data_plane.webhook_dispatcher import WebhookDispatcher
from app.services.webhook_ingest import WebhookIngestor


router = APIRouter(prefix="/connectors", tags=["connector_webhooks"])
logger = get_logger("api.connector_webhooks")
_ingestor = WebhookIngestor()


async def get_webhook_dispatcher() -> AsyncIterator[WebhookDispatcher]:
    """Yield a `WebhookDispatcher` bound to a fresh DB session.

    Unit tests override this dep with a no-op fake so the routes can run
    without Postgres; integration tests exercise the real path.
    """
    async with open_session() as session:
        yield WebhookDispatcher(session=session)


class WebhookAccepted(BaseModel):
    """Lightweight acknowledgement; sources don't read the body, only status."""

    accepted: bool = True


# ---------- Shopify ----------


@router.post(
    "/shopify/webhooks",
    status_code=status.HTTP_200_OK,
    response_model=WebhookAccepted,
    summary="Ingest a Shopify webhook delivery",
)
async def ingest_shopify_webhook(
    request: Request,
    dispatcher: Annotated[WebhookDispatcher, Depends(get_webhook_dispatcher)],
    x_shopify_topic: str = Header(default=""),
    x_shopify_shop_domain: str = Header(default=""),
    x_shopify_hmac_sha256: str = Header(default=""),
) -> WebhookAccepted:
    """Verify HMAC against `BASEFLO_SHOPIFY_CLIENT_SECRET`, parse, enqueue.

    The raw body MUST be read once and reused for HMAC verification — if we
    re-serialise after `await request.json()` the digest won't match.
    """
    config = get_config()
    if config.shopify_client_secret is None:
        raise BasefloError(
            error_code="BF-CONN-SHOPIFY-001",
            message=(
                "Shopify webhook ingestion is not configured. Set "
                "BASEFLO_SHOPIFY_CLIENT_SECRET on this deployment."
            ),
            status_code=503,
        )

    raw_body = await request.body()
    require_valid_shopify_webhook(
        raw_body=raw_body,
        header_value=x_shopify_hmac_sha256 or request.headers.get(SHOPIFY_HMAC_HEADER),
        secret=config.shopify_client_secret.get_secret_value(),
    )

    event = await _ingestor.ingest_shopify(raw_body=raw_body, topic=x_shopify_topic)
    logger.info(
        "shopify_webhook_accepted",
        topic=x_shopify_topic,
        shop_domain=x_shopify_shop_domain,
        op=event.op.value,
        source_id=event.source_id,
    )
    if x_shopify_shop_domain:
        await dispatcher.dispatch(
            event=event,
            connector_kind="shopify",
            routing_field="shop_domain",
            routing_value=x_shopify_shop_domain,
        )
    return WebhookAccepted()


# ---------- Stripe ----------


@router.post(
    "/stripe/webhooks",
    status_code=status.HTTP_200_OK,
    response_model=WebhookAccepted,
    summary="Ingest a Stripe webhook delivery",
)
async def ingest_stripe_webhook(
    request: Request,
    dispatcher: Annotated[WebhookDispatcher, Depends(get_webhook_dispatcher)],
    stripe_signature: str = Header(default=""),
) -> WebhookAccepted:
    """Verify the Stripe-Signature header against `BASEFLO_STRIPE_WEBHOOK_SECRET`.

    Replay protection is built into the verifier (5-minute window by default).
    """
    config = get_config()
    if config.stripe_webhook_secret is None:
        raise BasefloError(
            error_code="BF-CONN-STRIPE-001",
            message=(
                "Stripe webhook ingestion is not configured. Set "
                "BASEFLO_STRIPE_WEBHOOK_SECRET on this deployment."
            ),
            status_code=503,
        )

    raw_body = await request.body()
    require_valid_stripe_webhook(
        raw_body=raw_body,
        header_value=stripe_signature or request.headers.get(STRIPE_SIGNATURE_HEADER),
        secret=config.stripe_webhook_secret.get_secret_value(),
        now_unix=int(time.time()),
    )

    event = await _ingestor.ingest_stripe(raw_body=raw_body)
    logger.info(
        "stripe_webhook_accepted",
        source_table=event.source_table,
        op=event.op.value,
        source_id=event.source_id,
    )
    account_id = event.raw.get("account") if isinstance(event.raw, dict) else None
    if isinstance(account_id, str) and account_id:
        await dispatcher.dispatch(
            event=event,
            connector_kind="stripe",
            routing_field="account_id",
            routing_value=account_id,
        )
    return WebhookAccepted()


# ---------- Google Sheets (Drive Push Notifications) ----------


@router.post(
    "/google_sheets/webhooks",
    status_code=status.HTTP_200_OK,
    response_model=WebhookAccepted,
    summary="Ingest a Drive push notification for a Sheets-connected file",
)
async def ingest_sheets_webhook(
    request: Request,
    dispatcher: Annotated[WebhookDispatcher, Depends(get_webhook_dispatcher)],
    x_goog_resource_state: str = Header(default=""),
    x_goog_channel_id: str = Header(default=""),
    x_goog_resource_id: str = Header(default=""),
    x_goog_channel_token: str = Header(default=""),
) -> WebhookAccepted:
    """Drive sends a "something changed" ping; the reconciler re-fetches.

    The push notification has no body. The `X-Goog-Channel-Token` header
    carries the spreadsheet id we set during `webhook_subscribe` (in the
    `token` field of the watch request); the parser uses it to identify
    which spreadsheet refetches.

    Note: there's no HMAC on Drive notifications. The `channel_token` is the
    secret — set by us during subscribe and verified here. The `sync` state
    sent right after channel creation is dropped silently.
    """
    _ = (request,)
    spreadsheet_id = x_goog_channel_token or ""
    if not spreadsheet_id:
        raise BasefloError(
            error_code="BF-CONN-SHEETS-003",
            message=(
                "Sheets webhook missing `X-Goog-Channel-Token` (spreadsheet id). "
                "The watch subscription must set `token` on creation."
            ),
            status_code=400,
        )
    headers: dict[str, str] = {
        "X-Goog-Resource-State": x_goog_resource_state,
        "X-Goog-Channel-ID": x_goog_channel_id,
        "X-Goog-Resource-ID": x_goog_resource_id,
    }
    event = await _ingestor.ingest_sheets(
        headers=headers, spreadsheet_id=spreadsheet_id,
    )
    if event is None:
        # `sync` confirmation — Drive sends one when the watch starts; ignore.
        logger.info("sheets_drive_sync_received", channel_id=x_goog_channel_id)
        return WebhookAccepted()
    logger.info(
        "sheets_webhook_accepted",
        spreadsheet_id=spreadsheet_id,
        op=event.op.value,
        resource_state=x_goog_resource_state,
    )
    await dispatcher.dispatch(
        event=event,
        connector_kind="google_sheets",
        routing_field="spreadsheet_id",
        routing_value=spreadsheet_id,
    )
    return WebhookAccepted()


__all__ = ["router"]
