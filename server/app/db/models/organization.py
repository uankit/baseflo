"""Organization — billing entity; one or more users, one or more workspaces."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import CheckConstraint, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, SoftDeleteMixin, TimestampedMixin, uuid7_default


class OrganizationPlan(StrEnum):
    HOBBY = "hobby"
    PRO = "pro"
    BUSINESS = "business"
    ENTERPRISE = "enterprise"


class OrganizationStatus(StrEnum):
    ACTIVE = "active"
    PAUSED = "paused"
    CANCELLED = "cancelled"


class Organization(Base, TimestampedMixin, SoftDeleteMixin):
    __tablename__ = "organizations"
    __table_args__ = (
        UniqueConstraint("slug", name="uq__organizations__slug"),
        CheckConstraint(
            "plan IN ('hobby', 'pro', 'business', 'enterprise')",
            name="plan_enum",
        ),
        CheckConstraint(
            "status IN ('active', 'paused', 'cancelled')",
            name="status_enum",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid7_default
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(80), nullable=False)
    plan: Mapped[str] = mapped_column(String(20), nullable=False, default=OrganizationPlan.HOBBY)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=OrganizationStatus.ACTIVE
    )
    kms_key_arn: Mapped[str | None] = mapped_column(String(500), nullable=True, default=None)
    region: Mapped[str] = mapped_column(String(20), nullable=False, default="us-east-1")
    # Inherited: created_at, updated_at, deleted_at

    def __repr__(self) -> str:
        return f"Organization(id={self.id!s}, slug={self.slug!r}, plan={self.plan!r})"

    # Convenience for typed access in code that uses the enums:

    @property
    def plan_enum(self) -> OrganizationPlan:
        return OrganizationPlan(self.plan)

    @property
    def status_enum(self) -> OrganizationStatus:
        return OrganizationStatus(self.status)


# Re-export for typing
_ = datetime
