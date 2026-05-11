"""agent_tasks_feed_and_project_currency

Revision ID: 902637a2a6e1
Revises: 5ce6c0a75b9d
Create Date: 2026-05-11 01:11:10.942956
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "902637a2a6e1"
down_revision: str | None = "5ce6c0a75b9d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agent_feed",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("agent_id", sa.String(length=64), nullable=False),
        sa.Column("entry_type", sa.String(length=64), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "context",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name="fk__agent_feed__project_id__projects",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk__agent_feed")),
    )
    op.create_index(
        op.f("ix__agent_feed__agent_id"), "agent_feed", ["agent_id"], unique=False
    )
    op.create_index(
        op.f("ix__agent_feed__project_id"), "agent_feed", ["project_id"], unique=False
    )

    op.create_table(
        "agent_tasks",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("agent_id", sa.String(length=64), nullable=False),
        sa.Column("kind", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("result", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name="fk__agent_tasks__project_id__projects",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk__agent_tasks")),
    )
    op.create_index(
        op.f("ix__agent_tasks__agent_id"), "agent_tasks", ["agent_id"], unique=False
    )
    op.create_index(
        op.f("ix__agent_tasks__project_id"), "agent_tasks", ["project_id"], unique=False
    )

    op.add_column(
        "projects",
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="USD"),
    )


def downgrade() -> None:
    op.drop_column("projects", "currency")

    op.drop_index(op.f("ix__agent_tasks__project_id"), table_name="agent_tasks")
    op.drop_index(op.f("ix__agent_tasks__agent_id"), table_name="agent_tasks")
    op.drop_table("agent_tasks")

    op.drop_index(op.f("ix__agent_feed__project_id"), table_name="agent_feed")
    op.drop_index(op.f("ix__agent_feed__agent_id"), table_name="agent_feed")
    op.drop_table("agent_feed")
