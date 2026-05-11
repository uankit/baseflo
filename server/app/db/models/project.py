"""Project + ProjectVersion — the connected business and its immutable versions."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, LargeBinary, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base import Base, SoftDeleteMixin, TimestampedMixin, uuid7_default


class DeploymentMode(StrEnum):
    HOSTED = "hosted"
    BYO_DB = "byo_db"
    SELF_HOST = "self_host"
    LOCAL_DEV = "local_dev"


class ValidationStatus(StrEnum):
    PASSED = "passed"
    WARNING = "warning"
    FAILED = "failed"
    PENDING = "pending"


class Project(Base, TimestampedMixin, SoftDeleteMixin):
    __tablename__ = "projects"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "workspace_id", "slug",
            name="uq__projects__organization_id__workspace_id__slug",
        ),
        CheckConstraint(
            "deployment_mode IN ('hosted', 'byo_db', 'self_host', 'local_dev')",
            name="deployment_mode_enum",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid7_default
    )
    organization_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE", name="fk__projects__organization_id__organizations"),
        nullable=False,
    )
    workspace_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE", name="fk__projects__workspace_id__workspaces"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(80), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)
    current_version_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True, default=None
    )
    deployment_mode: Mapped[str] = mapped_column(
        String(20), nullable=False, default=DeploymentMode.HOSTED
    )
    tenant_data_dsn_encrypted: Mapped[bytes | None] = mapped_column(
        LargeBinary, nullable=True, default=None
    )
    tenant_data_schema_name: Mapped[str | None] = mapped_column(
        String(120), nullable=True, default=None
    )
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    created_by: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT", name="fk__projects__created_by__users"),
        nullable=False,
    )


class ProjectVersion(Base):
    __tablename__ = "project_versions"
    __table_args__ = (
        UniqueConstraint(
            "project_id", "version_number",
            name="uq__project_versions__project_id__version_number",
        ),
        CheckConstraint(
            "validation_status IN ('passed', 'warning', 'failed', 'pending')",
            name="validation_status_enum",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid7_default
    )
    project_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE", name="fk__project_versions__project_id__projects"),
        nullable=False,
    )
    parent_version_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(
            "project_versions.id", ondelete="SET NULL",
            name="fk__project_versions__parent_version_id__project_versions",
        ),
        nullable=True,
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    schema_ir: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    kpi_definitions: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    dashboard_spec: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    intelligence_taxonomy: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    assumptions: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    validation_status: Mapped[str] = mapped_column(String(20), nullable=False, default=ValidationStatus.PENDING)
    validation_report: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_by: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL", name="fk__project_versions__created_by__users"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
