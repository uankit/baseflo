"""add_artifacts_table

Revision ID: 5ce6c0a75b9d
Revises: 0023_share_token_rls
Create Date: 2026-05-10 22:50:50.879693
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = '5ce6c0a75b9d'
down_revision: str | None = '0023_share_token_rls'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "artifacts",
        sa.Column("artifact_id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("artifact_type", sa.String(length=64), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("provenance", sa.JSON(), nullable=False),
        sa.Column("produced_by", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("artifact_id"),
        sa.Index("ix_artifacts_project_id_type_version", "project_id", "artifact_type", "version"),
    )


def downgrade() -> None:
    op.drop_table("artifacts")
