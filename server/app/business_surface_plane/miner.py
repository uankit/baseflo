"""Deterministically mine generated operating surfaces from a run result."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.business_surface_plane.contracts import (
    AggregateKind,
    BulkActionPack,
    BusinessSurface,
    BusinessSurfacePackage,
    CandidateView,
    DimensionKind,
    InsightGraph,
    InsightGraphEdge,
    InsightGraphNode,
    MeasureKind,
    MiningAlgorithm,
    SurfaceCohort,
    SurfaceDimension,
    SurfaceKind,
    SurfaceMeasure,
)


@dataclass(frozen=True, slots=True)
class _SurfaceSpec:
    kind: SurfaceKind
    title: str
    description: str
    entity: str | None
    terms: tuple[str, ...]
    measure_terms: tuple[str, ...]
    dimension_terms: tuple[str, ...]


_SPECS: tuple[_SurfaceSpec, ...] = (
    _SurfaceSpec(
        kind="receivables",
        title="Receivables Workbench",
        description="Parties, bills, pending balances, ageing, and follow-up cohorts.",
        entity="party",
        terms=("receivable", "pending", "balance", "due", "bill", "invoice", "party"),
        measure_terms=("pending", "balance", "due", "bill", "invoice", "amount"),
        dimension_terms=("party", "customer", "vendor", "account", "name", "city", "date", "status"),
    ),
    _SurfaceSpec(
        kind="inventory",
        title="Inventory Workbench",
        description="Products, quantities, stock cover, movement, and low-stock cohorts.",
        entity="product",
        terms=("inventory", "stock", "qty", "quantity", "product", "item", "sku", "variant"),
        measure_terms=("inventory", "stock", "qty", "quantity", "sold", "available"),
        dimension_terms=("product", "item", "sku", "variant", "category", "location", "status"),
    ),
    _SurfaceSpec(
        kind="sales",
        title="Sales Workbench",
        description="Selling activity by party, product, time, channel, and value.",
        entity="sale",
        terms=("sale", "sales", "revenue", "order", "bill", "invoice", "amount", "customer"),
        measure_terms=("sale", "sales", "revenue", "order", "bill", "invoice", "amount", "total"),
        dimension_terms=("party", "customer", "product", "item", "date", "channel", "city", "status"),
    ),
    _SurfaceSpec(
        kind="profit_loss",
        title="Profit & Loss Workbench",
        description="Revenue, cost, expenses, and margin-risk views.",
        entity=None,
        terms=("profit", "loss", "revenue", "sale", "expense", "cost", "spend", "payment"),
        measure_terms=("revenue", "sale", "expense", "cost", "spend", "amount", "payment"),
        dimension_terms=("date", "head", "category", "party", "product", "item", "status"),
    ),
    _SurfaceSpec(
        kind="customers_parties",
        title="Customers & Parties Workbench",
        description="Named relationships, buying behavior, contactability, and account cohorts.",
        entity="party",
        terms=("customer", "party", "vendor", "supplier", "account", "name", "email", "phone"),
        measure_terms=("amount", "revenue", "orders", "pending", "balance", "count"),
        dimension_terms=("customer", "party", "vendor", "supplier", "account", "name", "email", "phone", "city"),
    ),
    _SurfaceSpec(
        kind="products_items",
        title="Products & Items Workbench",
        description="Item-level selling, stock, category, and performance views.",
        entity="product",
        terms=("product", "item", "sku", "style", "variant", "category", "article"),
        measure_terms=("amount", "revenue", "qty", "quantity", "stock", "inventory", "sold"),
        dimension_terms=("product", "item", "sku", "variant", "category", "style", "article"),
    ),
    _SurfaceSpec(
        kind="expenses",
        title="Expenses Workbench",
        description="Costs, spends, payments, and outflow concentration.",
        entity="expense",
        terms=("expense", "cost", "spend", "paid", "payment", "debit"),
        measure_terms=("expense", "cost", "spend", "paid", "payment", "debit", "amount"),
        dimension_terms=("head", "category", "party", "vendor", "date", "status"),
    ),
    _SurfaceSpec(
        kind="operations",
        title="Operations Workbench",
        description="Statuses, returns, fulfillment, process exceptions, and operational queues.",
        entity=None,
        terms=("status", "return", "fulfillment", "delivery", "task", "process", "operation"),
        measure_terms=("count", "days", "qty", "quantity", "amount"),
        dimension_terms=("status", "return", "delivery", "party", "product", "date", "location"),
    ),
    _SurfaceSpec(
        kind="data_quality",
        title="Data Quality Workbench",
        description="Coverage, missing fields, weak joins, and profile evidence.",
        entity=None,
        terms=("quality", "source", "field", "join", "relationship", "missing", "coverage"),
        measure_terms=("count", "row", "field", "relationship"),
        dimension_terms=("source", "field", "asset", "status"),
    ),
)

_SPEC_BY_KIND = {spec.kind: spec for spec in _SPECS}


def mine_business_surfaces(run: Any) -> BusinessSurfacePackage:
    """Generate operating surfaces, candidate drilldowns, cohorts, and graph links.

    This layer is intentionally deterministic. It does not execute analyses and
    it does not invent fields. It only re-composes existing semantic roles,
    materialized evidence, and business-view sections into inspectable workbench
    structure.
    """

    run_data = _dump(run)
    business_view = _record(run_data.get("business_view"))
    sections = _record_list(business_view.get("sections"))
    field_roles = _record_list(run_data.get("field_roles"))
    asset_roles = _record_list(run_data.get("asset_roles"))
    executions = _record_list(run_data.get("executions"))
    patterns = _record(run_data.get("patterns"))
    context = _record(run_data.get("context_summary"))

    surfaces = _surfaces_from_sections(
        sections=sections,
        field_roles=field_roles,
        asset_roles=asset_roles,
        executions=executions,
        patterns=patterns,
    )
    if not surfaces:
        surfaces = _surfaces_from_semantics(
            field_roles=field_roles,
            asset_roles=asset_roles,
            executions=executions,
            patterns=patterns,
        )
    if not surfaces:
        surfaces = [_connected_surface(field_roles, asset_roles, executions)]

    graph = _build_insight_graph(surfaces)
    algorithms = _algorithms(surfaces)
    return BusinessSurfacePackage(
        headline=f"{len(surfaces)} generated operating surfaces",
        summary=(
            f"Baseflo mined {sum(len(surface.candidate_views) for surface in surfaces)} "
            f"candidate views, {sum(len(surface.cohorts) for surface in surfaces)} cohorts, "
            f"and {sum(len(surface.action_packs) for surface in surfaces)} action packs."
        ),
        why=(
            "The surface miner applies semantic table interpretation, data-cube drilldown, "
            "candidate insight ranking, and entity-graph linking over the canonical data plane."
        ),
        algorithms=algorithms,
        surfaces=surfaces,
        insight_graph=graph,
        generated_from={
            "asset_count": context.get("asset_count", len(asset_roles)),
            "field_count": context.get("field_count", len(field_roles)),
            "row_count": context.get("row_count", 0),
            "business_view_section_count": len(sections),
        },
        confidence=_package_confidence(surfaces),
    )


def _surfaces_from_sections(
    *,
    sections: list[dict[str, Any]],
    field_roles: list[dict[str, Any]],
    asset_roles: list[dict[str, Any]],
    executions: list[dict[str, Any]],
    patterns: dict[str, Any],
) -> list[BusinessSurface]:
    surfaces: list[BusinessSurface] = []
    for section in sections:
        kind = _surface_kind(_text(section.get("kind")))
        if kind is None:
            continue
        spec = _surface_spec(kind)
        field_refs = set(_list_of_text(section.get("field_refs")))
        asset_refs = set(_list_of_text(section.get("source_asset_ids")))
        graph_refs = _list_of_text(section.get("graph_refs"))
        candidate_fields = [
            field
            for field in field_roles
            if _text(field.get("field_id")) in field_refs
            or _text(field.get("asset_id")) in asset_refs
            or _matches(_field_blob(field), spec.terms)
        ]
        candidate_assets = [
            asset
            for asset in asset_roles
            if _text(asset.get("asset_id")) in asset_refs
            or _matches(_asset_blob(asset), spec.terms)
        ]
        graph_matches = _graphs_by_refs_or_terms(
            executions=executions,
            patterns=patterns,
            graph_refs=graph_refs,
            terms=spec.terms,
        )
        surface = _surface(
            spec=spec,
            title=_text(section.get("title"), spec.title),
            description=_text(section.get("description"), spec.description),
            why_built=_text(section.get("why_built"), _why_from_evidence(spec, candidate_fields)),
            fields=candidate_fields,
            assets=candidate_assets,
            graph_refs=graph_refs or [_text(graph.get("graph_id")) for graph in graph_matches],
            executions=graph_matches,
            confidence=_float(section.get("confidence"), 0.65),
        )
        surfaces.append(surface)
    return _dedupe_surfaces(surfaces)


def _surfaces_from_semantics(
    *,
    field_roles: list[dict[str, Any]],
    asset_roles: list[dict[str, Any]],
    executions: list[dict[str, Any]],
    patterns: dict[str, Any],
) -> list[BusinessSurface]:
    surfaces: list[BusinessSurface] = []
    for spec in _SPECS:
        fields = [field for field in field_roles if _matches(_field_blob(field), spec.terms)]
        assets = [asset for asset in asset_roles if _matches(_asset_blob(asset), spec.terms)]
        graphs = _graphs_by_refs_or_terms(
            executions=executions,
            patterns=patterns,
            graph_refs=[],
            terms=spec.terms,
        )
        if not fields and not assets and not graphs:
            continue
        surfaces.append(
            _surface(
                spec=spec,
                title=spec.title,
                description=spec.description,
                why_built=_why_from_evidence(spec, fields),
                fields=fields,
                assets=assets,
                graph_refs=[_text(graph.get("graph_id")) for graph in graphs],
                executions=graphs,
                confidence=_surface_confidence(fields, assets, graphs),
            )
        )
    return _dedupe_surfaces(surfaces)


def _surface(
    *,
    spec: _SurfaceSpec,
    title: str,
    description: str,
    why_built: str,
    fields: list[dict[str, Any]],
    assets: list[dict[str, Any]],
    graph_refs: list[str],
    executions: list[dict[str, Any]],
    confidence: float,
) -> BusinessSurface:
    dimensions = _dimensions(spec, fields)
    measures = _measures(spec, fields)
    candidate_views = _candidate_views(spec, dimensions, measures, graph_refs, executions)
    cohorts = _cohorts(spec, dimensions, measures, graph_refs)
    action_packs = _action_packs(spec, dimensions, measures, cohorts, graph_refs, fields)
    asset_ids = _unique(
        [
            *[_text(asset.get("asset_id")) for asset in assets],
            *[_text(field.get("asset_id")) for field in fields],
        ]
    )
    field_refs = _unique(_text(field.get("field_id")) for field in fields)
    surface_id = spec.kind
    return BusinessSurface(
        surface_id=surface_id,
        kind=spec.kind,
        title=title if title.endswith("Workbench") else f"{title} Workbench",
        description=description,
        entity=spec.entity,
        why_built=why_built,
        source_asset_ids=asset_ids,
        field_refs=field_refs,
        graph_refs=_unique(graph_refs),
        dimensions=dimensions,
        measures=measures,
        candidate_views=candidate_views,
        cohorts=cohorts,
        action_packs=action_packs,
        confidence=round(min(confidence, 0.98), 2),
    )


def _dimensions(spec: _SurfaceSpec, fields: list[dict[str, Any]]) -> list[SurfaceDimension]:
    dimensions: list[SurfaceDimension] = []
    for field in fields:
        field_id = _text(field.get("field_id"))
        asset_id = _text(field.get("asset_id"))
        if not field_id or not asset_id:
            continue
        role = _text(field.get("role")).lower()
        blob = _field_blob(field)
        if role not in {"label", "category", "timestamp", "status", "identifier", "foreign_key", "primary_key"} and not _matches(blob, spec.dimension_terms):
            continue
        kind = _dimension_kind(blob, role)
        dimensions.append(
            SurfaceDimension(
                dimension_id=_stable_id("dim", field_id),
                label=_field_label(field),
                kind=kind,
                field_id=field_id,
                asset_id=asset_id,
                entity_hint=_text(field.get("entity_hint")) or None,
                why=(
                    f"{_field_label(field)} can slice {spec.title.replace(' Workbench', '').lower()} "
                    f"because it is a {kind} field."
                ),
                confidence=_float(field.get("confidence"), 0.7),
            )
        )
    return _dedupe_dimensions(dimensions)


def _measures(spec: _SurfaceSpec, fields: list[dict[str, Any]]) -> list[SurfaceMeasure]:
    measures: list[SurfaceMeasure] = []
    for field in fields:
        field_id = _text(field.get("field_id"))
        asset_id = _text(field.get("asset_id"))
        if not field_id or not asset_id:
            continue
        role = _text(field.get("role")).lower()
        blob = _field_meaning_blob(field)
        if role != "measure" and not _matches(blob, spec.measure_terms):
            continue
        kind = _measure_kind(blob)
        measures.append(
            SurfaceMeasure(
                measure_id=_stable_id("measure", field_id),
                label=_field_label(field),
                kind=kind,
                field_id=field_id,
                asset_id=asset_id,
                default_aggregate=_default_aggregate(kind, blob),
                unit="money" if kind in {"amount", "pending_amount", "bill_amount", "revenue", "cost", "expense"} else None,
                why=f"{_field_label(field)} is usable as a {kind} measure.",
                confidence=_float(field.get("confidence"), 0.7),
            )
        )
    return _dedupe_measures(measures)


def _candidate_views(
    spec: _SurfaceSpec,
    dimensions: list[SurfaceDimension],
    measures: list[SurfaceMeasure],
    graph_refs: list[str],
    executions: list[dict[str, Any]],
) -> list[CandidateView]:
    views: list[CandidateView] = []
    if measures and dimensions:
        primary_measure = measures[0]
        primary_dimension = _best_dimension(dimensions)
        if primary_dimension is None:
            return views
        views.append(
            CandidateView(
                view_id=f"{spec.kind}:cube_rollup",
                surface_id=spec.kind,
                title=f"{spec.title.replace(' Workbench', '')} by every useful angle",
                question=(
                    f"Break down {primary_measure.label} by "
                    f"{', '.join(d.label for d in dimensions[:4])}."
                ),
                algorithm="cube_rollup",
                dimensions=[dimension.dimension_id for dimension in dimensions[:4]],
                measures=[measure.measure_id for measure in measures[:3]],
                expected_output="table",
                priority=0.92,
                why=(
                    "Data-cube rollups let the founder move from the headline number "
                    "to party, product, status, source, and time slices without rebuilding the model."
                ),
                execution_hint={
                    "operator_language": "analysis_graph",
                    "operators": ["source", "aggregate", "rank", "limit"],
                    "duckdb_features": ["GROUPING SETS", "ROLLUP", "CUBE"],
                },
            )
        )
        views.append(
            CandidateView(
                view_id=f"{spec.kind}:top_{primary_dimension.kind}_{primary_measure.kind}",
                surface_id=spec.kind,
                title=f"Top {primary_dimension.label} by {primary_measure.label}",
                question=f"Which {primary_dimension.label} records explain most of {primary_measure.label}?",
                algorithm="extreme_rank",
                dimensions=[primary_dimension.dimension_id],
                measures=[primary_measure.measure_id],
                expected_output="bar",
                priority=0.88,
                why="Extreme-rank scans surface the few rows that explain a large part of the business movement.",
                execution_hint={
                    "operator_language": "analysis_graph",
                    "operators": ["source", "aggregate", "rank", "limit"],
                    "rank_direction": "desc",
                },
            )
        )
        views.append(
            CandidateView(
                view_id=f"{spec.kind}:long_tail",
                surface_id=spec.kind,
                title=f"Long tail of {spec.title.replace(' Workbench', '').lower()}",
                question=f"What many small {primary_dimension.label} records add up to a material total?",
                algorithm="long_tail_scan",
                dimensions=[primary_dimension.dimension_id],
                measures=[primary_measure.measure_id],
                expected_output="cohort",
                priority=0.76,
                why=(
                    "Long-tail scans catch the messy operational bulk that single top-N cards miss, "
                    "such as hundreds of small pending balances or many low-stock items."
                ),
                execution_hint={
                    "operator_language": "analysis_graph",
                    "operators": ["source", "aggregate", "filter", "project"],
                    "scan": "tail_contribution",
                },
            )
        )
    if _time_dimensions(dimensions) and measures:
        views.append(
            CandidateView(
                view_id=f"{spec.kind}:trend_change",
                surface_id=spec.kind,
                title=f"{spec.title.replace(' Workbench', '')} trend changes",
                question=f"What changed recently in {measures[0].label}?",
                algorithm="deviation_scan",
                dimensions=[dimension.dimension_id for dimension in _time_dimensions(dimensions)[:1]],
                measures=[measures[0].measure_id],
                expected_output="line",
                priority=0.82,
                why="Trend/deviation scans detect what moved versus recent history before the user asks.",
                execution_hint={
                    "operator_language": "analysis_graph",
                    "operators": ["source", "aggregate", "window", "compare"],
                    "math": ["z_score", "moving_average", "breakpoint"],
                },
            )
        )
    if graph_refs:
        views.append(
            CandidateView(
                view_id=f"{spec.kind}:relationship_walk",
                surface_id=spec.kind,
                title=f"{spec.title.replace(' Workbench', '')} across connected data",
                question="What changes when I follow the business graph to related sources?",
                algorithm="relationship_walk",
                dimensions=[dimension.dimension_id for dimension in dimensions[:3]],
                measures=[measure.measure_id for measure in measures[:2]],
                expected_output="comparison",
                priority=0.8,
                why="Relationship walks turn separate files and connectors into cross-source comparisons.",
                execution_hint={
                    "operator_language": "analysis_graph",
                    "operators": ["source", "join", "aggregate", "compare"],
                    "graph_refs": graph_refs,
                },
            )
        )
    entity_resolution = _entity_resolution_view(spec, dimensions)
    if entity_resolution is not None:
        views.append(entity_resolution)
    if not views:
        row_count = sum(_int(_record(execution.get("result")).get("row_count"), 0) for execution in executions)
        views.append(
            CandidateView(
                view_id=f"{spec.kind}:coverage_scan",
                surface_id=spec.kind,
                title=f"{spec.title.replace(' Workbench', '')} coverage",
                question="What can Baseflo inspect from this data and what is missing?",
                algorithm="coverage_scan",
                expected_output="table",
                priority=0.55,
                why="Coverage scans keep the UI honest when the data has structure but not enough measures yet.",
                execution_hint={"materialized_row_count": row_count, "operator_language": "analysis_graph"},
            )
        )
    return _dedupe_views(views)


def _entity_resolution_view(
    spec: _SurfaceSpec,
    dimensions: list[SurfaceDimension],
) -> CandidateView | None:
    grouped: dict[str, list[SurfaceDimension]] = {}
    for dimension in dimensions:
        if dimension.kind not in {"party", "customer", "product", "item"}:
            continue
        grouped.setdefault(dimension.kind, []).append(dimension)
    for kind, candidates in grouped.items():
        if len({candidate.asset_id for candidate in candidates}) < 2:
            continue
        return CandidateView(
            view_id=f"{spec.kind}:entity_resolution:{kind}",
            surface_id=spec.kind,
            title=f"Match {kind} names across sources",
            question=f"Which {kind} records look like the same real-world entity across connected data?",
            algorithm="probabilistic_entity_resolution",
            dimensions=[candidate.dimension_id for candidate in candidates[:4]],
            expected_output="comparison",
            priority=0.86,
            why=(
                "Probabilistic entity resolution is the bridge from messy source names to one business graph, "
                "especially when Excel, Shopify, and offline ledgers spell entities differently."
            ),
            execution_hint={
                "recommended_backend": "splink",
                "operator_language": "entity_resolution_plan",
                "match_fields": [candidate.field_id for candidate in candidates[:4]],
            },
        )
    return None


def _cohorts(
    spec: _SurfaceSpec,
    dimensions: list[SurfaceDimension],
    measures: list[SurfaceMeasure],
    graph_refs: list[str],
) -> list[SurfaceCohort]:
    cohorts: list[SurfaceCohort] = []
    primary_dimension = _best_dimension(dimensions)
    primary_measure = _best_measure(measures)
    if primary_dimension is None and primary_measure is None:
        return cohorts
    if spec.kind == "receivables" and primary_measure is not None:
        cohorts.extend(
            [
                SurfaceCohort(
                    cohort_id="receivables:highest_pending",
                    surface_id=spec.kind,
                    label="Highest pending parties",
                    entity="party",
                    description="Parties with the largest pending balance and the clearest follow-up value.",
                    filter_refs=[primary_dimension.dimension_id] if primary_dimension else [],
                    measure_refs=[primary_measure.measure_id],
                    dimension_refs=[primary_dimension.dimension_id] if primary_dimension else [],
                    size_hint="computed at execution time",
                    value_hint="ranked by pending amount",
                    actionability=0.93,
                    why="High pending balances are directly monetizable if the follow-up is correct.",
                ),
                SurfaceCohort(
                    cohort_id="receivables:long_tail_pending",
                    surface_id=spec.kind,
                    label="Long-tail receivables",
                    entity="party",
                    description="Many smaller pending balances that may add up to a meaningful collection run.",
                    measure_refs=[primary_measure.measure_id],
                    dimension_refs=[primary_dimension.dimension_id] if primary_dimension else [],
                    size_hint="computed at execution time",
                    value_hint="tail contribution",
                    actionability=0.82,
                    why="Founders usually miss the long tail because every individual row looks small.",
                ),
            ]
        )
    elif spec.kind == "inventory" and primary_measure is not None:
        cohorts.append(
            SurfaceCohort(
                cohort_id="inventory:low_stock",
                surface_id=spec.kind,
                label="Low-stock items",
                entity="product",
                description="Products or items whose available quantity is low enough to require review.",
                measure_refs=[primary_measure.measure_id],
                dimension_refs=[primary_dimension.dimension_id] if primary_dimension else [],
                size_hint="computed at execution time",
                value_hint="quantity threshold or lowest rank",
                actionability=0.88,
                why="Low-stock cohorts prevent revenue loss when demand still exists.",
            )
        )
    elif spec.kind in {"sales", "customers_parties"} and primary_dimension is not None:
        cohorts.append(
            SurfaceCohort(
                cohort_id=f"{spec.kind}:high_value_entities",
                surface_id=spec.kind,
                label="High-value entities",
                entity=spec.entity,
                description="Customers, parties, products, or channels that explain a large share of value.",
                measure_refs=[primary_measure.measure_id] if primary_measure else [],
                dimension_refs=[primary_dimension.dimension_id],
                size_hint="computed at execution time",
                value_hint="ranked value contribution",
                actionability=0.8,
                why="High-value cohorts anchor sales and relationship decisions around the biggest contributors.",
            )
        )
    elif spec.kind in {"expenses", "profit_loss"} and primary_measure is not None:
        cohorts.append(
            SurfaceCohort(
                cohort_id=f"{spec.kind}:largest_outflows",
                surface_id=spec.kind,
                label="Largest outflow drivers",
                entity=spec.entity,
                description="Expense heads, parties, or items that explain most cost pressure.",
                measure_refs=[primary_measure.measure_id],
                dimension_refs=[primary_dimension.dimension_id] if primary_dimension else [],
                size_hint="computed at execution time",
                value_hint="ranked by cost or expense",
                actionability=0.76,
                why="Cost concentration is the fastest path to a useful P&L conversation.",
            )
        )
    elif spec.kind == "operations" and primary_dimension is not None:
        cohorts.append(
            SurfaceCohort(
                cohort_id="operations:repeating_statuses",
                surface_id=spec.kind,
                label="Repeating operational statuses",
                entity=spec.entity,
                description="Statuses or process states that repeat enough to become a queue.",
                dimension_refs=[primary_dimension.dimension_id],
                size_hint="computed at execution time",
                value_hint="count by status",
                actionability=0.7,
                why="Repeated statuses are where operational follow-up becomes systematic instead of ad hoc.",
            )
        )
    if graph_refs and primary_dimension is not None:
        cohorts.append(
            SurfaceCohort(
                cohort_id=f"{spec.kind}:cross_source_gap",
                surface_id=spec.kind,
                label="Cross-source gap cohort",
                entity=spec.entity,
                description="Records that look important in one source but missing, weak, or different in another.",
                dimension_refs=[primary_dimension.dimension_id],
                measure_refs=[primary_measure.measure_id] if primary_measure else [],
                size_hint="computed at execution time",
                value_hint="relationship gap",
                actionability=0.84,
                why="Cross-source gaps are where connected data becomes more valuable than any single dashboard.",
            )
        )
    return _dedupe_cohorts(cohorts)


def _action_packs(
    spec: _SurfaceSpec,
    dimensions: list[SurfaceDimension],
    measures: list[SurfaceMeasure],
    cohorts: list[SurfaceCohort],
    graph_refs: list[str],
    fields: list[dict[str, Any]],
) -> list[BulkActionPack]:
    if spec.kind == "data_quality":
        return []
    action_packs: list[BulkActionPack] = []
    has_contact_field = any(_matches(_field_blob(field), ("email", "phone", "mobile", "contact")) for field in fields)
    contactable = has_contact_field or any(dimension.kind in {"party", "customer"} for dimension in dimensions)
    for cohort in cohorts[:4]:
        action_packs.append(
            BulkActionPack(
                action_pack_id=f"{cohort.cohort_id}:save",
                surface_id=spec.kind,
                title=f"Save cohort: {cohort.label}",
                action_type="save_cohort",
                target_entity=cohort.entity or spec.entity,
                cohort_refs=[cohort.cohort_id],
                evidence_refs=graph_refs,
                payload_template={
                    "cohort_id": cohort.cohort_id,
                    "surface_id": spec.kind,
                    "measure_refs": cohort.measure_refs,
                    "dimension_refs": cohort.dimension_refs,
                },
                why="Saving the cohort makes this operating slice reusable in Brief, Inbox, and Ask.",
                approval_required="User confirms the cohort name and scope.",
                risk="Low; no external system is changed.",
                priority=cohort.actionability,
            )
        )
        action_packs.append(
            BulkActionPack(
                action_pack_id=f"{cohort.cohort_id}:export",
                surface_id=spec.kind,
                title=f"Export list: {cohort.label}",
                action_type="export_list",
                target_entity=cohort.entity or spec.entity,
                cohort_refs=[cohort.cohort_id],
                evidence_refs=graph_refs,
                payload_template={
                    "cohort_id": cohort.cohort_id,
                    "surface_id": spec.kind,
                    "include_fields": _field_ids(dimensions[:4], measures[:3]),
                },
                why="Exporting the list turns the insight into a practical working queue.",
                approval_required="User confirms export columns and row scope.",
                risk="Medium; exported business data must be handled carefully.",
                priority=max(0.55, cohort.actionability - 0.05),
            )
        )
        if contactable and spec.kind in {"receivables", "customers_parties", "sales"}:
            action_packs.append(
                BulkActionPack(
                    action_pack_id=f"{cohort.cohort_id}:email",
                    surface_id=spec.kind,
                    title=f"Draft emails: {cohort.label}",
                    action_type="email_draft",
                    target_entity=cohort.entity or spec.entity,
                    cohort_refs=[cohort.cohort_id],
                    evidence_refs=graph_refs,
                    payload_template={
                        "cohort_id": cohort.cohort_id,
                        "surface_id": spec.kind,
                        "tone": "polite",
                        "personalization_fields": _field_ids(dimensions[:4], measures[:2]),
                        "send_mode": "draft_only",
                    },
                    why=(
                        "This cohort is contactable and has a business reason for follow-up, "
                        "so Baseflo can prepare bulk drafts without sending anything."
                    ),
                    approval_required="User reviews the draft template and selected recipients before any send.",
                    risk="Medium; messaging frequency and recipient accuracy must be reviewed.",
                    priority=cohort.actionability,
                )
            )
    return _dedupe_actions(action_packs)


def _connected_surface(
    field_roles: list[dict[str, Any]],
    asset_roles: list[dict[str, Any]],
    executions: list[dict[str, Any]],
) -> BusinessSurface:
    spec = _surface_spec("connected_data")
    fields = field_roles[:20]
    return _surface(
        spec=spec,
        title="Connected Data Workbench",
        description="A neutral operating surface over connected canonical data.",
        why_built="Because data is connected but business-specific surfaces need more semantic evidence.",
        fields=fields,
        assets=asset_roles,
        graph_refs=[_text(execution.get("graph_id")) for execution in executions],
        executions=executions,
        confidence=0.5,
    )


def _build_insight_graph(surfaces: list[BusinessSurface]) -> InsightGraph:
    nodes: list[InsightGraphNode] = []
    edges: list[InsightGraphEdge] = []
    for surface in surfaces:
        surface_node = f"surface:{surface.surface_id}"
        nodes.append(
            InsightGraphNode(
                node_id=surface_node,
                node_type="surface",
                label=surface.title,
                refs={"surface_id": surface.surface_id, "kind": surface.kind},
            )
        )
        if surface.entity:
            entity_node = f"entity:{surface.entity}"
            nodes.append(
                InsightGraphNode(
                    node_id=entity_node,
                    node_type="entity",
                    label=surface.entity,
                    refs={"entity": surface.entity},
                )
            )
            edges.append(
                InsightGraphEdge(
                    left_node_id=surface_node,
                    right_node_id=entity_node,
                    relationship="targets",
                    why=f"{surface.title} is organized around {surface.entity}.",
                    confidence=0.8,
                )
            )
        for measure in surface.measures:
            measure_node = f"measure:{measure.measure_id}"
            nodes.append(
                InsightGraphNode(
                    node_id=measure_node,
                    node_type="measure",
                    label=measure.label,
                    refs={"field_id": measure.field_id, "asset_id": measure.asset_id},
                )
            )
            edges.append(
                InsightGraphEdge(
                    left_node_id=surface_node,
                    right_node_id=measure_node,
                    relationship="uses",
                    why=f"{surface.title} uses {measure.label} as a measure.",
                    confidence=measure.confidence,
                )
            )
        for dimension in surface.dimensions:
            dimension_node = f"dimension:{dimension.dimension_id}"
            nodes.append(
                InsightGraphNode(
                    node_id=dimension_node,
                    node_type="dimension",
                    label=dimension.label,
                    refs={"field_id": dimension.field_id, "asset_id": dimension.asset_id},
                )
            )
            edges.append(
                InsightGraphEdge(
                    left_node_id=surface_node,
                    right_node_id=dimension_node,
                    relationship="drills_into",
                    why=f"{dimension.label} can slice {surface.title}.",
                    confidence=dimension.confidence,
                )
            )
        for graph_ref in surface.graph_refs:
            evidence_node = f"evidence:{graph_ref}"
            nodes.append(
                InsightGraphNode(
                    node_id=evidence_node,
                    node_type="evidence",
                    label=graph_ref,
                    refs={"graph_id": graph_ref},
                )
            )
            edges.append(
                InsightGraphEdge(
                    left_node_id=evidence_node,
                    right_node_id=surface_node,
                    relationship="supports",
                    why=f"{graph_ref} materializes evidence for {surface.title}.",
                    confidence=0.75,
                )
            )
        for view in surface.candidate_views:
            view_node = f"candidate:{view.view_id}"
            nodes.append(
                InsightGraphNode(
                    node_id=view_node,
                    node_type="candidate_view",
                    label=view.title,
                    refs={"view_id": view.view_id, "algorithm": view.algorithm},
                )
            )
            edges.append(
                InsightGraphEdge(
                    left_node_id=surface_node,
                    right_node_id=view_node,
                    relationship="contains",
                    why=view.why,
                    confidence=view.priority,
                )
            )
            for ref in view.measures:
                edges.append(
                    InsightGraphEdge(
                        left_node_id=view_node,
                        right_node_id=f"measure:{ref}",
                        relationship="uses",
                        why=f"{view.title} uses this measure.",
                        confidence=0.75,
                    )
                )
            for ref in view.dimensions:
                edges.append(
                    InsightGraphEdge(
                        left_node_id=view_node,
                        right_node_id=f"dimension:{ref}",
                        relationship="uses",
                        why=f"{view.title} uses this dimension.",
                        confidence=0.75,
                    )
                )
        for cohort in surface.cohorts:
            cohort_node = f"cohort:{cohort.cohort_id}"
            nodes.append(
                InsightGraphNode(
                    node_id=cohort_node,
                    node_type="cohort",
                    label=cohort.label,
                    refs={"cohort_id": cohort.cohort_id, "surface_id": surface.surface_id},
                )
            )
            edges.append(
                InsightGraphEdge(
                    left_node_id=surface_node,
                    right_node_id=cohort_node,
                    relationship="contains",
                    why=cohort.why,
                    confidence=cohort.actionability,
                )
            )
        for action in surface.action_packs:
            action_node = f"action_pack:{action.action_pack_id}"
            nodes.append(
                InsightGraphNode(
                    node_id=action_node,
                    node_type="action_pack",
                    label=action.title,
                    refs={"action_pack_id": action.action_pack_id, "action_type": action.action_type},
                )
            )
            edges.append(
                InsightGraphEdge(
                    left_node_id=surface_node,
                    right_node_id=action_node,
                    relationship="can_trigger",
                    why=action.why,
                    confidence=action.priority,
                )
            )
            for cohort_ref in action.cohort_refs:
                edges.append(
                    InsightGraphEdge(
                        left_node_id=action_node,
                        right_node_id=f"cohort:{cohort_ref}",
                        relationship="targets",
                        why=f"{action.title} acts on {cohort_ref}.",
                        confidence=action.priority,
                    )
                )
    return InsightGraph(nodes=_dedupe_nodes(nodes), edges=_dedupe_edges(edges))


def _graphs_by_refs_or_terms(
    *,
    executions: list[dict[str, Any]],
    patterns: dict[str, Any],
    graph_refs: list[str],
    terms: tuple[str, ...],
) -> list[dict[str, Any]]:
    refs = set(graph_refs)
    hypothesis_by_id = {
        _text(hypothesis.get("hypothesis_id")): hypothesis
        for hypothesis in _record_list(patterns.get("hypotheses"))
    }
    matches: list[dict[str, Any]] = []
    for execution in executions:
        graph_id = _text(execution.get("graph_id"))
        hypothesis = hypothesis_by_id.get(_text(execution.get("hypothesis_id")), {})
        if graph_id in refs or _matches(f"{execution} {hypothesis}".lower(), terms):
            matches.append(execution)
    return matches


def _best_dimension(dimensions: list[SurfaceDimension]) -> SurfaceDimension | None:
    if not dimensions:
        return None
    order = {"party": 0, "customer": 1, "product": 2, "item": 3, "category": 4, "status": 5, "time": 6}
    return sorted(dimensions, key=lambda dimension: (order.get(dimension.kind, 20), -dimension.confidence))[0]


def _best_measure(measures: list[SurfaceMeasure]) -> SurfaceMeasure | None:
    if not measures:
        return None
    order = {
        "pending_amount": 0,
        "revenue": 1,
        "bill_amount": 2,
        "amount": 3,
        "inventory": 4,
        "quantity": 5,
        "cost": 6,
        "expense": 7,
    }
    return sorted(measures, key=lambda measure: (order.get(measure.kind, 20), -measure.confidence))[0]


def _time_dimensions(dimensions: list[SurfaceDimension]) -> list[SurfaceDimension]:
    return [dimension for dimension in dimensions if dimension.kind == "time"]


def _dimension_kind(blob: str, role: str) -> DimensionKind:
    if "email" in blob:
        return "customer"
    if any(term in blob for term in ("party", "vendor", "supplier", "account")):
        return "party"
    if "customer" in blob:
        return "customer"
    if any(term in blob for term in ("product", "sku", "variant")):
        return "product"
    if any(term in blob for term in ("item", "article", "style")):
        return "item"
    if any(term in blob for term in ("date", "time", "created", "month", "year")) or role == "timestamp":
        return "time"
    if "status" in blob or role == "status":
        return "status"
    if any(term in blob for term in ("city", "state", "country", "location", "warehouse")):
        return "location"
    if any(term in blob for term in ("category", "head", "type")):
        return "category"
    if any(term in blob for term in ("channel", "source", "platform")):
        return "channel"
    if role in {"primary_key", "foreign_key", "identifier", "label"}:
        return "entity"
    return "unknown"


def _measure_kind(blob: str) -> MeasureKind:
    if any(term in blob for term in ("pending", "balance", "outstanding", "due")):
        return "pending_amount"
    if "bill" in blob or "invoice" in blob:
        return "bill_amount"
    if any(term in blob for term in ("revenue", "sale", "sales", "order_total")):
        return "revenue"
    if "expense" in blob:
        return "expense"
    if any(term in blob for term in ("cost", "spend", "paid", "payment", "debit")):
        return "cost"
    if any(term in blob for term in ("stock", "inventory", "available")):
        return "inventory"
    if any(term in blob for term in ("qty", "quantity", "units")):
        return "quantity"
    if any(term in blob for term in ("rate", "percent", "ratio")):
        return "rate"
    if "count" in blob or "orders" in blob:
        return "count"
    if any(term in blob for term in ("amount", "amt", "total", "value")):
        return "amount"
    return "unknown"


def _default_aggregate(kind: str, blob: str) -> AggregateKind:
    if kind == "rate" or "avg" in blob or "average" in blob:
        return "avg"
    if kind == "count":
        return "count"
    return "sum"


def _field_label(field: dict[str, Any]) -> str:
    return _humanize(
        _text(
            field.get("measure_kind"),
            _text(field.get("semantic_type"), _text(field.get("field_name"), _text(field.get("field_id")))),
        )
    )


def _field_blob(field: dict[str, Any]) -> str:
    return " ".join(
        _text(field.get(key))
        for key in ("field_id", "field_name", "semantic_type", "role", "measure_kind", "entity_hint", "why")
    ).lower()


def _field_meaning_blob(field: dict[str, Any]) -> str:
    return " ".join(
        _text(field.get(key))
        for key in ("field_name", "semantic_type", "role", "measure_kind", "entity_hint", "why")
    ).lower()


def _asset_blob(asset: dict[str, Any]) -> str:
    return " ".join(
        [
            *[_text(asset.get(key)) for key in ("asset_id", "role", "entity_type", "label", "why")],
            *[str(tag) for tag in _list(asset.get("tags"))],
        ]
    ).lower()


def _why_from_evidence(spec: _SurfaceSpec, fields: list[dict[str, Any]]) -> str:
    names = _unique(_field_label(field) for field in fields[:6])
    if names:
        return f"Because this data has {', '.join(names)}, Baseflo built {spec.title}."
    return f"Because this data contains {spec.title.replace(' Workbench', '').lower()} signals, Baseflo built {spec.title}."


def _surface_confidence(
    fields: list[dict[str, Any]],
    assets: list[dict[str, Any]],
    graphs: list[dict[str, Any]],
) -> float:
    score = 0.42
    if fields:
        score += 0.22
    if assets:
        score += 0.16
    if graphs:
        score += 0.14
    return min(score, 0.94)


def _package_confidence(surfaces: list[BusinessSurface]) -> float:
    if not surfaces:
        return 0.0
    return round(sum(surface.confidence for surface in surfaces) / len(surfaces), 2)


def _algorithms(surfaces: list[BusinessSurface]) -> list[MiningAlgorithm]:
    algorithms: list[str] = ["semantic_surface_detection"]
    for surface in surfaces:
        algorithms.extend(view.algorithm for view in surface.candidate_views)
    return _unique(algorithms)  # type: ignore[return-value]


def _surface_spec(kind: SurfaceKind) -> _SurfaceSpec:
    if kind == "connected_data":
        return _SurfaceSpec(
            kind="connected_data",
            title="Connected Data Workbench",
            description="A neutral surface over connected canonical assets.",
            entity=None,
            terms=("data", "source", "asset", "field"),
            measure_terms=("count", "row"),
            dimension_terms=("asset", "field", "source"),
        )
    return _SPEC_BY_KIND[kind]


def _surface_kind(value: str) -> SurfaceKind | None:
    allowed = {
        "sales",
        "receivables",
        "inventory",
        "customers_parties",
        "products_items",
        "expenses",
        "profit_loss",
        "operations",
        "data_quality",
        "connected_data",
    }
    return value if value in allowed else None  # type: ignore[return-value]


def _stable_id(prefix: str, value: str) -> str:
    clean = value.lower().replace(".", "_").replace(" ", "_").replace("-", "_")
    return f"{prefix}:{clean}"


def _field_ids(dimensions: list[SurfaceDimension], measures: list[SurfaceMeasure]) -> list[str]:
    return _unique([*[dimension.field_id for dimension in dimensions], *[measure.field_id for measure in measures]])


def _dedupe_surfaces(surfaces: list[BusinessSurface]) -> list[BusinessSurface]:
    by_id: dict[str, BusinessSurface] = {}
    for surface in surfaces:
        existing = by_id.get(surface.surface_id)
        if existing is None or surface.confidence > existing.confidence:
            by_id[surface.surface_id] = surface
    return sorted(by_id.values(), key=lambda surface: _surface_order(surface.kind))


def _dedupe_dimensions(dimensions: list[SurfaceDimension]) -> list[SurfaceDimension]:
    by_id: dict[str, SurfaceDimension] = {}
    for dimension in dimensions:
        by_id[dimension.dimension_id] = dimension
    return list(by_id.values())[:12]


def _dedupe_measures(measures: list[SurfaceMeasure]) -> list[SurfaceMeasure]:
    by_id: dict[str, SurfaceMeasure] = {}
    for measure in measures:
        by_id[measure.measure_id] = measure
    return list(by_id.values())[:10]


def _dedupe_views(views: list[CandidateView]) -> list[CandidateView]:
    by_id: dict[str, CandidateView] = {}
    for view in views:
        by_id[view.view_id] = view
    return sorted(by_id.values(), key=lambda view: view.priority, reverse=True)[:8]


def _dedupe_cohorts(cohorts: list[SurfaceCohort]) -> list[SurfaceCohort]:
    by_id: dict[str, SurfaceCohort] = {}
    for cohort in cohorts:
        by_id[cohort.cohort_id] = cohort
    return sorted(by_id.values(), key=lambda cohort: cohort.actionability, reverse=True)[:6]


def _dedupe_actions(actions: list[BulkActionPack]) -> list[BulkActionPack]:
    by_id: dict[str, BulkActionPack] = {}
    for action in actions:
        by_id[action.action_pack_id] = action
    return sorted(by_id.values(), key=lambda action: action.priority, reverse=True)[:10]


def _dedupe_nodes(nodes: list[InsightGraphNode]) -> list[InsightGraphNode]:
    by_id: dict[str, InsightGraphNode] = {}
    for node in nodes:
        by_id[node.node_id] = node
    return list(by_id.values())


def _dedupe_edges(edges: list[InsightGraphEdge]) -> list[InsightGraphEdge]:
    by_key: dict[tuple[str, str, str], InsightGraphEdge] = {}
    for edge in edges:
        by_key[(edge.left_node_id, edge.right_node_id, edge.relationship)] = edge
    return list(by_key.values())


def _surface_order(kind: str) -> int:
    order = {
        "sales": 10,
        "receivables": 20,
        "profit_loss": 30,
        "inventory": 40,
        "customers_parties": 50,
        "products_items": 60,
        "expenses": 70,
        "operations": 80,
        "data_quality": 90,
        "connected_data": 100,
    }
    return order.get(kind, 999)


def _matches(blob: str, terms: tuple[str, ...]) -> bool:
    return any(term.lower() in blob for term in terms)


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


def _int(value: Any, fallback: int = 0) -> int:
    return value if isinstance(value, int) else fallback


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


def _humanize(value: str) -> str:
    return value.replace("_", " ").replace("-", " ").title() if value else "Unknown"
