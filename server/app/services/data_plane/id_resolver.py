"""IdResolver — (source, source_id) → canonical_id mapping service.

Per docs/01-architecture.md §4. Used by:

  - `CanonicalUpserter` on every row write — resolve the canonical id, then
    upsert into the per-tenant table keyed on it.
  - `WebhookReconciler` when a webhook fires for `gid://shopify/Customer/1`,
    look up which canonical row to refresh.
  - The reconciler agent (post-alpha) when it asserts cross-source identity:
    it merges multiple `(source, source_id)` rows under one canonical id.

`resolve_or_create` uses Postgres `INSERT … ON CONFLICT … DO UPDATE` so it's
race-safe under concurrent inserts.
"""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core.errors import BasefloError
from app.core.ids import new_uuid7
from app.db.models.entity_id_map import EntityIdMap
from app.db.models.entity_identity_index import EntityIdentityIndex
from app.observability.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Iterable
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession

__all__ = [
    "IdResolver",
    "IdentityKey",
    "MappingKey",
    "ResolvedMapping",
    "identity_hash",
]


logger = get_logger("data_plane.id_resolver")


@dataclass(frozen=True, slots=True)
class MappingKey:
    """Composite key: a row from `source` with id `source_id` for `entity_kind`."""

    project_id: UUID
    entity_kind: str
    source: str
    source_id: str


@dataclass(frozen=True, slots=True)
class IdentityKey:
    """Normalized business identity for cross-source row convergence."""

    project_id: UUID
    entity_kind: str
    identity_key: str
    identity_hash: str
    evidence: dict[str, Any]


@dataclass(frozen=True, slots=True)
class ResolvedMapping:
    canonical_id: UUID
    was_created: bool
    """True when a fresh canonical_id was minted for this key."""


class IdResolver:
    """One instance per request. Stateless apart from its session."""

    def __init__(self, *, session: AsyncSession) -> None:
        self._session = session

    async def resolve_or_create(
        self, *, organization_id: UUID, key: MappingKey,
    ) -> ResolvedMapping:
        """Return canonical_id for `key`. Creates a new canonical_id atomically
        when none exists; concurrent calls converge on a single mapping.
        """
        return await self.resolve_or_create_with_identity(
            organization_id=organization_id,
            key=key,
            identity=None,
        )

    async def resolve_or_create_with_identity(
        self,
        *,
        organization_id: UUID,
        key: MappingKey,
        identity: IdentityKey | None,
    ) -> ResolvedMapping:
        """Resolve a source row, optionally converging via business identity.

        When `identity` is supplied, rows from different sources that normalize
        to the same identity hash share one canonical id. The source mapping is
        then written to that canonical id, and any prior source-specific
        canonical id is merged into it.
        """
        if identity is None:
            return await self._resolve_source_mapping(
                organization_id=organization_id,
                key=key,
                candidate_canonical_id=new_uuid7(),
            )

        canonical_id = await self._resolve_identity(
            organization_id=organization_id,
            identity=identity,
        )
        mapping = await self._resolve_source_mapping(
            organization_id=organization_id,
            key=key,
            candidate_canonical_id=canonical_id,
        )
        if mapping.canonical_id != canonical_id:
            await self.merge_canonicals(
                project_id=key.project_id,
                entity_kind=key.entity_kind,
                keep_canonical_id=canonical_id,
                merge_canonical_ids=[mapping.canonical_id],
            )
            return ResolvedMapping(
                canonical_id=canonical_id,
                was_created=mapping.was_created,
            )
        return mapping

    async def _resolve_source_mapping(
        self,
        *,
        organization_id: UUID,
        key: MappingKey,
        candidate_canonical_id: UUID,
    ) -> ResolvedMapping:
        stmt = (
            pg_insert(EntityIdMap)
            .values(
                organization_id=organization_id,
                project_id=key.project_id,
                entity_kind=key.entity_kind,
                source=key.source,
                source_id=key.source_id,
                canonical_id=candidate_canonical_id,
            )
            .on_conflict_do_nothing(
                index_elements=[
                    "project_id", "entity_kind", "source", "source_id",
                ],
            )
            .returning(EntityIdMap.canonical_id)
        )
        result = await self._session.execute(stmt)
        inserted_id = result.scalar_one_or_none()
        if inserted_id is not None:
            await self._session.flush()
            return ResolvedMapping(canonical_id=inserted_id, was_created=True)

        # Conflict — another writer got there first OR this is a re-call.
        # Read the existing mapping.
        existing = await self._session.execute(
            select(EntityIdMap.canonical_id).where(
                EntityIdMap.project_id == key.project_id,
                EntityIdMap.entity_kind == key.entity_kind,
                EntityIdMap.source == key.source,
                EntityIdMap.source_id == key.source_id,
            )
        )
        canonical_id = existing.scalar_one()
        return ResolvedMapping(canonical_id=canonical_id, was_created=False)

    async def _resolve_identity(
        self,
        *,
        organization_id: UUID,
        identity: IdentityKey,
    ) -> UUID:
        candidate_canonical_id = new_uuid7()
        stmt = (
            pg_insert(EntityIdentityIndex)
            .values(
                organization_id=organization_id,
                project_id=identity.project_id,
                entity_kind=identity.entity_kind,
                identity_key=identity.identity_key,
                identity_hash=identity.identity_hash,
                canonical_id=candidate_canonical_id,
                evidence=identity.evidence,
            )
            .on_conflict_do_nothing(
                index_elements=[
                    "project_id",
                    "entity_kind",
                    "identity_key",
                    "identity_hash",
                ],
            )
            .returning(EntityIdentityIndex.canonical_id)
        )
        result = await self._session.execute(stmt)
        inserted_id = result.scalar_one_or_none()
        if inserted_id is not None:
            await self._session.flush()
            return inserted_id

        existing = await self._session.execute(
            select(EntityIdentityIndex.canonical_id).where(
                EntityIdentityIndex.project_id == identity.project_id,
                EntityIdentityIndex.entity_kind == identity.entity_kind,
                EntityIdentityIndex.identity_key == identity.identity_key,
                EntityIdentityIndex.identity_hash == identity.identity_hash,
            )
        )
        return existing.scalar_one()

    async def resolve_many(
        self,
        *,
        keys: list[MappingKey],
    ) -> list[UUID | None]:
        """Batch-resolve canonical ids for a list of mapping keys.

        Returns a list aligned with ``keys``; ``None`` means no mapping exists.
        """
        if not keys:
            return []
        groups: dict[tuple[UUID, str, str], list[tuple[int, str]]] = defaultdict(list)
        for idx, key in enumerate(keys):
            groups[(key.project_id, key.entity_kind, key.source)].append(
                (idx, key.source_id)
            )
        results: list[UUID | None] = [None] * len(keys)
        for (project_id, entity_kind, source), items in groups.items():
            source_ids = [source_id for _, source_id in items]
            stmt = select(EntityIdMap.canonical_id, EntityIdMap.source_id).where(
                EntityIdMap.project_id == project_id,
                EntityIdMap.entity_kind == entity_kind,
                EntityIdMap.source == source,
                EntityIdMap.source_id.in_(source_ids),
            )
            rows = (await self._session.execute(stmt)).all()
            lookup = {source_id: cid for cid, source_id in rows}
            for idx, source_id in items:
                results[idx] = lookup.get(source_id)
        return results

    async def resolve_or_create_many(
        self,
        *,
        organization_id: UUID,
        keys: list[MappingKey],
        identities: list[IdentityKey | None] | None = None,
    ) -> list[ResolvedMapping]:
        """Batch-resolve or create mappings for a list of keys.

        Performs bulk ``INSERT … ON CONFLICT … RETURNING`` against
        ``entity_id_map`` (and ``entity_identity_index`` when identity is
        present). Order of the returned list matches ``keys``.
        """
        if not keys:
            return []
        if identities is not None and len(identities) != len(keys):
            raise BasefloError(
                error_code="BF-DATAPLANE-007",
                message="Length of identities must match length of keys.",
                status_code=400,
            )

        no_identity: list[tuple[int, MappingKey]] = []
        with_identity: list[tuple[int, MappingKey, IdentityKey]] = []
        for idx, key in enumerate(keys):
            ident = identities[idx] if identities is not None else None
            if ident is None:
                no_identity.append((idx, key))
            else:
                with_identity.append((idx, key, ident))

        results: list[ResolvedMapping | None] = [None] * len(keys)

        # ---- Fast path: no identity ----
        if no_identity:
            groups: dict[
                tuple[UUID, str, str], list[tuple[int, MappingKey]]
            ] = defaultdict(list)
            for idx, key in no_identity:
                groups[(key.project_id, key.entity_kind, key.source)].append(
                    (idx, key)
                )
            for (project_id, entity_kind, source), items in groups.items():
                values = [
                    {
                        "organization_id": organization_id,
                        "project_id": key.project_id,
                        "entity_kind": key.entity_kind,
                        "source": key.source,
                        "source_id": key.source_id,
                        "canonical_id": new_uuid7(),
                    }
                    for _, key in items
                ]
                stmt = (
                    pg_insert(EntityIdMap)
                    .values(values)
                    .on_conflict_do_nothing(
                        index_elements=[
                            "project_id",
                            "entity_kind",
                            "source",
                            "source_id",
                        ],
                    )
                    .returning(
                        EntityIdMap.canonical_id, EntityIdMap.source_id
                    )
                )
                res = await self._session.execute(stmt)
                inserted = {source_id: cid for cid, source_id in res.all()}
                missing = [
                    key.source_id
                    for _, key in items
                    if key.source_id not in inserted
                ]
                if missing:
                    existing_stmt = select(
                        EntityIdMap.canonical_id, EntityIdMap.source_id
                    ).where(
                        EntityIdMap.project_id == project_id,
                        EntityIdMap.entity_kind == entity_kind,
                        EntityIdMap.source == source,
                        EntityIdMap.source_id.in_(missing),
                    )
                    existing_res = await self._session.execute(existing_stmt)
                    existing = {
                        source_id: cid for cid, source_id in existing_res.all()
                    }
                else:
                    existing = {}
                for idx, key in items:
                    cid = inserted.get(key.source_id)
                    if cid is None:
                        cid = existing.get(key.source_id)
                    if cid is None:
                        raise BasefloError(
                            error_code="BF-DATAPLANE-006",
                            message=(
                                f"Failed to resolve mapping for source_id "
                                f"{key.source_id!r}."
                            ),
                            status_code=500,
                        )
                    results[idx] = ResolvedMapping(
                        canonical_id=cid,
                        was_created=key.source_id in inserted,
                    )

        # ---- Identity path: batch identity, then batch mapping, then merge ----
        if with_identity:
            ident_groups: dict[
                tuple[UUID, str], list[tuple[int, MappingKey, IdentityKey]]
            ] = defaultdict(list)
            for idx, key, ident in with_identity:
                ident_groups[(ident.project_id, ident.entity_kind)].append(
                    (idx, key, ident)
                )
            for (project_id, entity_kind), group_items in ident_groups.items():
                # 1) Batch insert into EntityIdentityIndex
                identity_values = [
                    {
                        "organization_id": organization_id,
                        "project_id": ident.project_id,
                        "entity_kind": ident.entity_kind,
                        "identity_key": ident.identity_key,
                        "identity_hash": ident.identity_hash,
                        "canonical_id": new_uuid7(),
                        "evidence": ident.evidence,
                    }
                    for _, _, ident in group_items
                ]
                stmt = (
                    pg_insert(EntityIdentityIndex)
                    .values(identity_values)
                    .on_conflict_do_nothing(
                        index_elements=[
                            "project_id",
                            "entity_kind",
                            "identity_key",
                            "identity_hash",
                        ],
                    )
                    .returning(
                        EntityIdentityIndex.canonical_id,
                        EntityIdentityIndex.identity_hash,
                    )
                )
                res = await self._session.execute(stmt)
                inserted_identity = {
                    ihash: cid for cid, ihash in res.all()
                }
                missing_hashes = [
                    ident.identity_hash
                    for _, _, ident in group_items
                    if ident.identity_hash not in inserted_identity
                ]
                if missing_hashes:
                    existing_stmt = select(
                        EntityIdentityIndex.canonical_id,
                        EntityIdentityIndex.identity_hash,
                    ).where(
                        EntityIdentityIndex.project_id == project_id,
                        EntityIdentityIndex.entity_kind == entity_kind,
                        EntityIdentityIndex.identity_hash.in_(missing_hashes),
                    )
                    existing_res = await self._session.execute(existing_stmt)
                    existing_identity = {
                        ihash: cid for cid, ihash in existing_res.all()
                    }
                else:
                    existing_identity = {}
                identity_cids: dict[int, UUID] = {}
                for idx, _, ident in group_items:
                    cid = inserted_identity.get(ident.identity_hash)
                    if cid is None:
                        cid = existing_identity.get(ident.identity_hash)
                    if cid is None:
                        raise BasefloError(
                            error_code="BF-DATAPLANE-006",
                            message=(
                                f"Failed to resolve identity for hash "
                                f"{ident.identity_hash!r}."
                            ),
                            status_code=500,
                        )
                    identity_cids[idx] = cid

                # 2) Batch insert into EntityIdMap
                source_groups: dict[
                    str, list[tuple[int, MappingKey, UUID]]
                ] = defaultdict(list)
                for idx, key, _ in group_items:
                    source_groups[key.source].append(
                        (idx, key, identity_cids[idx])
                    )
                for source, src_items in source_groups.items():
                    values = [
                        {
                            "organization_id": organization_id,
                            "project_id": key.project_id,
                            "entity_kind": key.entity_kind,
                            "source": key.source,
                            "source_id": key.source_id,
                            "canonical_id": candidate_cid,
                        }
                        for _, key, candidate_cid in src_items
                    ]
                    stmt = (
                        pg_insert(EntityIdMap)
                        .values(values)
                        .on_conflict_do_nothing(
                            index_elements=[
                                "project_id",
                                "entity_kind",
                                "source",
                                "source_id",
                            ],
                        )
                        .returning(
                            EntityIdMap.canonical_id, EntityIdMap.source_id
                        )
                    )
                    res = await self._session.execute(stmt)
                    inserted_map = {
                        source_id: cid for cid, source_id in res.all()
                    }
                    missing_source_ids = [
                        key.source_id
                        for _, key, _ in src_items
                        if key.source_id not in inserted_map
                    ]
                    if missing_source_ids:
                        existing_stmt = select(
                            EntityIdMap.canonical_id, EntityIdMap.source_id
                        ).where(
                            EntityIdMap.project_id == project_id,
                            EntityIdMap.entity_kind == entity_kind,
                            EntityIdMap.source == source,
                            EntityIdMap.source_id.in_(missing_source_ids),
                        )
                        existing_res = await self._session.execute(existing_stmt)
                        existing_map = {
                            source_id: cid
                            for cid, source_id in existing_res.all()
                        }
                    else:
                        existing_map = {}

                    # 3) Handle mismatches (merge) and build results
                    merge_plan: dict[UUID, list[UUID]] = defaultdict(list)
                    for idx, key, candidate_cid in src_items:
                        cid = inserted_map.get(key.source_id)
                        if cid is None:
                            cid = existing_map.get(key.source_id)
                        if cid is None:
                            raise BasefloError(
                                error_code="BF-DATAPLANE-006",
                                message=(
                                    f"Failed to resolve mapping for source_id "
                                    f"{key.source_id!r}."
                                ),
                                status_code=500,
                            )
                        was_created = key.source_id in inserted_map
                        if cid != candidate_cid:
                            merge_plan[candidate_cid].append(cid)
                            cid = candidate_cid
                        results[idx] = ResolvedMapping(
                            canonical_id=cid,
                            was_created=was_created,
                        )
                    for keep_cid, merge_cids in merge_plan.items():
                        await self.merge_canonicals(
                            project_id=project_id,
                            entity_kind=entity_kind,
                            keep_canonical_id=keep_cid,
                            merge_canonical_ids=merge_cids,
                        )

        return [r for r in results if r is not None]

    async def find_canonical(
        self, *, key: MappingKey,
    ) -> UUID | None:
        result = await self._session.execute(
            select(EntityIdMap.canonical_id).where(
                EntityIdMap.project_id == key.project_id,
                EntityIdMap.entity_kind == key.entity_kind,
                EntityIdMap.source == key.source,
                EntityIdMap.source_id == key.source_id,
            )
        )
        return result.scalar_one_or_none()

    async def find_sources(
        self, *, project_id: UUID, entity_kind: str, canonical_id: UUID,
    ) -> dict[str, list[str]]:
        """Reverse lookup: which source_ids contributed to this canonical row?

        Result shape: ``{"shopify": ["gid://...//1"], "excel": ["row_42"]}``.
        Useful for the unification UI and for the post-alpha reconciler
        when merging records.
        """
        stmt = select(EntityIdMap.source, EntityIdMap.source_id).where(
            EntityIdMap.project_id == project_id,
            EntityIdMap.entity_kind == entity_kind,
            EntityIdMap.canonical_id == canonical_id,
        )
        result = await self._session.execute(stmt)
        out: dict[str, list[str]] = defaultdict(list)
        for source, source_id in result.all():
            out[source].append(source_id)
        return dict(out)

    async def merge_canonicals(
        self,
        *,
        project_id: UUID,
        entity_kind: str,
        keep_canonical_id: UUID,
        merge_canonical_ids: Iterable[UUID],
    ) -> int:
        """Re-point every mapping at `merge_canonical_ids` to `keep_canonical_id`.

        Used by the (post-alpha) cross-source reconciler when it determines
        that two source rows are the same entity. Returns the number of
        rows re-pointed.

        The canonical row itself in the per-tenant table is the upserter's
        responsibility to consolidate — this method only updates the index.
        """
        merge_set = list(set(merge_canonical_ids))
        if not merge_set:
            return 0
        from sqlalchemy import update

        stmt = (
            update(EntityIdMap)
            .where(
                EntityIdMap.project_id == project_id,
                EntityIdMap.entity_kind == entity_kind,
                EntityIdMap.canonical_id.in_(merge_set),
            )
            .values(canonical_id=keep_canonical_id)
        )
        result = await self._session.execute(stmt)
        # `Result.rowcount` exists at runtime for UPDATE/DELETE; mypy's stubs
        # don't expose it on the Result generic.
        rowcount = int(getattr(result, "rowcount", 0) or 0)
        logger.info(
            "entity_canonicals_merged",
            project_id=str(project_id),
            entity_kind=entity_kind,
            keep=str(keep_canonical_id),
            merged=[str(c) for c in merge_set],
            rowcount=rowcount,
        )
        return rowcount

    async def delete_mapping(self, *, key: MappingKey) -> bool:
        """Delete the entity_id_map row for ``key``.

        Returns ``True`` when a row was actually removed.
        """
        stmt = (
            delete(EntityIdMap)
            .where(
                EntityIdMap.project_id == key.project_id,
                EntityIdMap.entity_kind == key.entity_kind,
                EntityIdMap.source == key.source,
                EntityIdMap.source_id == key.source_id,
            )
        )
        result = await self._session.execute(stmt)
        rowcount = int(getattr(result, "rowcount", 0) or 0)
        logger.info(
            "entity_mapping_deleted",
            project_id=str(key.project_id),
            entity_kind=key.entity_kind,
            source=key.source,
            source_id=key.source_id,
            rowcount=rowcount,
        )
        return rowcount > 0


def identity_hash(values: Iterable[str]) -> str:
    canonical = json.dumps(list(values), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
