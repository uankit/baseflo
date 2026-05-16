"""Persistence boundary for resolving execution catalog metadata."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import or_, select

from app.db.models import CanonicalAsset, CanonicalField, DataGraphEdge
from app.db.session import open_session
from app.execution_plane.contracts import (
    ExecutionCatalog,
    ResolvedAsset,
    ResolvedField,
    ResolvedRelationship,
)


async def load_execution_catalog_records(
    organization_id: UUID,
    *,
    asset_uuids: list[UUID],
    field_ids: set[str],
) -> ExecutionCatalog:
    async with open_session() as session:
        assets = list(
            (
                await session.execute(
                    select(CanonicalAsset).where(
                        CanonicalAsset.organization_id == organization_id,
                        CanonicalAsset.id.in_(asset_uuids),
                    )
                )
            )
            .scalars()
            .all()
        ) if asset_uuids else []
        fields = list(
            (
                await session.execute(
                    select(CanonicalField).where(
                        CanonicalField.organization_id == organization_id,
                        CanonicalField.asset_id.in_(asset_uuids),
                    )
                )
            )
            .scalars()
            .all()
        ) if asset_uuids else []
        edges = list(
            (
                await session.execute(
                    select(DataGraphEdge).where(
                        DataGraphEdge.organization_id == organization_id,
                        DataGraphEdge.predicate == "RELATIONSHIP_CANDIDATE",
                        DataGraphEdge.status == "active",
                        or_(
                            DataGraphEdge.subject_id.in_([_field_node_id(value) for value in field_ids]),
                            DataGraphEdge.object_id.in_([_field_node_id(value) for value in field_ids]),
                        ),
                    )
                )
            )
            .scalars()
            .all()
        ) if field_ids else []

    return ExecutionCatalog(
        assets={
            str(asset.id): ResolvedAsset(
                asset_id=str(asset.id),
                qualified_name=asset.qualified_name,
                storage_table=asset.storage_table,
                label=asset.label,
                row_count=asset.row_count,
            )
            for asset in assets
        },
        fields={
            str(field.id): ResolvedField(
                field_id=str(field.id),
                asset_id=str(field.asset_id),
                name=field.name,
                observed_type=field.observed_type,
                storage_type=field.storage_type,
                profile=field.profile or {},
            )
            for field in fields
        },
        relationships=[_resolved_relationship(edge) for edge in edges],
    )


def _resolved_relationship(edge: DataGraphEdge) -> ResolvedRelationship:
    evidence = edge.evidence or {}
    left_field_id = evidence.get("left_field_id") or _strip_field_node(edge.subject_id)
    right_field_id = evidence.get("right_field_id") or _strip_field_node(edge.object_id)
    return ResolvedRelationship(
        left_field_id=str(left_field_id),
        right_field_id=str(right_field_id),
        confidence=edge.confidence,
        evidence=evidence,
    )


def _field_node_id(field_id: str) -> str:
    return f"canonical_field:{field_id}"


def _strip_field_node(node_id: str) -> str:
    return node_id.removeprefix("canonical_field:")
