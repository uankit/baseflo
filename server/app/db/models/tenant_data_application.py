"""TenantDataApplication — record of one DDL application against a tenant
schema.

Used by `SchemaApplier` to short-circuit redundant re-applies (same `ir_hash`
already succeeded for a project) and by the refinement path to find a
parent `ir_hash` from which to compute an ALTER plan.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base import Base, uuid7_default


class TenantDataApplicationKind(StrEnum):
    INITIAL = "initial"
    ALTER = "alter"


class TenantDataApplicationStatus(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class TenantDataApplication(Base):
    __tablename__ = "tenant_data_applications"
    __table_args__ = (
        UniqueConstraint(
            "project_id", "ir_hash",
            name="uq__tenant_data_applications__project_id__ir_hash",
        ),
        CheckConstraint(
            "kind IN ('initial', 'alter')",
            name="kind_enum",
        ),
        CheckConstraint(
            "status IN ('succeeded', 'failed')",
            name="status_enum",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid7_default,
    )
    organization_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(
            "organizations.id", ondelete="CASCADE",
            name="fk__tenant_data_applications__organization_id__organizations",
        ),
        nullable=False,
    )
    project_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(
            "projects.id", ondelete="CASCADE",
            name="fk__tenant_data_applications__project_id__projects",
        ),
        nullable=False,
    )
    schema_name: Mapped[str] = mapped_column(String(120), nullable=False)
    ir_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    parent_ir_hash: Mapped[str | None] = mapped_column(
        String(64), nullable=True, default=None,
    )
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    statements_count: Mapped[int] = mapped_column(Integer, nullable=False)
    applied_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    error_text: Mapped[str | None] = mapped_column(
        Text, nullable=True, default=None,
    )

    def __repr__(self) -> str:
        return (
            f"TenantDataApplication(id={self.id!s}, project_id={self.project_id!s}, "
            f"kind={self.kind!r}, status={self.status!r}, "
            f"ir_hash={self.ir_hash[:8]}…)"
        )
