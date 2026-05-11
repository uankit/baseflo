"""CanonicalUpserter — write a row into the per-tenant canonical store.

Per docs/01-architecture.md §4. The upserter is the layer that turns a row
read from a connector (or a refetched resource on a webhook) into a row in
the tenant's canonical Postgres table.

Pipeline:
  1. Caller passes `(entity_kind, source, source_id, columns)`.
  2. `IdResolver.resolve_or_create` returns a stable `canonical_id` for that
     `(source, source_id)`.
  3. The upserter emits an `INSERT … ON CONFLICT (id) DO UPDATE` against
     `<tenant_schema>.<entity_kind>`. The `id` column carries `canonical_id`.

Why ON CONFLICT (id) and not (source_id):
  - The mapping table `entity_id_map` is the place where `(source, source_id)
    → canonical_id` is enforced unique. The canonical table needs only the
    canonical id as its PK; this is what enables cross-source unification
    (multiple `entity_id_map` rows can point at the same canonical row).
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from sqlalchemy import text

from app.connectors.base import Row
from app.core.errors import BasefloError
from app.engines.schema.ddl.identifiers import is_safe_identifier, quote_identifier
from app.observability.logging import get_logger
from app.services.data_plane.id_resolver import IdResolver, MappingKey

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession

    from app.services.data_plane.id_resolver import IdentityKey

__all__ = ["CanonicalUpserter", "UpsertResult"]


logger = get_logger("data_plane.canonical_upserter")


@dataclass(frozen=True, slots=True)
class UpsertResult:
    canonical_id: UUID
    was_created: bool
    """True when the canonical_id was minted in this call (first sighting)."""


class CanonicalUpserter:
    """Tenant-aware upsert into the canonical Postgres schema.

    One instance per request / job. The session it holds must be bound to
    the same engine that owns the tenant schema (Hosted Cloud: control-plane
    DB; BYO-DB: customer's engine — v1 supports hosted cloud only).
    """

    def __init__(
        self,
        *,
        tenant_session: AsyncSession,
        schema_name: str,
        id_resolver: IdResolver,
    ) -> None:
        if not is_safe_identifier(schema_name):
            raise BasefloError(
                error_code="BF-DATAPLANE-002",
                message=f"Unsafe schema name: {schema_name!r}.",
                status_code=500,
            )
        self._session = tenant_session
        self._schema_name = schema_name
        self._id_resolver = id_resolver

    async def upsert(
        self,
        *,
        organization_id: UUID,
        project_id: UUID,
        entity_kind: str,
        source: str,
        source_id: str,
        columns: dict[str, Any],
        identity: IdentityKey | None = None,
    ) -> UpsertResult:
        """Upsert one row. Caller's `columns` excludes `id` (we set it).

        The connector adapter is expected to have already mapped its raw row
        shape to IR-aligned column names (snake_case identifiers). The
        upserter validates each column name via `is_safe_identifier` to
        defeat SQL injection through column names.
        """
        if not is_safe_identifier(entity_kind):
            raise BasefloError(
                error_code="BF-DATAPLANE-004",
                message=f"Unsafe entity_kind: {entity_kind!r}.",
                status_code=400,
            )
        for column_name in columns:
            if column_name == "id":
                raise BasefloError(
                    error_code="BF-DATAPLANE-005",
                    message=(
                        "Caller must not include 'id' in columns; the upserter "
                        "sets it from the resolved canonical_id."
                    ),
                    status_code=400,
                )
            if not is_safe_identifier(column_name):
                raise BasefloError(
                    error_code="BF-DATAPLANE-004",
                    message=f"Unsafe column name: {column_name!r}.",
                    status_code=400,
                )

        key = MappingKey(
            project_id=project_id,
            entity_kind=entity_kind,
            source=source,
            source_id=source_id,
        )
        if identity is None:
            mapping = await self._id_resolver.resolve_or_create(
                organization_id=organization_id,
                key=key,
            )
        else:
            mapping = await self._id_resolver.resolve_or_create_with_identity(
                organization_id=organization_id,
                key=key,
                identity=identity,
            )

        all_values = {"id": mapping.canonical_id, **columns}
        column_idents = [quote_identifier(name) for name in all_values]
        # Use named params with `_p` prefix to avoid colliding with column
        # names that contain `id`.
        bind_names = [f"p_{i}" for i in range(len(all_values))]
        bind_map = dict(zip(bind_names, all_values.values(), strict=True))
        column_keys = list(all_values.keys())
        non_id_keys = [k for k in column_keys if k != "id"]

        sql = (
            f"INSERT INTO {quote_identifier(self._schema_name)}."  # noqa: S608
            f"{quote_identifier(entity_kind)} "
            f"({', '.join(column_idents)}) "
            f"VALUES ({', '.join(':' + n for n in bind_names)}) "
        )
        if non_id_keys:
            update_clause = ", ".join(
                f"{quote_identifier(k)} = EXCLUDED.{quote_identifier(k)}"
                for k in non_id_keys
            )
            sql += f"ON CONFLICT (id) DO UPDATE SET {update_clause} "
        else:
            sql += "ON CONFLICT (id) DO NOTHING "
        sql += "RETURNING id;"

        result = await self._session.execute(text(sql), bind_map)
        returned = result.scalar_one_or_none()
        # On `DO NOTHING` with conflict and no other update, RETURNING is empty.
        # Fall back to the resolved canonical_id (the existing row's id).
        canonical_id = returned if returned is not None else mapping.canonical_id

        logger.info(
            "canonical_upserted",
            project_id=str(project_id),
            entity_kind=entity_kind,
            source=source,
            source_id=source_id,
            canonical_id=str(canonical_id),
            was_created=mapping.was_created,
        )
        return UpsertResult(
            canonical_id=canonical_id,
            was_created=mapping.was_created,
        )

    async def upsert_many(
        self,
        *,
        organization_id: UUID,
        project_id: UUID,
        entity_kind: str,
        source: str,
        rows: list[Row],
        identities: list[IdentityKey | None] | None = None,
    ) -> list[UpsertResult]:
        """Batch upsert rows using a single ``INSERT … ON CONFLICT … RETURNING``.

        Rows are grouped by the set of columns they carry so that each
        generated INSERT statement has a uniform column list.  The id
        resolution step is also batched via
        :meth:`IdResolver.resolve_or_create_many`.
        """
        if not is_safe_identifier(entity_kind):
            raise BasefloError(
                error_code="BF-DATAPLANE-004",
                message=f"Unsafe entity_kind: {entity_kind!r}.",
                status_code=400,
            )
        if not rows:
            return []
        if identities is not None and len(identities) != len(rows):
            raise BasefloError(
                error_code="BF-DATAPLANE-007",
                message="Length of identities must match length of rows.",
                status_code=400,
            )

        keys: list[MappingKey] = []
        for row in rows:
            if row.source_id is None:
                raise BasefloError(
                    error_code="BF-DATAPLANE-005",
                    message="Row source_id must not be None for batch upsert.",
                    status_code=400,
                )
            for column_name in row.values:
                if column_name == "id":
                    raise BasefloError(
                        error_code="BF-DATAPLANE-005",
                        message=(
                            "Caller must not include 'id' in columns; the upserter "
                            "sets it from the resolved canonical_id."
                        ),
                        status_code=400,
                    )
                if not is_safe_identifier(column_name):
                    raise BasefloError(
                        error_code="BF-DATAPLANE-004",
                        message=f"Unsafe column name: {column_name!r}.",
                        status_code=400,
                    )
            keys.append(
                MappingKey(
                    project_id=project_id,
                    entity_kind=entity_kind,
                    source=source,
                    source_id=row.source_id,
                )
            )

        resolved = await self._id_resolver.resolve_or_create_many(
            organization_id=organization_id,
            keys=keys,
            identities=identities,
        )

        results: list[UpsertResult | None] = [None] * len(rows)

        grouped: dict[
            tuple[str, ...], list[tuple[int, dict[str, Any], UUID, bool]]
        ] = defaultdict(list)
        for idx, row in enumerate(rows):
            cid = resolved[idx].canonical_id
            was_created = resolved[idx].was_created
            cols = tuple(sorted(row.values.keys()))
            grouped[cols].append((idx, row.values, cid, was_created))

        for cols, items in grouped.items():
            all_cols = ["id", *cols]
            column_idents = [quote_identifier(c) for c in all_cols]

            value_clauses: list[str] = []
            bind_map: dict[str, Any] = {}
            for item_idx, (_, values, cid, _) in enumerate(items):
                row_bind_names: list[str] = []
                bind_name = f"p_{item_idx}_id"
                row_bind_names.append(bind_name)
                bind_map[bind_name] = cid
                for col in cols:
                    bind_name = f"p_{item_idx}_{col}"
                    row_bind_names.append(bind_name)
                    bind_map[bind_name] = values[col]
                value_clauses.append(
                    f"({', '.join(':' + n for n in row_bind_names)})"
                )

            sql = (
                f"INSERT INTO {quote_identifier(self._schema_name)}."
                f"{quote_identifier(entity_kind)} "
                f"({', '.join(column_idents)}) "
                f"VALUES {', '.join(value_clauses)} "
            )
            if cols:
                update_clause = ", ".join(
                    f"{quote_identifier(col)} = EXCLUDED.{quote_identifier(col)}"
                    for col in cols
                )
                sql += f"ON CONFLICT (id) DO UPDATE SET {update_clause} "
            else:
                sql += "ON CONFLICT (id) DO NOTHING "
            sql += "RETURNING id;"

            exec_result = await self._session.execute(text(sql), bind_map)
            # Consume the result so the driver is happy; canonical ids are
            # already known from the resolver.
            exec_result.scalars().all()

            for row_idx, _, cid, was_created in items:
                results[row_idx] = UpsertResult(
                    canonical_id=cid,
                    was_created=was_created,
                )

        logger.info(
            "canonical_upserted_many",
            project_id=str(project_id),
            entity_kind=entity_kind,
            source=source,
            batch_size=len(rows),
            groups=len(grouped),
        )
        return [r for r in results if r is not None]

    async def delete(
        self,
        *,
        entity_kind: str,
        canonical_id: UUID,
    ) -> bool:
        """Hard-delete a canonical row by its id.

        Returns ``True`` when a row was actually removed.
        """
        if not is_safe_identifier(entity_kind):
            raise BasefloError(
                error_code="BF-DATAPLANE-004",
                message=f"Unsafe entity_kind: {entity_kind!r}.",
                status_code=400,
            )
        sql = (
            f"DELETE FROM {quote_identifier(self._schema_name)}."
            f"{quote_identifier(entity_kind)} WHERE id = :cid"
        )
        result = await self._session.execute(text(sql), {"cid": canonical_id})
        rowcount = int(getattr(result, "rowcount", 0) or 0)
        logger.info(
            "canonical_deleted",
            schema_name=self._schema_name,
            entity_kind=entity_kind,
            canonical_id=str(canonical_id),
            rowcount=rowcount,
        )
        return rowcount > 0
