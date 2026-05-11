"""Transactional email sender.

Auth flows (magic link, password reset) deliver through this module.
Provider selection follows the digest pattern:

  - `BASEFLO_DIGEST_RESEND_API_KEY` set → `ResendEmailSender`. Auth and digest
    share the same Resend account; the env var name is historical.
  - Otherwise → `LogEmailSender` (logs at INFO; useful in dev + tests).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import httpx

from app.core.config import get_config
from app.core.errors import BasefloError
from app.observability.logging import get_logger

__all__ = [
    "EmailMessage",
    "EmailSendError",
    "EmailSender",
    "LogEmailSender",
    "ResendEmailSender",
    "default_email_sender",
]


logger = get_logger("services.email.sender")


class EmailSendError(BasefloError):
    """Provider rejected the email request."""

    def __init__(
        self, message: str, *, details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(
            error_code="BF-EMAIL-001",
            message=message,
            status_code=502,
            details=dict(details or {}),
        )


@dataclass(frozen=True, slots=True)
class EmailMessage:
    """One outbound transactional email."""

    to: str
    subject: str
    text_body: str
    html_body: str | None = None


class EmailSender(Protocol):
    """Strategy: one method, one job."""

    async def send(self, message: EmailMessage) -> str | None: ...


# ---------- LogEmailSender ----------


class LogEmailSender:
    """Logs the email at INFO; used in dev + tests."""

    async def send(self, message: EmailMessage) -> str | None:
        logger.info(
            "email_sent_via_log",
            to=message.to,
            subject=message.subject,
            text_body=message.text_body,
        )
        return None


# ---------- ResendEmailSender ----------


class ResendEmailSender:
    """Resend HTTP API adapter.

    Why Resend: low friction (single secret, no domain-verification gate to
    ship dev emails). Postmark / SES adapters are architecturally identical
    and arrive when needed.
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
        self._transport = transport

    async def send(self, message: EmailMessage) -> str | None:
        payload: dict[str, object] = {
            "from": self._from,
            "to": [message.to],
            "subject": message.subject,
            "text": message.text_body,
        }
        if message.html_body is not None:
            payload["html"] = message.html_body
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
                    self._endpoint, json=payload, headers=headers,
                )
        except httpx.HTTPError as exc:
            raise EmailSendError(
                f"Email transport failed: {exc!r}",
                details={"to": message.to, "exception": type(exc).__name__},
            ) from exc

        if response.status_code >= 400:
            raise EmailSendError(
                f"Email provider rejected message (status={response.status_code}).",
                details={
                    "status": response.status_code,
                    "to": message.to,
                    "response_text": response.text[:500],
                },
            )

        try:
            body = response.json()
        except ValueError:
            return None
        if isinstance(body, dict):
            mid = body.get("id")
            if isinstance(mid, str):
                return mid
        return None


# ---------- Selector ----------


def default_email_sender() -> EmailSender:
    """Return the right sender for the current process configuration."""
    config = get_config()
    if config.digest_resend_api_key is not None:
        return ResendEmailSender(
            api_key=config.digest_resend_api_key.get_secret_value(),
            from_address=config.digest_email_from,
            endpoint=config.digest_resend_endpoint,
        )
    return LogEmailSender()
