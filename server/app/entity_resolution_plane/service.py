"""Planning boundary for Baseflo entity resolution."""

from __future__ import annotations

import asyncio
from typing import Any
from uuid import UUID

from app.business_surface_plane.contracts import BusinessSurfacePackage
from app.data_plane.naming import quote_ident
from app.data_plane.storage import safe_query
from app.entity_resolution_plane.contracts import (
    EntityResolutionDataset,
    EntityResolutionExecution,
    EntityResolutionField,
    EntityResolutionFieldRole,
    EntityResolutionPlan,
    EntityResolutionRunResult,
)
from app.entity_resolution_plane.splink_engine import SplinkEntityResolutionEngine
from app.execution_plane.contracts import ExecutionCatalog
from app.execution_plane.store import load_execution_catalog_records


def plan_entity_resolution_from_surfaces(package: BusinessSurfacePackage | None) -> EntityResolutionRunResult:
    if package is None:
        return EntityResolutionRunResult()
    plans: list[EntityResolutionPlan] = []
    for surface in package.surfaces:
        for view in surface.candidate_views:
            if view.algorithm != "probabilistic_entity_resolution":
                continue
            fields = [
                _field_from_dimension(dimension)
                for dimension in surface.dimensions
                if dimension.dimension_id in set(view.dimensions)
            ]
            if len(fields) < 2:
                continue
            plans.append(
                EntityResolutionPlan(
                    plan_id=f"er:{view.view_id}",
                    surface_id=surface.surface_id,
                    view_id=view.view_id,
                    entity=_entity(surface.entity, fields),
                    link_type="link_only",
                    fields=fields,
                    blocking_fields=_blocking_fields(fields),
                    threshold_match_probability=0.85,
                    why=view.why,
                )
            )
    return EntityResolutionRunResult(
        plans=plans,
        executions=[EntityResolutionExecution(plan_id=plan.plan_id, status="planned") for plan in plans],
        generated_from={
            "surface_count": len(package.surfaces),
            "candidate_entity_resolution_views": len(plans),
            "engine": "splink",
        },
    )


def execute_entity_resolution(
    plan: EntityResolutionPlan,
    datasets: list[Any],
    *,
    engine: SplinkEntityResolutionEngine | None = None,
    max_pairs: int = 500,
) -> EntityResolutionExecution:
    runner = engine or SplinkEntityResolutionEngine()
    return runner.run(plan, datasets, max_pairs=max_pairs)


async def run_entity_resolution_from_surfaces(
    organization_id: UUID,
    package: BusinessSurfacePackage | None,
    *,
    max_rows_per_dataset: int = 500,
    max_pairs: int = 500,
    engine: SplinkEntityResolutionEngine | None = None,
) -> EntityResolutionRunResult:
    planned = plan_entity_resolution_from_surfaces(package)
    if not planned.plans:
        return planned
    executions: list[EntityResolutionExecution] = []
    runner = engine or SplinkEntityResolutionEngine()
    for plan in planned.plans:
        try:
            datasets = await _datasets_for_plan(
                organization_id,
                plan,
                max_rows_per_dataset=max_rows_per_dataset,
            )
            execution = await asyncio.to_thread(
                runner.run,
                plan,
                datasets,
                max_pairs=max_pairs,
            )
            executions.append(execution)
        except Exception as exc:
            executions.append(
                EntityResolutionExecution(
                    plan_id=plan.plan_id,
                    status="failed",
                    error=str(exc),
                )
            )
    return planned.model_copy(update={"executions": executions})


async def _datasets_for_plan(
    organization_id: UUID,
    plan: EntityResolutionPlan,
    *,
    max_rows_per_dataset: int,
) -> list[EntityResolutionDataset]:
    asset_ids = _asset_ids(plan)
    field_ids = {field.field_id for field in plan.fields}
    catalog = await load_execution_catalog_records(
        organization_id,
        asset_uuids=[_uuid(asset_id, "asset") for asset_id in asset_ids],
        field_ids=field_ids,
    )
    return await asyncio.to_thread(
        _load_datasets,
        organization_id,
        plan,
        catalog,
        max_rows_per_dataset,
    )


def _field_from_dimension(dimension: Any) -> EntityResolutionField:
    return EntityResolutionField(
        field_id=dimension.field_id,
        asset_id=dimension.asset_id,
        label=dimension.label,
        role=_role(dimension.kind, dimension.label),
        weight=dimension.confidence,
    )


def _role(kind: str, label: str) -> EntityResolutionFieldRole:
    blob = f"{kind} {label}".lower()
    if "email" in blob:
        return "email"
    if any(term in blob for term in ("phone", "mobile", "contact")):
        return "phone"
    if kind in {"party", "customer", "product", "item"}:
        return "name"
    if kind == "entity":
        return "identifier"
    if kind == "location":
        return "address"
    if kind == "category":
        return "category"
    return "unknown"


def _entity(entity: str | None, fields: list[EntityResolutionField]) -> str:
    if entity:
        return entity
    for field in fields:
        if field.role == "name":
            return field.label.lower().replace(" ", "_")
    return "entity"


def _blocking_fields(fields: list[EntityResolutionField]) -> list[str]:
    preferred = [field.field_id for field in fields if field.role in {"email", "identifier", "name"}]
    return preferred[:2] if preferred else [fields[0].field_id]


def _load_datasets(
    organization_id: UUID,
    plan: EntityResolutionPlan,
    catalog: ExecutionCatalog,
    max_rows_per_dataset: int,
) -> list[EntityResolutionDataset]:
    datasets: list[EntityResolutionDataset] = []
    fields_by_asset: dict[str, list[EntityResolutionField]] = {}
    for field in plan.fields:
        if field.asset_id not in catalog.assets:
            raise ValueError(f"Unknown asset id for entity resolution: {field.asset_id}")
        if field.field_id not in catalog.fields:
            raise ValueError(f"Unknown field id for entity resolution: {field.field_id}")
        fields_by_asset.setdefault(field.asset_id, []).append(field)

    for asset_id, fields in fields_by_asset.items():
        asset = catalog.assets[asset_id]
        select_parts = [f"{quote_ident('_bf_record_id')} AS {quote_ident('bf_record_id')}"]
        field_map: dict[str, str] = {}
        for field in fields:
            resolved = catalog.fields[field.field_id]
            alias = _canonical_column(field.field_id)
            select_parts.append(f"{quote_ident(resolved.name)} AS {quote_ident(alias)}")
            field_map[field.field_id] = alias
        where_clause = " OR ".join(
            f"{quote_ident(catalog.fields[field.field_id].name)} IS NOT NULL"
            for field in fields
        )
        sql = (
            f"SELECT {', '.join(select_parts)} "
            f"FROM {quote_ident(asset.storage_table)} "
            f"WHERE {where_clause} "
            f"LIMIT {max_rows_per_dataset}"
        )
        rows = safe_query(organization_id, sql, max_rows=max_rows_per_dataset)
        datasets.append(
            EntityResolutionDataset(
                dataset_id=asset_id,
                label=asset.label,
                rows=rows,
                field_map=field_map,
            )
        )
    return datasets


def _asset_ids(plan: EntityResolutionPlan) -> list[str]:
    result: list[str] = []
    for field in plan.fields:
        if field.asset_id not in result:
            result.append(field.asset_id)
    return result


def _uuid(value: str, kind: str) -> UUID:
    try:
        return UUID(value)
    except ValueError as exc:
        raise ValueError(f"Invalid {kind} id for entity resolution: {value}") from exc


def _canonical_column(field_id: str) -> str:
    return field_id.replace(".", "__").replace("-", "_").replace(" ", "_").lower()
