"""conversations, conversation_messages, conversation_events

Revision ID: 0004_conversations_events
Revises: 0003_connectors_tokens
Create Date: 2026-05-07
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_conversations_events"
down_revision: str | None = "0003_connectors_tokens"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "conversations",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "organizations.id", ondelete="CASCADE",
                name="fk__conversations__organization_id__organizations",
            ),
            nullable=False,
        ),
        sa.Column(
            "project_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "projects.id", ondelete="CASCADE",
                name="fk__conversations__project_id__projects",
            ),
            nullable=False,
        ),
        sa.Column(
            "started_by",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT", name="fk__conversations__started_by__users"),
            nullable=False,
        ),
        sa.Column("state", sa.String(30), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "state IN ('active', 'awaiting_clarification', 'closed')",
            name="ck__conversations__state_enum",
        ),
    )
    op.execute(
        "CREATE TRIGGER set_updated_at BEFORE UPDATE ON conversations "
        "FOR EACH ROW EXECUTE FUNCTION baseflo_set_updated_at();"
    )

    op.create_table(
        "conversation_messages",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "conversation_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "conversations.id", ondelete="CASCADE",
                name="fk__conversation_messages__conversation_id__conversations",
            ),
            nullable=False,
        ),
        sa.Column("author", sa.String(20), nullable=False),
        sa.Column("agent_name", sa.String(80), nullable=True),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("extra", sa.dialects.postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "author IN ('user', 'system', 'agent')",
            name="ck__conversation_messages__author_enum",
        ),
    )

    op.create_table(
        "conversation_events",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "conversation_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "conversations.id", ondelete="CASCADE",
                name="fk__conversation_events__conversation_id__conversations",
            ),
            nullable=False,
        ),
        sa.Column("sequence", sa.BigInteger, nullable=False),
        sa.Column("event_type", sa.String(60), nullable=False),
        sa.Column("payload", sa.dialects.postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint(
            "conversation_id", "sequence",
            name="uq__conversation_events__conversation_id__sequence",
        ),
    )
    op.create_index(
        "ix__conversation_events__created_at",
        "conversation_events",
        ["created_at"],
    )

    # ----- LISTEN/NOTIFY trigger: every insert NOTIFY's the conversation channel -----
    op.execute(
        """
        CREATE OR REPLACE FUNCTION baseflo_conversation_event_notify()
        RETURNS TRIGGER AS $$
        BEGIN
            PERFORM pg_notify(
                'conversation_' || NEW.conversation_id::text,
                NEW.sequence::text
            );
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER conversation_event_notify_trigger
        AFTER INSERT ON conversation_events
        FOR EACH ROW EXECUTE FUNCTION baseflo_conversation_event_notify();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS conversation_event_notify_trigger ON conversation_events")
    op.execute("DROP FUNCTION IF EXISTS baseflo_conversation_event_notify()")
    op.drop_index("ix__conversation_events__created_at", table_name="conversation_events")
    op.drop_table("conversation_events")
    op.drop_table("conversation_messages")
    op.execute("DROP TRIGGER IF EXISTS set_updated_at ON conversations")
    op.drop_table("conversations")
