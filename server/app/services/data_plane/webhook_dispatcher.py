"""WebhookDispatcher — receive-route → reconciler orchestration.

Per docs/01-architecture.md §4. Webhook receive endpoints have already
HMAC-verified the inbound delivery and parsed it into an `IngestedEvent`.
The dispatcher's job is the rest of the chain:

  1. Resolve `(organization, project, schema_name, current_version_id)`
     from a routing key (Shopify `shop_domain`, Stripe `account`, Sheets
     channel `spreadsheet_id`) via the SECURITY DEFINER lookup function.
  2. Set RLS scope on the session to the resolved organization.
  3. Load the project's current `SchemaIR` from `project_versions`.
  4. Build a `WebhookReconciler` with `CanonicalUpserter` + `IdResolver`
     bound to the same session.
  5. Call `reconciler.reconcile_event(...)` and return the result.

If lookup returns nothing (no connector matches the routing key), the
dispatcher logs and returns a `SKIPPED` result — the receive route still
acknowledges the webhook (HMAC verified) so providers don't retry.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crypto.envelope import EnvelopeCrypto
from app.core.crypto.kms import get_kms_client
from app.db.models.project import ProjectVersion
from app.engines.schema.ir import SchemaIR
from app.observability.logging import get_logger
from app.services.data_plane.canonical_upserter import CanonicalUpserter
from app.services.data_plane.id_resolver import IdResolver
from app.services.data_plane.webhook_reconciler import (
    ReconcileResult,
    ReconcileStatus,
    WebhookReconciler,
)
from app.services.webhook_ingest.types import IngestedEvent


__all__ = ["ConnectorRoutingMatch", "WebhookDispatcher"]


logger = get_logger("data_plane.webhook_dispatcher")


@dataclass(frozen=True, slots=True)
class ConnectorRoutingMatch:
    connector_id: UUID
    organization_id: UUID
    project_id: UUID
    schema_name: str | None
    current_version_id: UUID | None


class WebhookDispatcher:
    """One instance per webhook delivery."""

    def __init__(self, *, session: AsyncSession) -> None:
        self._session = session

    async def dispatch(
        self,
        *,
        event: IngestedEvent,
        connector_kind: str,
        routing_field: str,
        routing_value: str,
    ) -> ReconcileResult:
        match = await self._lookup_connector(
            connector_kind=connector_kind,
            routing_field=routing_field,
            routing_value=routing_value,
        )
        if match is None:
            logger.info(
                "webhook_dispatch_no_connector",
                connector_kind=connector_kind,
                routing_field=routing_field,
                routing_value=routing_value,
            )
            return ReconcileResult(
                status=ReconcileStatus.SKIPPED_NO_TABLE,
                detail=(
                    f"No installed {connector_kind} connector matches "
                    f"{routing_field}={routing_value!r}."
                ),
            )

        if match.schema_name is None or match.current_version_id is None:
            logger.info(
                "webhook_dispatch_project_not_finalized",
                project_id=str(match.project_id),
                schema_name=match.schema_name,
                current_version_id=(
                    str(match.current_version_id)
                    if match.current_version_id
                    else None
                ),
            )
            return ReconcileResult(
                status=ReconcileStatus.SKIPPED_NO_TABLE,
                detail=(
                    "Project has no current version or no canonical schema; "
                    "webhook accepted but nothing to reconcile yet."
                ),
            )

        # RLS scope: set to the matched org so subsequent queries respect tenant.
        await self._session.execute(
            text("SELECT set_config('app.organization_id', :org, true)"),
            {"org": str(match.organization_id)},
        )

        # Load the IR from the current project_version row.
        version = await self._session.get(ProjectVersion, match.current_version_id)
        if version is None or not version.schema_ir:
            return ReconcileResult(
                status=ReconcileStatus.SKIPPED_NO_TABLE,
                detail="Current project version not found or schema_ir empty.",
            )
        ir = SchemaIR.model_validate(version.schema_ir)

        upserter = CanonicalUpserter(
            tenant_session=self._session,
            schema_name=match.schema_name,
            id_resolver=IdResolver(session=self._session),
        )
        from app.services.data_plane.refetch_executor import (  # noqa: PLC0415
            RefetchExecutor,
        )

        refetch_executor = RefetchExecutor(
            session=self._session, upserter=upserter,
        )

        async def _refetch_handler(
            inner_event: IngestedEvent,
            organization_id: UUID,
            project_id: UUID,
        ) -> ReconcileResult:
            return await refetch_executor.execute(
                event=inner_event,
                organization_id=organization_id,
                project_id=project_id,
                ir=ir,
            )

        reconciler = WebhookReconciler(
            upserter=upserter,
            id_resolver=IdResolver(session=self._session),
            refetch_handler=_refetch_handler,
        )
        result = await reconciler.reconcile_event(
            event=event,
            organization_id=match.organization_id,
            project_id=match.project_id,
            ir=ir,
        )
        logger.info(
            "webhook_dispatch_completed",
            connector_kind=connector_kind,
            project_id=str(match.project_id),
            organization_id=str(match.organization_id),
            op=event.op.value,
            source_id=event.source_id,
            status=result.status,
        )
        # Reference KMS so callers that introspect dispatcher dependencies
        # know it pulls from the central client (no per-blob credential).
        _ = EnvelopeCrypto, get_kms_client
        return result

    # ---------- internal ----------

    async def _lookup_connector(
        self, *, connector_kind: str, routing_field: str, routing_value: str,
    ) -> ConnectorRoutingMatch | None:
        result = await self._session.execute(
            text(
                "SELECT connector_id, organization_id, project_id, "
                "schema_name, current_version_id "
                "FROM app_lookup_connector_for_webhook(:kind, :field, :value)"
            ),
            {
                "kind": connector_kind,
                "field": routing_field,
                "value": routing_value,
            },
        )
        row = result.mappings().first()
        if row is None:
            return None
        return ConnectorRoutingMatch(
            connector_id=row["connector_id"],
            organization_id=row["organization_id"],
            project_id=row["project_id"],
            schema_name=row["schema_name"],
            current_version_id=row["current_version_id"],
        )


# `select` re-exported for tests that introspect the SQL paths.
_ = select
