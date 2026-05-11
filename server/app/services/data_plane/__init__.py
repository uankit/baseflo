"""Data-plane services — schema apply, cross-source reconciliation.

Per docs/01-architecture.md §4 and docs/40-features/AGENT-ENT.md §3.7.

  - `SchemaApplier`     runs compiled DDL into a per-tenant Postgres schema.

`CanonicalUpserter`, `EntityIdMap`/`IdResolver`, `BackfillRunner`, and
`WebhookReconciler` join this module as the data plane lights up.
"""

from __future__ import annotations

from app.services.data_plane.backfill_runner import (
    BackfillRunner,
    BackfillTableResult,
    ConnectorReader,
    build_column_rename,
    find_ir_table_for_source,
)
from app.services.data_plane.canonical_upserter import (
    CanonicalUpserter,
    UpsertResult,
)
from app.services.data_plane.id_resolver import (
    IdResolver,
    MappingKey,
    ResolvedMapping,
)
from app.services.data_plane.schema_applier import (
    ApplicationResult,
    SchemaApplier,
    split_ddl,
)
from app.services.data_plane.webhook_dispatcher import (
    ConnectorRoutingMatch,
    WebhookDispatcher,
)
from app.services.data_plane.webhook_reconciler import (
    ReconcileResult,
    ReconcileStatus,
    RefetchHandler,
    WebhookReconciler,
)

__all__ = [
    "ApplicationResult",
    "BackfillRunner",
    "BackfillTableResult",
    "CanonicalUpserter",
    "ConnectorReader",
    "IdResolver",
    "MappingKey",
    "ReconcileResult",
    "ReconcileStatus",
    "RefetchHandler",
    "ResolvedMapping",
    "SchemaApplier",
    "UpsertResult",
    "WebhookReconciler",
    "build_column_rename",
    "find_ir_table_for_source",
    "split_ddl",
]
