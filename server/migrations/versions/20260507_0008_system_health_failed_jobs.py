"""system_health, failed_jobs

Revision ID: 0008_system_health_failed_jobs
Revises: 0007_audit_digests_apikeys_billing
Create Date: 2026-05-07
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008_system_health_failed_jobs"
down_revision: str | None = "0007_audit_digests_apikeys_billing"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "system_health",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("worker_id", sa.String(120), nullable=False),
        sa.Column("metric", sa.String(60), nullable=False),
        sa.Column("value", sa.Float, nullable=False),
        sa.Column("extra", sa.dialects.postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "ix__system_health__worker_id__recorded_at",
        "system_health",
        ["worker_id", sa.text("recorded_at DESC")],
    )

    op.create_table(
        "failed_jobs",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("job_kind", sa.String(60), nullable=False),
        sa.Column("job_payload", sa.dialects.postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("error", sa.dialects.postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("attempt_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("failed_jobs")
    op.drop_index("ix__system_health__worker_id__recorded_at", table_name="system_health")
    op.drop_table("system_health")
