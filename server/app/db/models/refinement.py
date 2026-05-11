"""Refinement — typed evolution intent + plan + child-version pointer."""

from __future__ import annotations

from enum import StrEnum
from typing import Any
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampedMixin, uuid7_default


class RefinementStatus(StrEnum):
    PROPOSED = "proposed"
    APPLIED = "applied"
    DISCARDED = "discarded"
    FAILED = "failed"


class Refinement(Base, TimestampedMixin):
    __tablename__ = "refinements"
    __table_args__ = (
        CheckConstraint(
            "status IN ('proposed', 'applied', 'discarded', 'failed')",
            name="status_enum",
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid7_default)
    project_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE", name="fk__refinements__project_id__projects"),
        nullable=False,
    )
    parent_version_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(
            "project_versions.id", ondelete="RESTRICT",
            name="fk__refinements__parent_version_id__project_versions",
        ),
        nullable=False,
    )
    child_version_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(
            "project_versions.id", ondelete="SET NULL",
            name="fk__refinements__child_version_id__project_versions",
        ),
        nullable=True,
    )
    intent_text: Mapped[str] = mapped_column(Text, nullable=False)
    interpreted_intent: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    change_plan: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    impact_summary: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=RefinementStatus.PROPOSED)
    created_by: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT", name="fk__refinements__created_by__users"),
        nullable=False,
    )
