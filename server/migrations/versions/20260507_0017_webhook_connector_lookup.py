"""SECURITY DEFINER function for resolving a webhook delivery to its tenant.

Webhook receive endpoints have no authenticated session (the source is a
provider, not a user). We need to find the `(connector, project,
organization)` triple from a routing key (Shopify shop_domain, Stripe
account, Sheets channel-token). Connectors are RLS-scoped, so a normal
SELECT can't see them without an active tenant. The SECURITY DEFINER
function bypasses RLS for this single, well-defined lookup.

The function also returns the project's current `tenant_data_schema_name`
and `current_version_id` so the caller can load the IR + apply RLS scope
without a second round-trip.

Revision ID: 0017_webhook_connector_lookup
Revises: 0016_entity_id_map
Create Date: 2026-05-07
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op


revision: str = "0017_webhook_connector_lookup"
down_revision: str | None = "0016_entity_id_map"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION app_lookup_connector_for_webhook(
            p_kind TEXT,
            p_routing_field TEXT,
            p_routing_value TEXT
        )
        RETURNS TABLE(
            connector_id UUID,
            organization_id UUID,
            project_id UUID,
            schema_name TEXT,
            current_version_id UUID
        )
        LANGUAGE sql
        SECURITY DEFINER
        SET search_path = public
        AS $$
            SELECT
                c.id,
                c.organization_id,
                c.project_id,
                p.tenant_data_schema_name,
                p.current_version_id
            FROM connectors c
            JOIN projects p ON p.id = c.project_id
            WHERE c.kind = p_kind
              AND c.config->>p_routing_field = p_routing_value
              AND c.deleted_at IS NULL
              AND c.status = 'connected'
              AND p.deleted_at IS NULL
            LIMIT 1;
        $$;
        """
    )
    op.execute(
        "REVOKE ALL ON FUNCTION "
        "app_lookup_connector_for_webhook(TEXT, TEXT, TEXT) FROM PUBLIC"
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'baseflo_app') THEN
                EXECUTE 'GRANT EXECUTE ON FUNCTION '
                        || 'app_lookup_connector_for_webhook(TEXT, TEXT, TEXT) '
                        || 'TO baseflo_app';
            END IF;
        END$$;
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP FUNCTION IF EXISTS app_lookup_connector_for_webhook(TEXT, TEXT, TEXT)"
    )
