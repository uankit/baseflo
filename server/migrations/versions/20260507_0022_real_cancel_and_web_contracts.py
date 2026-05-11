"""real cancellation metadata and workspace-build cancelled state.

Revision ID: 0022_real_cancel_web
Revises: 0021_entity_identity_index
Create Date: 2026-05-10
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0022_real_cancel_web"
down_revision: str | None = "0021_entity_identity_index"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "generation_jobs",
        sa.Column("conversation_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk__generation_jobs__conversation_id__conversations",
        "generation_jobs",
        "conversations",
        ["conversation_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix__generation_jobs__conversation_id",
        "generation_jobs",
        ["conversation_id"],
    )

    op.drop_constraint(
        "ck__workspace_builds__status_enum",
        "workspace_builds",
        type_="check",
    )
    op.create_check_constraint(
        "ck__workspace_builds__status_enum",
        "workspace_builds",
        "status IN ('running', 'succeeded', 'failed', 'cancelled')",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck__workspace_builds__status_enum",
        "workspace_builds",
        type_="check",
    )
    op.create_check_constraint(
        "ck__workspace_builds__status_enum",
        "workspace_builds",
        "status IN ('running', 'succeeded', 'failed')",
    )
    op.drop_index("ix__generation_jobs__conversation_id", table_name="generation_jobs")
    op.drop_constraint(
        "fk__generation_jobs__conversation_id__conversations",
        "generation_jobs",
        type_="foreignkey",
    )
    op.drop_column("generation_jobs", "conversation_id")
