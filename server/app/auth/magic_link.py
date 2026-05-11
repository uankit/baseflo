"""Magic-link sign-in service.

Per docs/40-features/AUTH.md §3.3. Single-use, short-TTL passwordless tokens
delivered via email. The service owns the full flow: token generation,
persistence (as a hash), email rendering + dispatch, and consumption with
find-or-create-user semantics.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol
from uuid import UUID

from app.core.crypto.hashing import generate_token_urlsafe, hash_high_entropy_token
from app.core.errors import BasefloError
from app.observability.logging import get_logger
from app.services.email.sender import EmailMessage, EmailSender

__all__ = [
    "IssuedMagicLink",
    "MagicLinkRecord",
    "MagicLinkRepository",
    "MagicLinkService",
    "UserDirectory",
    "UserHandle",
]


logger = get_logger("auth.magic_link")


# Conservative email-shape check: a single `@`, non-empty local + host, dot in
# host, no whitespace. RFC 5322 is intentionally not implemented — we delegate
# the deliverability question to the email provider.
_EMAIL_SHAPE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


# ---------- Repository protocols ----------


@dataclass(frozen=True, slots=True)
class MagicLinkRecord:
    """The minimal shape of a stored magic-link token row."""

    id: UUID
    email: str
    token_hash: bytes
    expires_at: datetime
    consumed_at: datetime | None


class MagicLinkRepository(Protocol):
    async def create_token(
        self,
        *,
        email: str,
        token_hash: bytes,
        expires_at: datetime,
        ip_address: str | None,
        user_agent: str | None,
    ) -> MagicLinkRecord: ...

    async def find_by_token_hash(self, token_hash: bytes) -> MagicLinkRecord | None: ...

    async def mark_consumed(self, token_id: UUID, consumed_at: datetime) -> None: ...


@dataclass(frozen=True, slots=True)
class UserHandle:
    """Just enough of `User` for the service to return upstream."""

    id: UUID
    email: str


class UserDirectory(Protocol):
    """Service-shaped slice of `UserRepository`."""

    async def find_or_create_by_email(self, email: str) -> UserHandle: ...


# ---------- Service-facing types ----------


@dataclass(frozen=True, slots=True)
class IssuedMagicLink:
    """Result of `MagicLinkService.request`."""

    token_id: UUID
    raw_token: str
    expires_at: datetime


# ---------- Errors ----------


def _raise_invalid_token() -> None:
    raise BasefloError(
        error_code="BF-AUTH-006",
        message="Magic link is invalid, expired, or has already been used.",
        status_code=410,
    )


# ---------- Service ----------


class MagicLinkService:
    """Coordinates token issuance, email delivery, and consumption."""

    DEFAULT_TTL = timedelta(minutes=15)

    def __init__(
        self,
        *,
        repo: MagicLinkRepository,
        users: UserDirectory,
        sender: EmailSender,
        verify_url_template: str,
        ttl: timedelta = DEFAULT_TTL,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        if "{token}" not in verify_url_template:
            raise ValueError(
                "verify_url_template must contain a `{token}` placeholder.",
            )
        self._repo = repo
        self._users = users
        self._sender = sender
        self._verify_url_template = verify_url_template
        self._ttl = ttl
        self._clock = clock

    async def request(
        self,
        *,
        email: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> IssuedMagicLink:
        """Generate a token, persist its hash, send the email, return metadata.

        The raw token is also returned so route handlers can log a redacted
        prefix or include the token in test responses; never expose the full
        raw token to anyone but the recipient.
        """
        normalised = email.strip().lower()
        if not _EMAIL_SHAPE.match(normalised):
            _raise_invalid_token()

        raw_token = generate_token_urlsafe(num_bytes=32)
        token_hash = hash_high_entropy_token(raw_token)
        expires_at = self._clock() + self._ttl
        record = await self._repo.create_token(
            email=normalised,
            token_hash=token_hash,
            expires_at=expires_at,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        verify_url = self._verify_url_template.format(token=raw_token)
        await self._sender.send(_render_email(to=normalised, verify_url=verify_url))

        logger.info(
            "magic_link_issued",
            token_id=str(record.id),
            email=normalised,
            expires_at=expires_at.isoformat(),
        )
        return IssuedMagicLink(
            token_id=record.id,
            raw_token=raw_token,
            expires_at=expires_at,
        )

    async def consume(self, raw_token: str) -> UserHandle:
        """Validate the token, mark consumed, return the user (creating if new).

        Raises `BF-AUTH-006` for any failure mode (unknown / expired / reused).
        """
        token_hash = hash_high_entropy_token(raw_token)
        record = await self._repo.find_by_token_hash(token_hash)
        now = self._clock()
        if record is None or record.consumed_at is not None or record.expires_at <= now:
            _raise_invalid_token()
            # mypy: _raise_invalid_token always raises.
            raise AssertionError  # pragma: no cover

        await self._repo.mark_consumed(record.id, now)
        user = await self._users.find_or_create_by_email(record.email)
        logger.info(
            "magic_link_consumed",
            token_id=str(record.id),
            email=record.email,
            user_id=str(user.id),
        )
        return user


# ---------- Email rendering ----------


def _render_email(*, to: str, verify_url: str) -> EmailMessage:
    text_body = (
        "Sign in to Baseflo by clicking the link below. "
        "It expires in 15 minutes and can only be used once.\n\n"
        f"{verify_url}\n\n"
        "If you didn't request this, ignore this email — your account is unchanged."
    )
    html_body = (
        "<p>Sign in to <strong>Baseflo</strong> by clicking the link below. "
        "It expires in 15 minutes and can only be used once.</p>"
        f'<p><a href="{verify_url}">{verify_url}</a></p>'
        "<p>If you didn't request this, ignore this email — "
        "your account is unchanged.</p>"
    )
    return EmailMessage(
        to=to,
        subject="Sign in to Baseflo",
        text_body=text_body,
        html_body=html_body,
    )
