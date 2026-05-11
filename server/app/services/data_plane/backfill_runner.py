"""BackfillRunner — streams `connector.read()` into the canonical store.

Per docs/01-architecture.md §4. Called once after a project version's
SchemaApplier run succeeds, to populate the per-tenant tables with the
initial set of rows from each connector.

Single-source-per-table backfill. Each `TableIR.sources` entry that names
a connector kind triggers one backfill stream for that (table, connector)
pair. Multi-source unification — where two source rows merge into one
canonical row — is handled by the ReconciliationAgent before backfill.

Idempotency: the upsert path is `ON CONFLICT (id) DO UPDATE`, so re-running
a backfill is safe — it just refreshes column values.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from app.connectors.base import Row, SourceQuery
from app.observability.logging import get_logger
from app.services.data_plane.id_resolver import IdentityKey, identity_hash

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from uuid import UUID

    from app.connectors.base import ConnectorToken
    from app.engines.schema.ir import SchemaIR, SourceRef, TableIR
    from app.services.data_plane.canonical_upserter import CanonicalUpserter

__all__ = [
    "BackfillRunner",
    "BackfillTableResult",
    "ConnectorReader",
    "build_column_rename",
    "build_identity_key",
    "find_ir_table_for_source",
]


logger = get_logger("data_plane.backfill_runner")


class ConnectorReader(Protocol):
    """Slice of `Connector` the runner needs. Lets tests pass a fake."""

    async def read(
        self, token: ConnectorToken, query: SourceQuery,
    ) -> AsyncIterator[Row]: ...


@dataclass(frozen=True, slots=True)
class BackfillTableResult:
    entity_kind: str
    source: str
    rows_seen: int
    rows_upserted: int
    rows_skipped: int
    """Rows skipped because they had no `source_id` to key the upsert on."""


class BackfillRunner:
    """Per-(table, connector) backfill of rows into the canonical store."""

    BATCH_SIZE = 500

    def __init__(self, *, upserter: CanonicalUpserter) -> None:
        self._upserter = upserter

    async def backfill_table(
        self,
        *,
        organization_id: UUID,
        project_id: UUID,
        connector: ConnectorReader,
        token: ConnectorToken,
        ir_table: TableIR,
        source_ref: SourceRef,
    ) -> BackfillTableResult:
        """Stream rows from one source-table and upsert them in batches."""
        column_rename = build_column_rename(ir_table, source_ref.connector_name)

        iterator = await connector.read(
            token, SourceQuery(table=source_ref.source_table),
        )
        seen = 0
        upserted = 0
        skipped = 0
        batch: list[Row] = []
        identity_batch: list[IdentityKey | None] = []

        async for row in iterator:
            seen += 1
            if row.source_id is None:
                logger.warning(
                    "backfill_skip_no_source_id",
                    project_id=str(project_id),
                    entity_kind=ir_table.name,
                    source=source_ref.connector_name,
                    source_table=source_ref.source_table,
                )
                skipped += 1
                continue
            mapped = self._map_columns(row.values, column_rename)
            identity = build_identity_key(
                project_id=project_id,
                ir_table=ir_table,
                source_ref=source_ref,
                values=row.values,
            )
            batch.append(Row(values=mapped, source_id=row.source_id))
            identity_batch.append(identity)

            if len(batch) >= self.BATCH_SIZE:
                results = await self._upserter.upsert_many(
                    organization_id=organization_id,
                    project_id=project_id,
                    entity_kind=ir_table.name,
                    source=source_ref.connector_name,
                    rows=batch,
                    identities=identity_batch,
                )
                upserted += len(results)
                batch.clear()
                identity_batch.clear()

        if batch:
            results = await self._upserter.upsert_many(
                organization_id=organization_id,
                project_id=project_id,
                entity_kind=ir_table.name,
                source=source_ref.connector_name,
                rows=batch,
                identities=identity_batch,
            )
            upserted += len(results)

        return BackfillTableResult(
            entity_kind=ir_table.name,
            source=source_ref.connector_name,
            rows_seen=seen,
            rows_upserted=upserted,
            rows_skipped=skipped,
        )

    async def backfill_ir(
        self,
        *,
        organization_id: UUID,
        project_id: UUID,
        ir: SchemaIR,
        connectors: dict[str, tuple[ConnectorReader, ConnectorToken]],
    ) -> list[BackfillTableResult]:
        """Walk the IR, calling `backfill_table` for every (table, source) pair
        whose connector_name is in `connectors`.

        `connectors` is keyed by connector kind — caller resolves Connector
        rows + tokens upstream and passes the live instances here.
        """
        results: list[BackfillTableResult] = []
        for ir_table in ir.tables:
            for source_ref in ir_table.sources:
                pair = connectors.get(source_ref.connector_name)
                if pair is None:
                    logger.info(
                        "backfill_skip_unknown_connector",
                        project_id=str(project_id),
                        entity_kind=ir_table.name,
                        connector=source_ref.connector_name,
                    )
                    continue
                connector, token = pair
                result = await self.backfill_table(
                    organization_id=organization_id,
                    project_id=project_id,
                    connector=connector,
                    token=token,
                    ir_table=ir_table,
                    source_ref=source_ref,
                )
                results.append(result)
        return results

    @staticmethod
    def _map_columns(
        values: dict[str, object], rename: dict[str, str],
    ) -> dict[str, object]:
        """Project + rename the source row to IR column names."""
        return {
            ir_col: values.get(source_col)
            for source_col, ir_col in rename.items()
        }


def build_column_rename(
    ir_table: TableIR, connector_name: str,
) -> dict[str, str]:
    """{source_column_name → ir_column_name} for columns from `connector_name`.

    The canonical `id` column is always skipped because `CanonicalUpserter`
    writes it from the identity map. Columns whose `sources` entry has
    `source_column=None` (or no entry from this connector) are skipped —
    they're either derived/computed or sourced elsewhere. Shared between the
    backfill runner and webhook reconciler so column-rename rules stay
    identical across paths.
    """
    rename: dict[str, str] = {}
    for col in ir_table.columns:
        if col.name == "id":
            continue
        for src in col.sources:
            if (
                src.connector_name == connector_name
                and src.source_column is not None
            ):
                rename[src.source_column] = col.name
                break
    return rename


def build_identity_key(
    *,
    project_id: UUID,
    ir_table: TableIR,
    source_ref: SourceRef,
    values: dict[str, object],
) -> IdentityKey | None:
    """Build a row-level identity key from the table reconciliation policy.

    Join keys are source-column based. For a row from either side of a
    `JoinKey`, normalize the configured columns and hash the normalized tuple.
    Rows from different sources with the same normalized tuple converge to the
    same canonical id through `EntityIdentityIndex`.
    """
    policy = ir_table.reconciliation_policy
    if policy is None:
        return None

    for idx, join_key in enumerate(policy.join_keys):
        columns: list[str] | None = None
        if (
            join_key.source_a.connector_name == source_ref.connector_name
            and join_key.source_a.source_table == source_ref.source_table
        ):
            columns = join_key.columns_a
        elif (
            join_key.source_b.connector_name == source_ref.connector_name
            and join_key.source_b.source_table == source_ref.source_table
        ):
            columns = join_key.columns_b
        if columns is None:
            continue

        raw_values = [values.get(column) for column in columns]
        if any(value in (None, "") for value in raw_values):
            continue
        normalized = [
            _normalize_identity_value(value, join_key.transformation)
            for value in raw_values
        ]
        if any(value == "" for value in normalized):
            continue
        identity_key = (
            f"{ir_table.name}:join_key_{idx}:{join_key.transformation.value}"
        )
        return IdentityKey(
            project_id=project_id,
            entity_kind=ir_table.name,
            identity_key=identity_key,
            identity_hash=identity_hash(normalized),
            evidence={
                "connector": source_ref.connector_name,
                "source_table": source_ref.source_table,
                "columns": columns,
                "raw_values": [str(value) for value in raw_values],
                "normalized_values": normalized,
                "transformation": join_key.transformation.value,
            },
        )
    return None


def _normalize_identity_value(value: object, transformation: object) -> str:
    text = str(value).strip()
    transform = getattr(transformation, "value", str(transformation))
    if transform == "lowercase_trim":
        return text.lower()
    if transform == "digits_only":
        return "".join(ch for ch in text if ch.isdigit())
    return text


def find_ir_table_for_source(
    *, ir: SchemaIR, connector_name: str, source_table: str,
) -> TableIR | None:
    """Return the IR table sourced from `(connector_name, source_table)`.

    None when the IR doesn't carry a table sourced from this pair (which is
    fine for events the project hasn't modeled yet — the reconciler skips).
    """
    for table in ir.tables:
        for src in table.sources:
            if (
                src.connector_name == connector_name
                and src.source_table == source_table
            ):
                return table
    return None
