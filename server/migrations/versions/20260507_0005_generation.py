"""generation_jobs, generation_steps, agent_runs, agent_run_attempts

Revision ID: 0005_generation
Revises: 0004_conversations_events
Create Date: 2026-05-07
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_generation"
down_revision: str | None = "0004_conversations_events"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "generation_jobs",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "project_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "projects.id", ondelete="CASCADE",
                name="fk__generation_jobs__project_id__projects",
            ),
            nullable=False,
        ),
        sa.Column(
            "parent_version_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "project_versions.id", ondelete="SET NULL",
                name="fk__generation_jobs__parent_version_id__project_versions",
            ),
            nullable=True,
        ),
        sa.Column("kind", sa.String(40), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="queued"),
        sa.Column("idempotency_key", sa.String(120), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.dialects.postgresql.JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("idempotency_key", name="uq__generation_jobs__idempotency_key"),
        sa.CheckConstraint(
            "kind IN ('initial', 'refinement', 'connector_added', 're_introspect')",
            name="ck__generation_jobs__kind_enum",
        ),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'succeeded', 'failed', 'cancelled')",
            name="ck__generation_jobs__status_enum",
        ),
    )
    op.execute(
        "CREATE TRIGGER set_updated_at BEFORE UPDATE ON generation_jobs "
        "FOR EACH ROW EXECUTE FUNCTION baseflo_set_updated_at();"
    )

    op.create_table(
        "generation_steps",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "job_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "generation_jobs.id", ondelete="CASCADE",
                name="fk__generation_steps__job_id__generation_jobs",
            ),
            nullable=False,
        ),
        sa.Column("step_name", sa.String(80), nullable=False),
        sa.Column("step_index", sa.Integer, nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("input_hash", sa.String(64), nullable=True),
        sa.Column("output_hash", sa.String(64), nullable=True),
        sa.Column("validation_status", sa.String(20), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.dialects.postgresql.JSONB, nullable=True),
        sa.UniqueConstraint("job_id", "step_index", name="uq__generation_steps__job_id__step_index"),
        sa.CheckConstraint(
            "status IN ('pending', 'running', 'passed', 'warning', 'failed', 'skipped')",
            name="ck__generation_steps__status_enum",
        ),
    )

    op.create_table(
        "agent_runs",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "step_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "generation_steps.id", ondelete="CASCADE",
                name="fk__agent_runs__step_id__generation_steps",
            ),
            nullable=False,
        ),
        sa.Column("agent_name", sa.String(80), nullable=False),
        sa.Column("model_tier", sa.String(20), nullable=False),
        sa.Column("model_name", sa.String(120), nullable=False),
        sa.Column("input_hash", sa.String(64), nullable=False),
        sa.Column("output_hash", sa.String(64), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duration_ms", sa.Integer, nullable=False),
        sa.Column("input_tokens", sa.Integer, nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer, nullable=False, server_default="0"),
        sa.Column("cache_read_tokens", sa.Integer, nullable=False, server_default="0"),
        sa.Column("cache_write_tokens", sa.Integer, nullable=False, server_default="0"),
        sa.Column("repair_attempts", sa.Integer, nullable=False, server_default="0"),
        sa.Column("escalated", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("final_status", sa.String(30), nullable=False),
        sa.CheckConstraint(
            "final_status IN ('passed', 'warning', 'failed', 'needs_clarification')",
            name="ck__agent_runs__final_status_enum",
        ),
    )

    op.create_table(
        "agent_run_attempts",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "agent_run_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "agent_runs.id", ondelete="CASCADE",
                name="fk__agent_run_attempts__agent_run_id__agent_runs",
            ),
            nullable=False,
        ),
        sa.Column("attempt_number", sa.Integer, nullable=False),
        sa.Column("prompt_hash", sa.String(64), nullable=False),
        sa.Column("output_payload", sa.dialects.postgresql.JSONB, nullable=True),
        sa.Column("validation_error", sa.dialects.postgresql.JSONB, nullable=True),
        sa.Column("usage", sa.dialects.postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("agent_run_attempts")
    op.drop_table("agent_runs")
    op.drop_table("generation_steps")
    op.execute("DROP TRIGGER IF EXISTS set_updated_at ON generation_jobs")
    op.drop_table("generation_jobs")
