"""WebhookReconciler — turns a verified `IngestedEvent` into a canonical-row write.

Per docs/01-architecture.md §4. The webhook receive endpoints HMAC-verify
the inbound delivery and parse it into a typed `IngestedEvent`. The
reconciler:

  - **CREATE / UPDATE**: trusts the verified payload (it carries the resource)
    and upserts directly into the canonical store. No round-trip to the
    provider — the HMAC + the parser already validated the shape.
  - **DELETE**: looks up the canonical_id via `IdResolver`, hard-deletes the
    canonical row from the per-tenant table, and deletes the matching
    `entity_id_map` entry so the next CREATE on the same source_id mints a
    fresh canonical_id. Both deletions run inside the same DB transaction.
  - **REFETCH** (Google Drive Push): the payload doesn't carry data; we hand
    off to a refetch handler that the caller wires up. If none is registered,
    we log + skip — the reconciler is correct, the data plane will fill in.

`raw` event payloads from Shopify / Stripe arrive in their native shapes
(snake_case for Stripe, camelCase for Shopify GraphQL). The reconciler
applies the same `(source_column → ir_column)` rename that
`BackfillRunner` uses, so the canonical column names match across both
backfill and live updates.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from uuid import UUID

from app.observability.logging import get_logger
from app.services.data_plane.backfill_runner import (
    build_column_rename,
    find_ir_table_for_source,
)
from app.engines.schema.ir import SchemaIR, TableIR
from app.services.data_plane.canonical_upserter import CanonicalUpserter
from app.services.data_plane.id_resolver import IdResolver, MappingKey
from app.services.webhook_ingest.types import (
    IngestedEvent,
    IngestedEventOp,
    ProviderName,
)


__all__ = [
    "ReconcileResult",
    "ReconcileStatus",
    "RefetchHandler",
    "WebhookReconciler",
]


logger = get_logger("data_plane.webhook_reconciler")


# Provider → connector kind. The reconciler uses connector kind as the
# `source` field on EntityIdMap rows so cross-references match what the
# backfill runner writes.
_PROVIDER_TO_CONNECTOR_KIND: dict[ProviderName, str] = {
    ProviderName.SHOPIFY: "shopify",
    ProviderName.STRIPE: "stripe",
    ProviderName.GOOGLE_SHEETS: "google_sheets",
}


class ReconcileStatus:
    APPLIED = "applied"
    """Canonical row upserted (CREATE/UPDATE) or id_map cleared (DELETE)."""
    SKIPPED_NO_TABLE = "skipped_no_table"
    """No IR table sourced from (provider, source_table). Project hasn't
    modeled this entity — webhook accepted but ignored."""
    SKIPPED_NO_SOURCE_ID = "skipped_no_source_id"
    SKIPPED_NO_REFETCH_HANDLER = "skipped_no_refetch_handler"
    REFETCH_RAN = "refetch_ran"


@dataclass(frozen=True, slots=True)
class ReconcileResult:
    status: str
    canonical_id: UUID | None = None
    detail: str | None = None


# Refetch handler signature: caller resolves a connector + token + IR table
# and passes them to the runner. We don't import the BackfillRunner directly
# because the reconciler runs in an arq worker context where the runner is
# constructed fresh per job.
RefetchHandler = Callable[
    [IngestedEvent, UUID, UUID],  # event, organization_id, project_id
    Awaitable[ReconcileResult],
]


class WebhookReconciler:
    """One instance per arq job. Holds upserter + id_resolver bound to a
    tenant-scoped session.
    """

    def __init__(
        self,
        *,
        upserter: CanonicalUpserter,
        id_resolver: IdResolver,
        refetch_handler: RefetchHandler | None = None,
    ) -> None:
        self._upserter = upserter
        self._id_resolver = id_resolver
        self._refetch_handler = refetch_handler

    async def reconcile_event(
        self,
        *,
        event: IngestedEvent,
        organization_id: UUID,
        project_id: UUID,
        ir: SchemaIR,
    ) -> ReconcileResult:
        """Dispatch on `event.op`. Returns a typed result for telemetry."""
        connector_kind = _PROVIDER_TO_CONNECTOR_KIND.get(event.provider)
        if connector_kind is None:
            return ReconcileResult(
                status=ReconcileStatus.SKIPPED_NO_TABLE,
                detail=f"No connector mapping for provider {event.provider!r}.",
            )

        if event.op == IngestedEventOp.REFETCH:
            return await self._handle_refetch(
                event=event, organization_id=organization_id, project_id=project_id,
            )

        ir_table = find_ir_table_for_source(
            ir=ir, connector_name=connector_kind, source_table=event.source_table,
        )
        if ir_table is None:
            logger.info(
                "reconcile_skip_unmapped_table",
                project_id=str(project_id),
                provider=event.provider.value,
                source_table=event.source_table,
            )
            return ReconcileResult(
                status=ReconcileStatus.SKIPPED_NO_TABLE,
                detail=f"IR has no table sourced from ({connector_kind}, {event.source_table}).",
            )

        if event.source_id is None:
            return ReconcileResult(
                status=ReconcileStatus.SKIPPED_NO_SOURCE_ID,
                detail=f"{event.op.value} event missing source_id.",
            )

        if event.op in (IngestedEventOp.CREATE, IngestedEventOp.UPDATE):
            return await self._handle_upsert(
                event=event,
                organization_id=organization_id,
                project_id=project_id,
                connector_kind=connector_kind,
                ir_table=ir_table,
            )
        if event.op == IngestedEventOp.DELETE:
            return await self._handle_delete(
                event=event,
                project_id=project_id,
                connector_kind=connector_kind,
                ir_table_name=ir_table.name,
            )
        # Unknown op (defensive — IngestedEventOp is an enum).
        return ReconcileResult(
            status=ReconcileStatus.SKIPPED_NO_TABLE,
            detail=f"Unhandled op {event.op!r}.",
        )

    # ---------- per-op handlers ----------

    async def _handle_upsert(
        self,
        *,
        event: IngestedEvent,
        organization_id: UUID,
        project_id: UUID,
        connector_kind: str,
        ir_table: TableIR,
    ) -> ReconcileResult:
        rename = build_column_rename(ir_table, connector_kind)
        mapped_columns = {
            ir_col: event.raw.get(source_col)
            for source_col, ir_col in rename.items()
            if source_col != "id"  # `id` is set from canonical_id in the upserter
        }
        # `event.source_id` is verified non-None by the caller.
        assert event.source_id is not None
        result = await self._upserter.upsert(
            organization_id=organization_id,
            project_id=project_id,
            entity_kind=ir_table.name,
            source=connector_kind,
            source_id=event.source_id,
            columns=mapped_columns,
        )
        logger.info(
            "reconcile_upsert_applied",
            project_id=str(project_id),
            entity_kind=ir_table.name,
            source=connector_kind,
            source_id=event.source_id,
            canonical_id=str(result.canonical_id),
            was_created=result.was_created,
        )
        return ReconcileResult(
            status=ReconcileStatus.APPLIED,
            canonical_id=result.canonical_id,
        )

    async def _handle_delete(
        self,
        *,
        event: IngestedEvent,
        project_id: UUID,
        connector_kind: str,
        ir_table_name: str,
    ) -> ReconcileResult:
        # `event.source_id` is verified non-None by the caller.
        assert event.source_id is not None
        key = MappingKey(
            project_id=project_id,
            entity_kind=ir_table_name,
            source=connector_kind,
            source_id=event.source_id,
        )
        canonical_id = await self._id_resolver.find_canonical(key=key)
        if canonical_id is None:
            logger.info(
                "reconcile_delete_no_mapping",
                project_id=str(project_id),
                source=connector_kind,
                source_id=event.source_id,
            )
            return ReconcileResult(
                status=ReconcileStatus.APPLIED,
                detail="Delete event for unknown source_id; nothing to remove.",
            )

        deleted_canonical = await self._upserter.delete(
            entity_kind=ir_table_name,
            canonical_id=canonical_id,
        )
        deleted_mapping = await self._id_resolver.delete_mapping(key=key)

        logger.info(
            "reconcile_delete_applied",
            project_id=str(project_id),
            source=connector_kind,
            source_id=event.source_id,
            canonical_id=str(canonical_id),
            canonical_deleted=deleted_canonical,
            mapping_deleted=deleted_mapping,
        )
        return ReconcileResult(
            status=ReconcileStatus.APPLIED,
            canonical_id=canonical_id,
            detail="Canonical row and mapping deleted.",
        )

    async def _handle_refetch(
        self,
        *,
        event: IngestedEvent,
        organization_id: UUID,
        project_id: UUID,
    ) -> ReconcileResult:
        if self._refetch_handler is None:
            logger.info(
                "reconcile_refetch_no_handler",
                project_id=str(project_id),
                provider=event.provider.value,
            )
            return ReconcileResult(
                status=ReconcileStatus.SKIPPED_NO_REFETCH_HANDLER,
                detail="No refetch handler registered; data plane will fill in.",
            )
        return await self._refetch_handler(event, organization_id, project_id)
