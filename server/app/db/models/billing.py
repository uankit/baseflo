"""BillingSubscription — provider-side subscription record."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampedMixin, uuid7_default


class BillingProvider(StrEnum):
    STRIPE = "stripe"


class BillingSubscription(Base, TimestampedMixin):
    __tablename__ = "billing_subscriptions"
    __table_args__ = (
        CheckConstraint(
            "provider IN ('stripe')",
            name="provider_enum",
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid7_default)
    organization_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE", name="fk__billing_subscriptions__organization_id__organizations"),
        nullable=False,
    )
    provider: Mapped[str] = mapped_column(String(20), nullable=False, default=BillingProvider.STRIPE)
    external_subscription_id: Mapped[str] = mapped_column(String(255), nullable=False)
    plan: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    current_period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
