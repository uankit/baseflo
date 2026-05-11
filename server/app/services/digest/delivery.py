"""Digest delivery adapters.

Per docs/40-features/DIGEST.md §3.5 + §4 (Strategy pattern). Each adapter
fronts a specific channel:

  - `LogDelivery`     — structlog-only; the M1 default when no provider key
                        is configured. Useful in dev + tests.
  - `ResendDelivery`  — real Resend HTTP API integration. Activated when
                        `BASEFLO_DIGEST_RESEND_API_KEY` is set.
  - Slack / webhook   — not available in v1.

The adapters share a tiny `DigestDeliveryAdapter` Protocol so the runner
can inject any of them without compile-time coupling.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import httpx

from app.core.config import get_config
from app.core.errors import BasefloError
from app.observability.logging import get_logger
from app.services.digest.render import render_html, render_text
from app.services.digest.types import DigestEmail


__all__ = [
    "DeliveryError",
    "DeliveryResult",
    "DigestDeliveryAdapter",
    "LogDelivery",
    "ResendDelivery",
    "default_delivery_adapter",
]


logger = get_logger("services.digest.delivery")


# ---------- Types ----------


class DeliveryError(BasefloError):
    """Delivery provider rejected the request. Raised with BF-DIG-002."""

    def __init__(self, message: str, *, details: dict[str, object] | None = None) -> None:
        super().__init__(
            error_code="BF-DIG-002",
            message=message,
            status_code=502,
            details=dict(details or {}),
        )


@dataclass(frozen=True, slots=True)
class DeliveryResult:
    """Provider-side identifier + an `accepted` flag for runner bookkeeping."""

    provider: str
    provider_message_id: str | None
    accepted: bool


class DigestDeliveryAdapter(Protocol):
    """Strategy interface; one method, one job."""

    async def send(
        self, *, email: DigestEmail, recipient: str
    ) -> DeliveryResult: ...


# ---------- LogDelivery: M1 default fallback ----------


class LogDelivery:
    """Logs the rendered digest at INFO; useful in dev + tests.

    Returns a stable `DeliveryResult` with `accepted=True` so callers can
    flow as if the email left the building.
    """

    async def send(
        self, *, email: DigestEmail, recipient: str
    ) -> DeliveryResult:
        body = render_text(email)
        logger.info(
            "digest_delivered_via_log",
            recipient=recipient,
            project_id=str(email.project_id),
            user_id=str(email.user_id),
            subject=email.subject,
            section_count=len(email.sections),
            body=body,
        )
        return DeliveryResult(
            provider="log", provider_message_id=None, accepted=True,
        )


# ---------- ResendDelivery: M1 production adapter ----------


class ResendDelivery:
    """Resend HTTP API adapter.

    `api_key` defaults to `BASEFLO_DIGEST_RESEND_API_KEY` from env; pass
    explicitly in tests. The adapter is async-friendly — uses httpx's async
    client with a 10s timeout.

    Why Resend (vs Postmark) for M1: lower friction (single secret, no
    domain-verification gate to ship dev-mode digests). Postmark adapter is
    architecturally identical.
    """

    def __init__(
        self,
        *,
        api_key: str,
        from_address: str,
        endpoint: str = "https://api.resend.com/emails",
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._api_key = api_key
        self._from = from_address
        self._endpoint = endpoint
        # `transport` is plumbed for tests to plug a `MockTransport`. Production
        # callers leave it None so httpx picks the default async transport.
        self._transport = transport

    async def send(
        self, *, email: DigestEmail, recipient: str
    ) -> DeliveryResult:
        payload = {
            "from": self._from,
            "to": [recipient],
            "subject": email.subject,
            "text": render_text(email),
            "html": render_html(email),
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        client_kwargs: dict[str, object] = {"timeout": 10.0}
        if self._transport is not None:
            client_kwargs["transport"] = self._transport
        try:
            async with httpx.AsyncClient(**client_kwargs) as client:  # type: ignore[arg-type]
                response = await client.post(
                    self._endpoint, json=payload, headers=headers
                )
        except httpx.HTTPError as exc:
            raise DeliveryError(
                f"Resend transport failed: {exc!r}",
                details={"recipient": recipient, "exception": type(exc).__name__},
            ) from exc

        if response.status_code >= 400:
            raise DeliveryError(
                f"Resend rejected delivery (status={response.status_code}).",
                details={
                    "status": response.status_code,
                    "recipient": recipient,
                    "response_text": response.text[:500],
                },
            )

        try:
            body = response.json()
        except ValueError:
            body = {}
        provider_id = (
            body.get("id") if isinstance(body, dict) else None
        )
        return DeliveryResult(
            provider="resend",
            provider_message_id=provider_id if isinstance(provider_id, str) else None,
            accepted=True,
        )


# ---------- Selector ----------


def default_delivery_adapter() -> DigestDeliveryAdapter:
    """Return the right adapter for the current process configuration.

    Order:
      1. If `BASEFLO_DIGEST_RESEND_API_KEY` is set → `ResendDelivery`.
      2. Otherwise → `LogDelivery` (M1 dev default).
    """
    config = get_config()
    if config.digest_resend_api_key is not None:
        return ResendDelivery(
            api_key=config.digest_resend_api_key.get_secret_value(),
            from_address=config.digest_email_from,
            endpoint=config.digest_resend_endpoint,
        )
    return LogDelivery()
