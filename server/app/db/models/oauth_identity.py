"""OAuthIdentity — provider linkage for a user.

Per docs/40-features/AUTH.md §3.4, supports Google/GitHub/Microsoft for v1.
"""

from __future__ import annotations

from enum import StrEnum
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampedMixin, uuid7_default


class OAuthProvider(StrEnum):
    GOOGLE = "google"
    GITHUB = "github"
    MICROSOFT = "microsoft"


class OAuthIdentity(Base, TimestampedMixin):
    __tablename__ = "oauth_identities"
    __table_args__ = (
        UniqueConstraint("provider", "subject", name="uq__oauth_identities__provider__subject"),
        CheckConstraint(
            "provider IN ('google', 'github', 'microsoft')",
            name="provider_enum",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid7_default
    )
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE", name="fk__oauth_identities__user_id__users"),
        nullable=False,
    )
    provider: Mapped[str] = mapped_column(String(20), nullable=False)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
