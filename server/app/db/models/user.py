"""User — auth identity. Belongs to one or more organizations via memberships."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import CITEXT, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, SoftDeleteMixin, TimestampedMixin, uuid7_default


class User(Base, TimestampedMixin, SoftDeleteMixin):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("email", name="uq__users__email"),)

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid7_default
    )
    email: Mapped[str] = mapped_column(CITEXT, nullable=False)
    email_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
    display_name: Mapped[str | None] = mapped_column(String(200), nullable=True, default=None)
    password_hash: Mapped[str | None] = mapped_column(String(500), nullable=True, default=None)
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
    # Inherited: created_at, updated_at, deleted_at

    def __repr__(self) -> str:
        return f"User(id={self.id!s}, email={self.email!r})"
