"""Resolve Agent Plane ids into canonical storage metadata."""

from __future__ import annotations

from uuid import UUID

from app.analysis_contracts import AnalysisGraphPlan
from app.execution_plane.contracts import (
    ExecutionCatalog,
    PlanValidationError,
)
from app.execution_plane.store import load_execution_catalog_records


async def resolve_execution_catalog(
    organization_id: UUID,
    plan: AnalysisGraphPlan,
) -> ExecutionCatalog:
    """Load only the canonical assets/fields/relationship evidence a plan uses."""
    asset_ids = _asset_ids(plan)
    field_ids = _field_ids(plan)
    asset_uuids = _uuid_values(asset_ids, kind="asset")
    catalog = await load_execution_catalog_records(
        organization_id,
        asset_uuids=asset_uuids,
        field_ids=field_ids,
    )
    _ensure_catalog_complete(catalog, asset_ids=asset_ids, field_ids=field_ids)
    return catalog


def _asset_ids(plan: AnalysisGraphPlan) -> set[str]:
    return {op.asset_id for op in plan.operators if op.op == "source"}


def _field_ids(plan: AnalysisGraphPlan) -> set[str]:
    field_ids: set[str] = set()
    for op in plan.operators:
        if op.op == "select":
            field_ids.update(op.field_ids)
        elif op.op == "filter":
            field_ids.update(predicate.field_id for predicate in op.predicates)
        elif op.op == "join":
            field_ids.add(op.left_field_id)
            field_ids.add(op.right_field_id)
        elif op.op == "aggregate":
            field_ids.update(op.group_by_field_ids)
            field_ids.update(measure.field_id for measure in op.measures if measure.field_id)
    return field_ids


def _ensure_catalog_complete(
    catalog: ExecutionCatalog,
    *,
    asset_ids: set[str],
    field_ids: set[str],
) -> None:
    missing_assets = sorted(asset_ids - set(catalog.assets))
    if missing_assets:
        raise PlanValidationError("Unknown asset ids", details={"asset_ids": missing_assets})
    missing_fields = sorted(field_ids - set(catalog.fields))
    if missing_fields:
        raise PlanValidationError("Unknown field ids", details={"field_ids": missing_fields})
    for field_id in field_ids:
        field = catalog.fields[field_id]
        if field.asset_id not in catalog.assets:
            raise PlanValidationError(
                "Field belongs to an asset that is not in the plan source set",
                details={"field_id": field_id, "asset_id": field.asset_id},
            )


def _uuid_values(values: set[str], *, kind: str) -> list[UUID]:
    uuids: list[UUID] = []
    for value in values:
        try:
            uuids.append(UUID(value))
        except ValueError as exc:
            raise PlanValidationError(
                f"Invalid {kind} id",
                details={f"{kind}_id": value},
            ) from exc
    return uuids
