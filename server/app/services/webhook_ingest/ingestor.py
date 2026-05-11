"""WebhookIngestor — orchestrates parse → enqueue.

Per docs/40-features/CONN-FRAMEWORK.md §3.6. Routes verified webhook bytes
through the per-provider parser, then enqueues the typed event for the
cross-source reconciler.

The enqueue is a no-op log + persist-to-`connector_events`.
"""

from __future__ import annotations

from app.observability.logging import get_logger
from app.services.webhook_ingest.parsers import (
    parse_sheets_change,
    parse_shopify_event,
    parse_stripe_event,
)
from app.services.webhook_ingest.types import (
    IngestedEvent,
    ProviderName,
)


__all__ = ["WebhookIngestor"]


logger = get_logger("services.webhook_ingest.ingestor")


class WebhookIngestor:
    """Stateless coordinator. One ingest call per verified delivery."""

    async def ingest_shopify(
        self, *, raw_body: bytes, topic: str
    ) -> IngestedEvent:
        event = parse_shopify_event(raw_body=raw_body, topic=topic)
        await self._enqueue(event)
        return event

    async def ingest_stripe(self, *, raw_body: bytes) -> IngestedEvent:
        event = parse_stripe_event(raw_body=raw_body)
        await self._enqueue(event)
        return event

    async def ingest_sheets(
        self, *, headers: dict[str, str], spreadsheet_id: str,
    ) -> IngestedEvent | None:
        event = parse_sheets_change(
            headers=headers, spreadsheet_id=spreadsheet_id,
        )
        if event is not None:
            await self._enqueue(event)
        return event

    # ---------- internal ----------

    async def _enqueue(self, event: IngestedEvent) -> None:
        """Persist + enqueue for the reconciler.

        Log only in v1.
        """
        logger.info(
            "webhook_event_enqueued",
            provider=event.provider.value,
            source_table=event.source_table,
            op=event.op.value,
            source_id=event.source_id,
            occurred_at=event.occurred_at.isoformat(),
        )
