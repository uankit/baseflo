"""tenant_data_applications — track which DDL has been applied per project.

Per docs/01-architecture.md §4 (data plane). The control plane records every
SchemaApplier run so re-applies are idempotent (short-circuit by ir_hash) and
ALTER plans (M2) can find the parent application to compute deltas against.

Also grants `baseflo_app` the CREATE privilege on the database so the
runtime applier can `CREATE SCHEMA` on a fresh project. (Test/dev runs as
superuser so the GRANT is conditional on the role's existence.)

Revision ID: 0015_tenant_data_applications
Revises: 0014_auth_membership_lookup_function
Create Date: 2026-05-07
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0015_tenant_data_applications"
down_revision: str | None = "0014_auth_membership_lookup_function"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "tenant_data_applications",
        sa.Column(
            "id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True,
        ),
        sa.Column(
            "organization_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "organizations.id", ondelete="CASCADE",
                name="fk__tenant_data_applications__organization_id__organizations",
            ),
            nullable=False,
        ),
        sa.Column(
            "project_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "projects.id", ondelete="CASCADE",
                name="fk__tenant_data_applications__project_id__projects",
            ),
            nullable=False,
        ),
        sa.Column("schema_name", sa.String(120), nullable=False),
        sa.Column("ir_hash", sa.String(64), nullable=False),
        sa.Column("parent_ir_hash", sa.String(64), nullable=True),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("statements_count", sa.Integer(), nullable=False),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("error_text", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "kind IN ('initial', 'alter')",
            name="ck__tenant_data_applications__kind_enum",
        ),
        sa.CheckConstraint(
            "status IN ('succeeded', 'failed')",
            name="ck__tenant_data_applications__status_enum",
        ),
        sa.UniqueConstraint(
            "project_id", "ir_hash",
            name="uq__tenant_data_applications__project_id__ir_hash",
        ),
    )
    op.create_index(
        "ix__tenant_data_applications__project_id__applied_at",
        "tenant_data_applications",
        ["project_id", "applied_at"],
    )

    # RLS — direct organization_id scope.
    op.execute("ALTER TABLE tenant_data_applications ENABLE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON tenant_data_applications
        USING (organization_id = current_setting('app.organization_id', true)::uuid)
        WITH CHECK (organization_id = current_setting('app.organization_id', true)::uuid);
        """
    )

    # Allow the application role to CREATE schemas at runtime (Hosted Cloud
    # writes per-tenant schemas inside the control-plane database for M0).
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'baseflo_app') THEN
                EXECUTE 'GRANT CREATE ON DATABASE ' || current_database()
                        || ' TO baseflo_app';
            END IF;
        END$$;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'baseflo_app') THEN
                EXECUTE 'REVOKE CREATE ON DATABASE ' || current_database()
                        || ' FROM baseflo_app';
            END IF;
        END$$;
        """
    )
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON tenant_data_applications")
    op.execute("ALTER TABLE tenant_data_applications DISABLE ROW LEVEL SECURITY")
    op.drop_index(
        "ix__tenant_data_applications__project_id__applied_at",
        table_name="tenant_data_applications",
    )
    op.drop_table("tenant_data_applications")
