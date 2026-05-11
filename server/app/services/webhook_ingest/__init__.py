"""Webhook ingestion — typed events + per-provider parsers.

Per docs/40-features/CONN-FRAMEWORK.md §3.6. Each provider's webhook payload
shape is different (Shopify: REST resource body + topic header; Stripe:
event envelope; Sheets: empty body + change-state header). The ingestor
normalises them into typed `IngestedEvent` records the cross-source
reconciler can act on.

The parser, typed event model, and persistence into `connector_events` are available in v1.
"""

from __future__ import annotations

from app.services.webhook_ingest.types import (
    IngestedEvent,
    IngestedEventOp,
    ProviderName,
)
from app.services.webhook_ingest.parsers import (
    parse_sheets_change,
    parse_shopify_event,
    parse_stripe_event,
)
from app.services.webhook_ingest.ingestor import WebhookIngestor

__all__ = [
    "IngestedEvent",
    "IngestedEventOp",
    "ProviderName",
    "WebhookIngestor",
    "parse_sheets_change",
    "parse_shopify_event",
    "parse_stripe_event",
]
