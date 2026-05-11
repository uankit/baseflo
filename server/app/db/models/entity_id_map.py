"""EntityIdMap — (source, source_id) ↔ canonical_id mapping per project.

Per docs/01-architecture.md §4. The reconciler, backfill runner, and row
upserter all consult this table to find the canonical row id for a row
arriving from a connector. Reverse lookup (canonical_id → source_ids) is
also indexed.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base import Base, uuid7_default


class EntityIdMap(Base):
    __tablename__ = "entity_id_map"
    __table_args__ = (
        UniqueConstraint(
            "project_id", "entity_kind", "source", "source_id",
            name="uq__entity_id_map__project_id__entity_kind__source__source_id",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid7_default,
    )
    organization_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(
            "organizations.id", ondelete="CASCADE",
            name="fk__entity_id_map__organization_id__organizations",
        ),
        nullable=False,
    )
    project_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(
            "projects.id", ondelete="CASCADE",
            name="fk__entity_id_map__project_id__projects",
        ),
        nullable=False,
    )
    entity_kind: Mapped[str] = mapped_column(String(64), nullable=False)
    source: Mapped[str] = mapped_column(String(60), nullable=False)
    source_id: Mapped[str] = mapped_column(String(255), nullable=False)
    canonical_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
    )
