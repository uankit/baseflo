"""MagicLinkToken — passwordless sign-in token.

Per docs/40-features/AUTH.md §3.3. The table holds `sha256(raw_token)`
as `token_hash`; the raw token is delivered via email and never persisted.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, LargeBinary, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import CITEXT, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base import Base, uuid7_default


class MagicLinkToken(Base):
    __tablename__ = "magic_link_tokens"
    __table_args__ = (
        UniqueConstraint("token_hash", name="uq__magic_link_tokens__token_hash"),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid7_default,
    )
    email: Mapped[str] = mapped_column(CITEXT, nullable=False)
    token_hash: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None,
    )
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True, default=None)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
    )

    def __repr__(self) -> str:
        return (
            f"MagicLinkToken(id={self.id!s}, email={self.email!r}, "
            f"expires_at={self.expires_at!s}, "
            f"consumed={self.consumed_at is not None})"
        )
