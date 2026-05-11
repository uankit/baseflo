"""Auto-subscribe webhooks after a connector finishes installing.

Per docs/40-features/CONN-FRAMEWORK.md §3.6. Right after `ConnectorRegistrar`
persists a fresh `Connector` row + encrypted token, this service:

  1. Looks up the connector class via `ConnectorRegistry`.
  2. Skips if `metadata.capabilities.can_subscribe_webhooks` is False
     (CSV / Excel / Postgres in v1).
  3. Hydrates a live `ConnectorToken` from the merged config + token payload.
  4. Calls `connector.webhook_subscribe(...)` with a project-scoped callback
     URL and the per-provider default event set.
  5. Persists the `subscription.id` into `connectors.config` so revoke flows
     can later DELETE the right webhook.

Failures are caught + logged + returned as `None` (best-effort): a connector
that fails to subscribe is still installed; the user can retry or rely on
manual provider-side webhook config until the underlying issue is resolved.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.base import ConnectorToken
from app.connectors.registry import ConnectorRegistry
from app.db.models.connector import Connector as ConnectorRow
from app.observability.logging import get_logger
from app.services.connector_tokens.vault import TokenVault


__all__ = ["WebhookSubscriber", "default_event_set_for"]


logger = get_logger("services.connector_oauth.webhook_subscriber")


# Per-provider default event sets. Picked to match what each connector's
# canonical IR tables source from. Conservative — extend as IR grows.
_DEFAULT_EVENTS: dict[str, list[str]] = {
    "shopify": [
        "customers/create", "customers/update", "customers/delete",
        "orders/create", "orders/updated", "orders/cancelled",
        "products/create", "products/update", "products/delete",
    ],
    "stripe": [
        "customer.created", "customer.updated", "customer.deleted",
        "customer.subscription.created", "customer.subscription.updated",
        "customer.subscription.deleted",
        "invoice.created", "invoice.paid", "invoice.payment_failed",
        "charge.succeeded", "charge.refunded",
    ],
    # Sheets uses Drive Push channels; the connector's `webhook_subscribe`
    # ignores `events` and watches the spreadsheet's resource id.
    "google_sheets": ["change"],
}


def default_event_set_for(connector_kind: str) -> list[str]:
    return list(_DEFAULT_EVENTS.get(connector_kind, []))


class WebhookSubscriber:
    """One instance per OAuth callback / install request."""

    def __init__(
        self,
        *,
        session: AsyncSession,
        vault: TokenVault,
        api_base_url: str,
    ) -> None:
        self._session = session
        self._vault = vault
        self._api_base_url = api_base_url.rstrip("/")

    async def subscribe_for_connector(
        self,
        connector_id: UUID,
        *,
        events: list[str] | None = None,
    ) -> str | None:
        """Subscribe webhooks for a freshly-installed connector.

        Returns the persisted subscription id (string from the provider) or
        None when the connector doesn't support webhooks / subscription
        failed.
        """
        connector_row = await self._session.get(ConnectorRow, connector_id)
        if connector_row is None:
            logger.warning(
                "webhook_subscriber_connector_not_found",
                connector_id=str(connector_id),
            )
            return None

        try:
            connector_cls = ConnectorRegistry.get(connector_row.kind)
        except Exception as exc:  # noqa: BLE001 — typed error logged
            logger.warning(
                "webhook_subscriber_kind_not_registered",
                kind=connector_row.kind, exc=str(exc),
            )
            return None
        if not connector_cls.metadata.capabilities.can_subscribe_webhooks:
            return None

        stored = await self._vault.get(connector_id)
        if stored is None:
            logger.warning(
                "webhook_subscriber_no_token",
                connector_id=str(connector_id),
            )
            return None

        # Build a live token: merge non-secret config + decrypted secret payload.
        metadata: dict[str, Any] = {**dict(connector_row.config), **stored.payload}
        if stored.expires_at is not None:
            metadata.setdefault("expires_at", stored.expires_at.isoformat())
        token = ConnectorToken(
            connector_name=connector_row.kind,
            token_id=stored.token_id,
            metadata=metadata,
        )

        callback_url = (
            f"{self._api_base_url}/api/v1/connectors/{connector_row.kind}/webhooks"
        )
        events_list = events if events is not None else default_event_set_for(connector_row.kind)

        try:
            subscription = await connector_cls().webhook_subscribe(
                token, events=events_list, callback_url=callback_url,
            )
        except Exception as exc:  # noqa: BLE001 — best-effort post-install
            logger.warning(
                "webhook_subscribe_failed",
                connector_id=str(connector_id),
                kind=connector_row.kind,
                exc=str(exc),
            )
            return None

        # Persist the subscription id so revoke flows can DELETE it later.
        await self._record_subscription(
            connector_row=connector_row,
            subscription_id=subscription.id,
            events=subscription.events,
            callback_url=subscription.callback_url,
        )

        logger.info(
            "webhook_subscribed",
            connector_id=str(connector_id),
            kind=connector_row.kind,
            subscription_id=subscription.id,
            events_count=len(subscription.events),
        )
        return subscription.id

    async def _record_subscription(
        self,
        *,
        connector_row: ConnectorRow,
        subscription_id: str,
        events: list[str],
        callback_url: str,
    ) -> None:
        config = dict(connector_row.config)
        config["webhook_subscription_id"] = subscription_id
        config["webhook_events"] = events
        config["webhook_callback_url"] = callback_url
        connector_row.config = config
        # SQLAlchemy doesn't always notice mutations of a JSONB column when
        # the dict is replaced; mark dirty explicitly.
        from sqlalchemy.orm.attributes import flag_modified  # noqa: PLC0415
        flag_modified(connector_row, "config")
        # Reference JSONB so this import isn't unused in environments where
        # the runtime ORM module didn't trigger it transitively.
        _ = JSONB
        # Reference select so the type-imported constant doesn't get pruned.
        _ = select
        await self._session.flush()
