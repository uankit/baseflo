"""Lucia-style sessions: raw token in cookie, sha256 in DB.

Per docs/40-features/AUTH.md §3.3.

Lifecycle:
  1. Sign-in → `SessionService.create(user_id)` → returns `IssuedSession`
     containing the raw token. The route writes the cookie; only the hash is
     persisted.
  2. Subsequent request → middleware reads cookie, calls `validate(raw)` to
     resolve the user.
  3. Sign-out → `revoke(session_id)`.
  4. Idle expiry → 30 days; refresh slides expiry forward on each request.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol
from uuid import UUID

from app.core.crypto.hashing import generate_token_urlsafe, hash_high_entropy_token
from app.observability.logging import get_logger

__all__ = [
    "IssuedSession",
    "ResolvedSession",
    "SessionRepository",
    "SessionService",
    "StoredSession",
]


logger = get_logger("auth.sessions")


# ---------- Repository protocol ----------


@dataclass(frozen=True, slots=True)
class StoredSession:
    """Repository read shape — carries the fields the service needs to validate."""

    session_id: UUID
    user_id: UUID
    expires_at: datetime
    revoked_at: datetime | None


class SessionRepository(Protocol):
    async def create(
        self,
        *,
        user_id: UUID,
        token_hash: bytes,
        expires_at: datetime,
        user_agent: str | None,
        ip_address: str | None,
    ) -> StoredSession: ...

    async def find_by_token_hash(self, token_hash: bytes) -> StoredSession | None: ...

    async def revoke(self, session_id: UUID, revoked_at: datetime) -> None: ...

    async def extend(self, session_id: UUID, new_expires_at: datetime) -> None: ...


# ---------- Service-facing types ----------


@dataclass(frozen=True, slots=True)
class IssuedSession:
    """Result of `SessionService.create` — includes the raw token for the cookie."""

    session_id: UUID
    user_id: UUID
    raw_token: str
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class ResolvedSession:
    """Result of `SessionService.validate` — the active session bound to a user."""

    session_id: UUID
    user_id: UUID
    expires_at: datetime


# ---------- Service ----------


class SessionService:
    DEFAULT_TTL = timedelta(days=30)

    def __init__(
        self,
        *,
        repo: SessionRepository,
        ttl: timedelta = DEFAULT_TTL,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._repo = repo
        self._ttl = ttl
        self._clock = clock

    @property
    def ttl(self) -> timedelta:
        return self._ttl

    async def create(
        self,
        *,
        user_id: UUID,
        user_agent: str | None = None,
        ip_address: str | None = None,
    ) -> IssuedSession:
        raw_token = generate_token_urlsafe(num_bytes=32)
        token_hash = hash_high_entropy_token(raw_token)
        expires_at = self._clock() + self._ttl
        record = await self._repo.create(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
            user_agent=user_agent,
            ip_address=ip_address,
        )
        logger.info(
            "session_created",
            session_id=str(record.session_id),
            user_id=str(user_id),
            expires_at=expires_at.isoformat(),
        )
        return IssuedSession(
            session_id=record.session_id,
            user_id=record.user_id,
            raw_token=raw_token,
            expires_at=record.expires_at,
        )

    async def validate(self, raw_token: str) -> ResolvedSession | None:
        """Return an active session for `raw_token`, or None if invalid.

        "Invalid" covers all of: unknown, revoked, or past `expires_at`.
        """
        record = await self._repo.find_by_token_hash(hash_high_entropy_token(raw_token))
        if record is None:
            return None
        if record.revoked_at is not None:
            return None
        if record.expires_at <= self._clock():
            return None
        return ResolvedSession(
            session_id=record.session_id,
            user_id=record.user_id,
            expires_at=record.expires_at,
        )

    async def refresh(self, session_id: UUID) -> datetime:
        """Slide expiry forward by TTL. Returns the new `expires_at`."""
        new_expiry = self._clock() + self._ttl
        await self._repo.extend(session_id, new_expiry)
        return new_expiry

    async def revoke(self, session_id: UUID) -> None:
        await self._repo.revoke(session_id, self._clock())
        logger.info("session_revoked", session_id=str(session_id))
