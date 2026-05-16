"""Build a formal semantic layer from agent roles and generated surfaces."""

from __future__ import annotations

from typing import Any, cast

from app.semantic_layer.contracts import (
    SemanticAggregateKind,
    SemanticDimension,
    SemanticEntity,
    SemanticLayerPackage,
    SemanticMeasure,
    SemanticMetric,
    SemanticSurfaceBinding,
)


def build_semantic_layer(run: Any) -> SemanticLayerPackage:
    run_data = _dump(run)
    business_model = _record(run_data.get("business_model"))
    field_roles = _record_list(run_data.get("field_roles"))
    asset_roles = _record_list(run_data.get("asset_roles"))
    business_surfaces = _record(run_data.get("business_surfaces"))
    surfaces = _record_list(business_surfaces.get("surfaces"))

    entities = _entities(business_model, asset_roles, field_roles)
    dimensions = _dimensions(field_roles, surfaces)
    measures = _measures(field_roles, surfaces)
    metrics = _metrics(measures, dimensions, surfaces)
    surface_bindings = _surface_bindings(surfaces, entities, dimensions, measures, metrics)

    return SemanticLayerPackage(
        entities=entities,
        dimensions=dimensions,
        measures=measures,
        metrics=metrics,
        surfaces=surface_bindings,
        generated_from={
            "business_model_entity_count": len(_record_list(business_model.get("entities"))),
            "asset_role_count": len(asset_roles),
            "field_role_count": len(field_roles),
            "surface_count": len(surfaces),
        },
        confidence=_confidence(
            [
                *[entity.confidence for entity in entities],
                *[dimension.confidence for dimension in dimensions],
                *[measure.confidence for measure in measures],
                *[metric.confidence for metric in metrics],
            ]
        ),
    )


def _entities(
    business_model: dict[str, Any],
    asset_roles: list[dict[str, Any]],
    field_roles: list[dict[str, Any]],
) -> list[SemanticEntity]:
    entities: list[SemanticEntity] = []
    for entity in _record_list(business_model.get("entities")):
        name = _text(entity.get("name"))
        if not name:
            continue
        entity_id = _slug(name)
        primary_asset_id = _text(entity.get("primary_asset_id")) or None
        related_asset_ids = _list_of_text(entity.get("related_asset_ids"))
        fields = [
            field
            for field in field_roles
            if _text(field.get("asset_id")) in {primary_asset_id, *related_asset_ids}
            or _text(field.get("entity_hint")).lower() == name.lower()
        ]
        entities.append(
            SemanticEntity(
                entity_id=entity_id,
                name=name,
                plural=_text(entity.get("plural"), f"{name}s"),
                description=_text(entity.get("description"), f"{name.title()} records."),
                primary_asset_id=primary_asset_id,
                source_asset_ids=_unique([primary_asset_id or "", *related_asset_ids]),
                field_refs=_unique(_text(field.get("field_id")) for field in fields),
                why=f"{name} was identified by the business model and connected semantic roles.",
                confidence=0.82,
            )
        )

    known = {entity.entity_id for entity in entities}
    for asset in asset_roles:
        entity_type = _text(asset.get("entity_type"))
        if not entity_type or entity_type.lower() == "unknown":
            continue
        entity_id = _slug(entity_type)
        if entity_id in known:
            continue
        fields = [
            field
            for field in field_roles
            if _text(field.get("asset_id")) == _text(asset.get("asset_id"))
            or _text(field.get("entity_hint")).lower() == entity_type.lower()
        ]
        entities.append(
            SemanticEntity(
                entity_id=entity_id,
                name=entity_type,
                plural=f"{entity_type}s",
                description=f"{entity_type.title()} records discovered from asset roles.",
                primary_asset_id=_text(asset.get("asset_id")) or None,
                source_asset_ids=_unique([_text(asset.get("asset_id"))]),
                field_refs=_unique(_text(field.get("field_id")) for field in fields),
                why=_text(asset.get("why"), "Entity was discovered from source shape."),
                confidence=_float(asset.get("confidence"), 0.65),
            )
        )
        known.add(entity_id)
    return entities


def _dimensions(
    field_roles: list[dict[str, Any]],
    surfaces: list[dict[str, Any]],
) -> list[SemanticDimension]:
    by_id: dict[str, SemanticDimension] = {}
    surface_dimensions = {
        _text(dimension.get("field_id")): dimension
        for surface in surfaces
        for dimension in _record_list(surface.get("dimensions"))
    }
    for field in field_roles:
        role = _text(field.get("role"))
        field_id = _text(field.get("field_id"))
        asset_id = _text(field.get("asset_id"))
        if not field_id or not asset_id:
            continue
        if role not in {"label", "timestamp", "status", "category", "identifier", "primary_key", "foreign_key"} and field_id not in surface_dimensions:
            continue
        surface_dim = surface_dimensions.get(field_id, {})
        kind = _text(surface_dim.get("kind"), _dimension_kind(field))
        by_id[_stable_id("dimension", field_id)] = SemanticDimension(
            dimension_id=_stable_id("dimension", field_id),
            name=_slug(_text(field.get("semantic_type"), _text(field.get("field_name"), field_id))),
            label=_humanize(_text(surface_dim.get("label"), _text(field.get("field_name"), field_id))),
            kind=kind,
            entity_id=_slug(_text(field.get("entity_hint"))) or None,
            field_id=field_id,
            asset_id=asset_id,
            data_type=_text(field.get("semantic_type")) or None,
            why=_text(surface_dim.get("why"), _text(field.get("why"), "Field can be used as a dimension.")),
            confidence=max(_float(field.get("confidence"), 0.65), _float(surface_dim.get("confidence"), 0.0)),
        )
    return list(by_id.values())


def _measures(
    field_roles: list[dict[str, Any]],
    surfaces: list[dict[str, Any]],
) -> list[SemanticMeasure]:
    by_id: dict[str, SemanticMeasure] = {}
    surface_measures = {
        _text(measure.get("field_id")): measure
        for surface in surfaces
        for measure in _record_list(surface.get("measures"))
    }
    for field in field_roles:
        field_id = _text(field.get("field_id"))
        asset_id = _text(field.get("asset_id"))
        if not field_id or not asset_id:
            continue
        if _text(field.get("role")) != "measure" and field_id not in surface_measures:
            continue
        surface_measure = surface_measures.get(field_id, {})
        kind = _text(surface_measure.get("kind"), _text(field.get("measure_kind"), "unknown"))
        by_id[_stable_id("measure", field_id)] = SemanticMeasure(
            measure_id=_stable_id("measure", field_id),
            name=_slug(_text(field.get("measure_kind"), _text(field.get("semantic_type"), field_id))),
            label=_humanize(_text(surface_measure.get("label"), _text(field.get("field_name"), field_id))),
            kind=kind,
            field_id=field_id,
            asset_id=asset_id,
            default_aggregate=_aggregate(kind, _text(surface_measure.get("default_aggregate"))),
            unit=_text(surface_measure.get("unit")) or ("money" if _is_money(kind) else None),
            why=_text(surface_measure.get("why"), _text(field.get("why"), "Field can be used as a measure.")),
            confidence=max(_float(field.get("confidence"), 0.65), _float(surface_measure.get("confidence"), 0.0)),
        )
    return list(by_id.values())


def _metrics(
    measures: list[SemanticMeasure],
    dimensions: list[SemanticDimension],
    surfaces: list[dict[str, Any]],
) -> list[SemanticMetric]:
    dimensions_by_field = {dimension.field_id: dimension for dimension in dimensions}
    measures_by_field = {measure.field_id: measure for measure in measures}
    metrics: dict[str, SemanticMetric] = {}
    for surface in surfaces:
        surface_id = _text(surface.get("surface_id"))
        for measure in _record_list(surface.get("measures")):
            field_id = _text(measure.get("field_id"))
            semantic_measure = measures_by_field.get(field_id)
            if semantic_measure is None:
                continue
            related_dims = [
                dimensions_by_field[_text(dimension.get("field_id"))].dimension_id
                for dimension in _record_list(surface.get("dimensions"))[:5]
                if _text(dimension.get("field_id")) in dimensions_by_field
            ]
            metric_id = _stable_id("metric", f"{surface_id}:{semantic_measure.name}")
            metrics[metric_id] = SemanticMetric(
                metric_id=metric_id,
                name=f"{surface_id}_{semantic_measure.name}",
                label=f"{surface.get('title', surface_id)} · {semantic_measure.label}",
                description=f"{semantic_measure.label} measured inside {surface.get('title', surface_id)}.",
                measure_refs=[semantic_measure.measure_id],
                dimension_refs=related_dims,
                expression={
                    "aggregate": semantic_measure.default_aggregate,
                    "measure_id": semantic_measure.measure_id,
                },
                default_grain=related_dims[0] if related_dims else None,
                source_surface_ids=[surface_id],
                why=f"This metric is governed by the {surface.get('title', surface_id)} surface.",
                confidence=min(0.95, semantic_measure.confidence + 0.05),
            )
    return list(metrics.values())


def _surface_bindings(
    surfaces: list[dict[str, Any]],
    entities: list[SemanticEntity],
    dimensions: list[SemanticDimension],
    measures: list[SemanticMeasure],
    metrics: list[SemanticMetric],
) -> list[SemanticSurfaceBinding]:
    entity_by_name = {entity.name.lower(): entity for entity in entities}
    dimension_by_field = {dimension.field_id: dimension.dimension_id for dimension in dimensions}
    measure_by_field = {measure.field_id: measure.measure_id for measure in measures}
    bindings: list[SemanticSurfaceBinding] = []
    for surface in surfaces:
        surface_id = _text(surface.get("surface_id"))
        if not surface_id:
            continue
        surface_dimensions = _record_list(surface.get("dimensions"))
        surface_measures = _record_list(surface.get("measures"))
        metric_refs = [
            metric.metric_id
            for metric in metrics
            if surface_id in metric.source_surface_ids
        ]
        entity_ref = entity_by_name.get(_text(surface.get("entity")).lower())
        bindings.append(
            SemanticSurfaceBinding(
                surface_id=surface_id,
                title=_text(surface.get("title"), _humanize(surface_id)),
                entity_refs=[entity_ref.entity_id] if entity_ref else [],
                dimension_refs=_unique(
                    dimension_by_field.get(_text(dimension.get("field_id")), "")
                    for dimension in surface_dimensions
                ),
                measure_refs=_unique(
                    measure_by_field.get(_text(measure.get("field_id")), "")
                    for measure in surface_measures
                ),
                metric_refs=metric_refs,
                why=_text(surface.get("why_built"), "Surface is available from semantic roles."),
            )
        )
    return bindings


def _dimension_kind(field: dict[str, Any]) -> str:
    blob = " ".join(
        _text(field.get(key))
        for key in ("field_id", "field_name", "semantic_type", "role", "entity_hint")
    ).lower()
    if "date" in blob or "time" in blob or _text(field.get("role")) == "timestamp":
        return "time"
    if "status" in blob:
        return "status"
    if any(term in blob for term in ("party", "customer", "vendor", "supplier")):
        return "party"
    if any(term in blob for term in ("product", "sku", "item")):
        return "product"
    if any(term in blob for term in ("city", "state", "location")):
        return "location"
    return _text(field.get("role"), "unknown")


def _aggregate(kind: str, existing: str) -> SemanticAggregateKind:
    if existing in {"sum", "avg", "count", "min", "max"}:
        return cast(SemanticAggregateKind, existing)
    if kind in {"rate"}:
        return "avg"
    if kind == "count":
        return "count"
    return "sum"


def _is_money(kind: str) -> bool:
    return kind in {"amount", "pending_amount", "bill_amount", "revenue", "cost", "expense"}


def _dump(value: Any) -> dict[str, Any]:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    return value if isinstance(value, dict) else {}


def _record(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    return {}


def _record_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [_record(item) for item in value if _record(item)]


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _list_of_text(value: Any) -> list[str]:
    return _unique(_text(item) for item in _list(value))


def _text(value: Any, fallback: str = "") -> str:
    return value.strip() if isinstance(value, str) and value.strip() else fallback


def _float(value: Any, fallback: float) -> float:
    if isinstance(value, int | float):
        return float(value)
    return fallback


def _unique(values: Any) -> list[str]:
    result: list[str] = []
    for value in values:
        if not isinstance(value, str):
            continue
        clean = value.strip()
        if clean and clean not in result:
            result.append(clean)
    return result


def _slug(value: str) -> str:
    return value.lower().replace(" ", "_").replace("-", "_").replace(".", "_").strip("_")


def _stable_id(prefix: str, value: str) -> str:
    return f"{prefix}:{_slug(value)}"


def _humanize(value: Any) -> str:
    text = _text(value, "Unknown")
    return text.replace("_", " ").replace("-", " ").title()


def _confidence(values: list[float]) -> float:
    if not values:
        return 0.0
    return round(sum(values) / len(values), 2)
