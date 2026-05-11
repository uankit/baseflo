"""RefetchExecutor — handles `IngestedEventOp.REFETCH` events.

Per docs/01-architecture.md §4. Drive Push notifications (Sheets) carry no
payload — just "this resource changed." The executor:

  1. Resolves the IR table sourced from the affected (provider, source_table).
  2. Loads the active connector + decrypted token via `load_active_connectors`.
  3. Streams `connector.read(...)` for that source through `BackfillRunner.
     backfill_table` → `CanonicalUpserter` → existing canonical rows refresh
     in place.

For non-Sheets connectors that emit REFETCH (none today; contract
allows it), the same code path applies — strategy is provider-agnostic.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.engines.schema.ir import SchemaIR
from app.observability.logging import get_logger
from app.orchestration.connectors import LoadedConnector, load_active_connectors
from app.services.data_plane.backfill_runner import (
    BackfillRunner,
    find_ir_table_for_source,
)
from app.services.data_plane.canonical_upserter import CanonicalUpserter
from app.services.data_plane.webhook_reconciler import (
    ReconcileResult,
    ReconcileStatus,
)
from app.services.webhook_ingest.types import IngestedEvent, ProviderName


__all__ = ["RefetchExecutor"]


logger = get_logger("data_plane.refetch_executor")


_PROVIDER_TO_CONNECTOR_KIND: dict[ProviderName, str] = {
    ProviderName.SHOPIFY: "shopify",
    ProviderName.STRIPE: "stripe",
    ProviderName.GOOGLE_SHEETS: "google_sheets",
}


@dataclass(frozen=True, slots=True)
class _RefetchTarget:
    """Internal: the IR table + source_ref + live connector for one refetch."""

    connector_kind: str
    ir_table_name: str


class RefetchExecutor:
    """One instance per webhook delivery. Stateless apart from its session."""

    def __init__(
        self, *, session: AsyncSession, upserter: CanonicalUpserter,
    ) -> None:
        self._session = session
        self._upserter = upserter

    async def execute(
        self,
        *,
        event: IngestedEvent,
        organization_id: UUID,
        project_id: UUID,
        ir: SchemaIR,
    ) -> ReconcileResult:
        connector_kind = _PROVIDER_TO_CONNECTOR_KIND.get(event.provider)
        if connector_kind is None:
            return ReconcileResult(
                status=ReconcileStatus.SKIPPED_NO_TABLE,
                detail=f"No connector kind mapped for provider {event.provider!r}.",
            )

        ir_table = find_ir_table_for_source(
            ir=ir,
            connector_name=connector_kind,
            source_table=event.source_table,
        )
        if ir_table is None:
            return ReconcileResult(
                status=ReconcileStatus.SKIPPED_NO_TABLE,
                detail=(
                    f"IR has no table sourced from "
                    f"({connector_kind}, {event.source_table})."
                ),
            )

        source_ref = next(
            (s for s in ir_table.sources if s.connector_name == connector_kind),
            None,
        )
        if source_ref is None:
            return ReconcileResult(
                status=ReconcileStatus.SKIPPED_NO_TABLE,
                detail=(
                    f"IR table {ir_table.name!r} has no `{connector_kind}` "
                    "source ref."
                ),
            )

        loaded = await self._find_connector(
            project_id=project_id, connector_kind=connector_kind,
        )
        if loaded is None:
            return ReconcileResult(
                status=ReconcileStatus.SKIPPED_NO_TABLE,
                detail=(
                    f"No active {connector_kind} connector for project "
                    f"{project_id}; cannot refetch."
                ),
            )

        runner = BackfillRunner(upserter=self._upserter)
        result = await runner.backfill_table(
            organization_id=organization_id,
            project_id=project_id,
            connector=loaded.instance,
            token=loaded.token,
            ir_table=ir_table,
            source_ref=source_ref,
        )
        logger.info(
            "refetch_complete",
            project_id=str(project_id),
            entity_kind=ir_table.name,
            connector_kind=connector_kind,
            rows_seen=result.rows_seen,
            rows_upserted=result.rows_upserted,
            rows_skipped=result.rows_skipped,
        )
        return ReconcileResult(
            status=ReconcileStatus.REFETCH_RAN,
            detail=(
                f"refetched {ir_table.name}: "
                f"upserted={result.rows_upserted} skipped={result.rows_skipped}"
            ),
        )

    async def _find_connector(
        self, *, project_id: UUID, connector_kind: str,
    ) -> LoadedConnector | None:
        loaded_list = await load_active_connectors(
            self._session, project_id=project_id,
        )
        for loaded in loaded_list:
            if loaded.token.connector_name == connector_kind:
                return loaded
        return None
