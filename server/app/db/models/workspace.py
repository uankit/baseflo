"""Workspace — grouping inside an organization that holds projects."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, SoftDeleteMixin, TimestampedMixin, uuid7_default


class Workspace(Base, TimestampedMixin, SoftDeleteMixin):
    __tablename__ = "workspaces"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "slug", name="uq__workspaces__organization_id__slug"
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid7_default
    )
    organization_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(
            "organizations.id",
            ondelete="CASCADE",
            name="fk__workspaces__organization_id__organizations",
        ),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(80), nullable=False)
    created_by: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT", name="fk__workspaces__created_by__users"),
        nullable=False,
    )
