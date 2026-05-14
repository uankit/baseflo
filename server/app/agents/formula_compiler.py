"""FormulaCompiler - deterministic FormulaSpec -> AnalysisGraph.

Team agents speak in business fields: "customer.email", "order.total_price",
"transaction.amount". This compiler is the boundary that resolves those field
refs against the validated business graph, plans any required multi-hop joins,
and emits an AnalysisGraph with stable internal aliases.
"""

from __future__ import annotations

import hashlib
import json
from collections import deque
from dataclasses import dataclass
from difflib import get_close_matches
from uuid import UUID

from app.agentic import (
    AggregateMeasure,
    AggregateNode,
    AnalysisGraph,
    AnalysisNode,
    FilterNode,
    FilterPredicate,
    JoinNode,
    LimitNode,
    RankNode,
    SourceNode,
    _analysis_alias,
    _slug,
)
from app.agents._contracts import EntityGraph, FormulaFieldRef, FormulaSpec, GraphEdge
from app.db.models import OperatingAsset, OperatingColumn


class FormulaCompileError(Exception):
    pass


@dataclass(frozen=True)
class _ResolvedField:
    entity: str
    table: str
    column: str
    alias: str


@dataclass(frozen=True)
class _EntitySource:
    entity: str
    table: str
    label: str


@dataclass(frozen=True)
class _FieldCandidate:
    ref: FormulaFieldRef
    entity: str
    table: str
    column: OperatingColumn
    score: float


class _BusinessFieldRegistry:
    def __init__(
        self,
        *,
        graph: EntityGraph,
        assets: list[OperatingAsset],
        columns_by_asset: dict[UUID, list[OperatingColumn]],
    ) -> None:
        self._graph = graph
        self._asset_by_table = {asset.qualified_name: asset for asset in assets}
        self._columns_by_table: dict[str, dict[str, OperatingColumn]] = {}
        for asset in assets:
            self._columns_by_table[asset.qualified_name] = {
                column.name: column for column in columns_by_asset.get(asset.id, [])
            }
        self._sources: dict[str, _EntitySource] = {
            node.entity: _EntitySource(
                entity=node.entity,
                table=node.asset_qualified_name,
                label=node.label,
            )
            for node in graph.nodes
        }
        self._surface_tables_by_entity: dict[str, set[str]] = {
            entity: {source.table} for entity, source in self._sources.items()
        }
        for edge in graph.edges:
            self._surface_tables_by_entity.setdefault(edge.left_entity, set()).add(edge.left_table)
            self._surface_tables_by_entity.setdefault(edge.right_entity, set()).add(edge.right_table)

    @property
    def entities(self) -> list[str]:
        return sorted(self._sources)

    def require_entity(self, entity: str, *, purpose: str) -> _EntitySource:
        if entity in self._sources:
            return self._sources[entity]
        suffix = _candidate_suffix(entity, self.entities)
        raise FormulaCompileError(f"Unknown {purpose} entity '{entity}'.{suffix}")

    def resolve_field(self, ref: FormulaFieldRef, *, purpose: str) -> _ResolvedField:
        source = self.require_entity(ref.entity, purpose=purpose)
        candidate_tables = sorted(self._surface_tables_by_entity.get(ref.entity, {source.table}))
        if ref.surface_table:
            if ref.surface_table not in candidate_tables:
                suffix = _candidate_suffix(ref.surface_table, candidate_tables)
                raise FormulaCompileError(
                    f"Unknown {purpose} surface '{ref.surface_table}' for entity '{ref.entity}'.{suffix}"
                )
            candidate_tables = [ref.surface_table]
        else:
            # Prefer the entity's primary asset, then any relationship surface.
            candidate_tables = [
                source.table,
                *[table for table in candidate_tables if table != source.table],
            ]
        for table in candidate_tables:
            columns = self._columns_by_table.get(table, {})
            if ref.field in columns:
                return _ResolvedField(
                    entity=ref.entity,
                    table=table,
                    column=ref.field,
                    alias=_analysis_alias(ref.entity, ref.field),
                )
        all_columns = sorted({
            column
            for table in candidate_tables
            for column in self._columns_by_table.get(table, {})
        })
        if ref.field not in all_columns:
            suffix = _candidate_suffix(ref.field, all_columns)
            raise FormulaCompileError(
                f"Unknown {purpose} field '{ref.entity}.{ref.field}'.{suffix}"
            )
        raise FormulaCompileError(
            f"Ambiguous {purpose} field '{ref.entity}.{ref.field}'. "
            "Use the field catalog ref with surface_table."
        )

    def field_catalog(self) -> list[dict[str, object]]:
        catalog: list[dict[str, object]] = []
        for entity in self.entities:
            source = self._sources[entity]
            for table in sorted(self._surface_tables_by_entity.get(entity, {source.table})):
                for column in sorted(self._columns_by_table.get(table, {}).values(), key=lambda c: c.name):
                    catalog.append({
                        "entity": entity,
                        "field": column.name,
                        "surface_table": table,
                        "label": source.label,
                        "observed_type": column.observed_type,
                        "semantic_type": column.semantic_type,
                        "null_rate": column.null_rate,
                        "unique_count": column.unique_count,
                        "sample_values": (column.sample_values or [])[:5],
                        "ref": {"entity": entity, "field": column.name, "surface_table": table},
                    })
        return catalog

    def require_known_table(self, table: str, *, entity: str) -> None:
        if table in self._columns_by_table:
            return
        raise FormulaCompileError(
            f"Entity '{entity}' references unknown table surface '{table}'."
        )

    def candidate_measure_fields(self, spec: FormulaSpec, measure_index: int) -> list[_FieldCandidate]:
        measure = spec.measures[measure_index]
        search_text = " ".join(
            [
                spec.formula_id,
                spec.title,
                spec.why,
                spec.expected_shape,
                spec.target_entity,
                spec.group_by_field.entity,
                spec.group_by_field.field,
                measure.alias,
                measure.aggregate,
            ]
        ).lower()
        candidates: list[_FieldCandidate] = []
        for entity in self.entities:
            try:
                _find_path(spec.target_entity, entity, self._graph)
            except FormulaCompileError:
                continue
            for table in sorted(self._surface_tables_by_entity.get(entity, [])):
                for column in self._columns_by_table.get(table, {}).values():
                    score = _measure_field_score(
                        column,
                        entity=entity,
                        table=table,
                        spec=spec,
                        aggregate=measure.aggregate,
                        search_text=search_text,
                    )
                    if score > 0:
                        candidates.append(
                            _FieldCandidate(
                                ref=FormulaFieldRef(entity=entity, field=column.name, surface_table=table),
                                entity=entity,
                                table=table,
                                column=column,
                                score=score,
                            )
                        )
        return sorted(candidates, key=lambda c: c.score, reverse=True)


def _safe_id(value: str) -> str:
    return _slug(value)


def _candidate_suffix(value: str, candidates: list[str]) -> str:
    matches = get_close_matches(value, candidates, n=6)
    shown = list(dict.fromkeys([*matches, *candidates[:8]]))
    if not shown:
        return ""
    return " Candidates: " + ", ".join(shown) + "."


def _field_tokens(value: str) -> set[str]:
    normalized = "".join(ch.lower() if ch.isalnum() else " " for ch in value)
    return {part for part in normalized.split() if part}


def _looks_numeric(column: OperatingColumn) -> bool:
    text = f"{column.name} {column.observed_type} {column.semantic_type}".lower()
    numeric_markers = (
        "number", "numeric", "integer", "int", "float", "double", "decimal",
        "money", "measure", "amount", "price", "total", "subtotal", "spent",
        "revenue", "sales", "quantity", "count", "inventory", "available",
        "rate", "percent", "tax", "discount", "value",
    )
    if any(marker in text for marker in numeric_markers):
        return True
    samples = column.sample_values or []
    if not samples:
        return False
    numeric_samples = 0
    for sample in samples[:5]:
        try:
            float(str(sample).replace(",", ""))
        except (TypeError, ValueError):
            continue
        numeric_samples += 1
    return numeric_samples >= max(1, min(3, len(samples[:5])))


def _measure_field_score(
    column: OperatingColumn,
    *,
    entity: str,
    table: str,
    spec: FormulaSpec,
    aggregate: str,
    search_text: str,
) -> float:
    name = column.name.lower()
    table_text = table.lower()
    descriptor = f"{name} {table_text} {entity.lower()} {column.observed_type} {column.semantic_type}".lower()
    if aggregate in {"sum", "avg", "min", "max"} and not _looks_numeric(column):
        return -1

    score = 0.0
    if _looks_numeric(column):
        score += 4
    if entity == spec.target_entity:
        score += 2
    if entity == spec.group_by_field.entity:
        score += 1
    if "id" == name or name.endswith("_id") or "gid" in name:
        score -= 7

    query_tokens = _field_tokens(search_text)
    field_tokens = _field_tokens(f"{column.name} {table} {entity}")
    score += len(query_tokens & field_tokens) * 2

    money_intent = (
        "spend", "spent", "revenue", "sales", "sale", "aov", "value",
        "amount", "price", "ltv", "gmv", "order value",
    )
    money_fields = (
        "total_spent", "total_price", "subtotal_price", "amount", "price",
        "current_total_price", "value", "revenue", "spent",
    )
    if any(term in search_text for term in money_intent) and any(term in descriptor for term in money_fields):
        score += 9

    count_intent = ("orders", "order count", "frequency", "count", "volume")
    count_fields = ("orders_count", "order_count", "count", "quantity", "line_items_quantity")
    if any(term in search_text for term in count_intent) and any(term in descriptor for term in count_fields):
        score += 7

    stock_intent = ("stock", "inventory", "cover", "available", "reorder", "capacity")
    stock_fields = ("inventory", "available", "quantity", "stock", "on_hand")
    if any(term in search_text for term in stock_intent) and any(term in descriptor for term in stock_fields):
        score += 8

    engagement_intent = ("engagement", "campaign", "email", "open", "click", "audience", "marketing")
    engagement_fields = ("engagement", "open", "click", "email", "orders_count", "total_spent", "quantity")
    if any(term in search_text for term in engagement_intent) and any(term in descriptor for term in engagement_fields):
        score += 5

    if aggregate == "avg" and any(term in descriptor for term in ("price", "amount", "spent", "value")):
        score += 5
    if aggregate == "sum" and any(term in descriptor for term in ("price", "amount", "spent", "quantity", "count", "inventory")):
        score += 3

    return score


def _ground_missing_measure_fields(spec: FormulaSpec, registry: _BusinessFieldRegistry) -> FormulaSpec:
    measures = []
    changed = False
    for index, measure in enumerate(spec.measures):
        if measure.field is not None or measure.aggregate == "count":
            measures.append(measure)
            continue

        candidates = registry.candidate_measure_fields(spec, index)
        best = candidates[0] if candidates else None
        if best is None or best.score < 6:
            candidate_names = [
                f"{candidate.entity}.{candidate.column.name}"
                for candidate in candidates[:6]
            ]
            suffix = _candidate_suffix(measure.alias, candidate_names)
            raise FormulaCompileError(
                f"Measure {index} ({measure.aggregate}:{measure.alias}) has no field ref "
                f"and could not be grounded safely.{suffix}"
            )
        measures.append(measure.model_copy(update={"field": best.ref}))
        changed = True

    if not changed:
        return spec
    return spec.model_copy(update={"measures": measures})


def _edge_neighbors(graph: EntityGraph) -> dict[str, list[str]]:
    neighbors: dict[str, list[str]] = {}
    for edge in graph.edges:
        if not edge.validated:
            continue
        neighbors.setdefault(edge.left_entity, []).append(edge.right_entity)
        neighbors.setdefault(edge.right_entity, []).append(edge.left_entity)
    return neighbors


def _find_path(start: str, end: str, graph: EntityGraph) -> list[str]:
    if start == end:
        return [start]
    neighbors = _edge_neighbors(graph)
    queue: deque[list[str]] = deque([[start]])
    seen = {start}
    while queue:
        path = queue.popleft()
        current = path[-1]
        for nxt in sorted(neighbors.get(current, [])):
            if nxt in seen:
                continue
            next_path = [*path, nxt]
            if nxt == end:
                return next_path
            seen.add(nxt)
            queue.append(next_path)
    raise FormulaCompileError(f"No validated entity path connects '{start}' to '{end}'.")


def _edge_for_pair(left_entity: str, right_entity: str, graph: EntityGraph) -> GraphEdge:
    for edge in graph.edges:
        if not edge.validated:
            continue
        if edge.left_entity == left_entity and edge.right_entity == right_entity:
            return edge
        if edge.left_entity == right_entity and edge.right_entity == left_entity:
            return edge
    raise FormulaCompileError(f"No validated edge connects '{left_entity}' and '{right_entity}'.")


def _oriented_edge(
    left_entity: str,
    right_entity: str,
    graph: EntityGraph,
) -> tuple[str, str, str, str]:
    edge = _edge_for_pair(left_entity, right_entity, graph)
    if edge.left_entity == left_entity and edge.right_entity == right_entity:
        return edge.left_table, edge.left_key, edge.right_table, edge.right_key
    return edge.right_table, edge.right_key, edge.left_table, edge.left_key


def field_catalog_for_prompt(
    graph: EntityGraph,
    *,
    assets: list[OperatingAsset],
    columns_by_asset: dict[UUID, list[OperatingColumn]],
) -> list[dict[str, object]]:
    """Return the deterministic field refs a team agent is allowed to use."""
    return _BusinessFieldRegistry(
        graph=graph,
        assets=assets,
        columns_by_asset=columns_by_asset,
    ).field_catalog()


def compile_formula(
    spec: FormulaSpec,
    graph: EntityGraph,
    *,
    assets: list[OperatingAsset],
    columns_by_asset: dict[UUID, list[OperatingColumn]],
) -> AnalysisGraph:
    """Compile a business FormulaSpec into a runtime-ready AnalysisGraph.

    The compiler:
    - rejects unknown business entities before SQL exists;
    - resolves business field refs to real columns and stable aliases;
    - plans multi-hop joins through the validated EntityGraph;
    - emits only generic AnalysisGraph operators for AnalysisRuntime.
    """
    registry = _BusinessFieldRegistry(
        graph=graph,
        assets=assets,
        columns_by_asset=columns_by_asset,
    )
    spec = _ground_missing_measure_fields(spec, registry)
    target_source = registry.require_entity(spec.target_entity, purpose="target")
    group_by = registry.resolve_field(spec.group_by_field, purpose="group_by")

    filter_fields = [
        registry.resolve_field(filter_.field, purpose="filter")
        for filter_ in spec.filters
    ]
    measure_fields = [
        registry.resolve_field(measure.field, purpose="measure")
        for measure in spec.measures
        if measure.field is not None
    ]
    for i, measure in enumerate(spec.measures):
        if measure.aggregate != "count" and measure.field is None:
            raise FormulaCompileError(
                f"Measure {i} uses aggregate '{measure.aggregate}' but has no field ref."
            )

    required_entities = {
        group_by.entity,
        *[field.entity for field in filter_fields],
        *[field.entity for field in measure_fields],
    }
    for entity in required_entities:
        registry.require_entity(entity, purpose="formula")

    nodes: list[AnalysisNode] = []
    next_id = 0

    def issue_id(stem: str) -> str:
        nonlocal next_id
        next_id += 1
        return f"{_safe_id(stem)}_{next_id}"

    source_id = issue_id(f"src_{spec.target_entity}")
    nodes.append(SourceNode(id=source_id, table=target_source.table, namespace=spec.target_entity))
    current = source_id
    joined_entities = {spec.target_entity}
    join_lineage: list[dict[str, str]] = []

    def ensure_entity_joined(entity: str) -> None:
        nonlocal current
        if entity in joined_entities:
            return
        path = _find_path(spec.target_entity, entity, graph)
        previous = path[0]
        for nxt in path[1:]:
            if nxt in joined_entities:
                previous = nxt
                continue
            left_table, left_key, right_table, right_key = _oriented_edge(previous, nxt, graph)
            registry.require_entity(previous, purpose="join")
            registry.require_entity(nxt, purpose="join")
            registry.require_known_table(left_table, entity=previous)
            registry.require_known_table(right_table, entity=nxt)
            right_source_id = issue_id(f"src_{nxt}")
            nodes.append(SourceNode(id=right_source_id, table=right_table, namespace=nxt))
            join_id = issue_id(f"join_{previous}_{nxt}")
            nodes.append(JoinNode(
                id=join_id,
                left_input=current,
                right_input=right_source_id,
                left_key=_analysis_alias(previous, left_key),
                right_key=_analysis_alias(nxt, right_key),
                join_kind="inner",
            ))
            current = join_id
            joined_entities.add(nxt)
            join_lineage.append({
                "left_entity": previous,
                "left_table": left_table,
                "left_key": left_key,
                "right_entity": nxt,
                "right_table": right_table,
                "right_key": right_key,
            })
            previous = nxt

    for entity in sorted(required_entities):
        ensure_entity_joined(entity)

    if spec.filters:
        filter_id = issue_id("filter")
        nodes.append(FilterNode(
            id=filter_id,
            input=current,
            predicates=[
                FilterPredicate(
                    column=field.alias,
                    operator=filter_.operator,
                    value=filter_.value,
                )
                for filter_, field in zip(spec.filters, filter_fields, strict=True)
            ],
        ))
        current = filter_id

    aggregate_id = issue_id("aggregate")
    nodes.append(AggregateNode(
        id=aggregate_id,
        input=current,
        group_by=[group_by.alias],
        measures=[
            AggregateMeasure(
                function=measure.aggregate,
                column=None if measure.field is None else field.alias,
                alias=_safe_id(measure.alias) or f"value_{i}",
            )
            for i, (measure, field) in enumerate(_zip_measures(spec, measure_fields))
        ],
    ))
    current = aggregate_id

    order_by_alias = spec.order_by_alias or (spec.measures[0].alias if spec.measures else None)
    if order_by_alias is None:
        raise FormulaCompileError("FormulaSpec needs at least one measure for ranking.")
    rank_id = issue_id("rank")
    nodes.append(RankNode(
        id=rank_id,
        input=current,
        order_by=_safe_id(order_by_alias),
        direction=spec.direction,
        alias="signal_rank",
    ))
    current = rank_id

    limit_id = issue_id("limit")
    nodes.append(LimitNode(id=limit_id, input=current, limit=spec.limit))
    current = limit_id

    graph_seed = json.dumps(
        {"team": spec.team_id, "formula": spec.formula_id, "entity": spec.target_entity},
        sort_keys=True,
    )
    graph_id = hashlib.sha256(graph_seed.encode()).hexdigest()[:16]

    return AnalysisGraph(
        graph_id=graph_id,
        hypothesis_type=f"{spec.team_id}__{spec.formula_id}"[:60],
        nodes=nodes,
        output_node=current,
        lineage=[
            {
                "team": spec.team_id,
                "formula_id": spec.formula_id,
                "target_entity": spec.target_entity,
            },
            {
                "group_by_entity": group_by.entity,
                "group_by_field": group_by.column,
                "group_by_alias": group_by.alias,
            },
            *[
                {
                    "measure_entity": field.entity,
                    "measure_field": field.column,
                    "measure_alias": _safe_id(measure.alias),
                }
                for measure, field in _zip_measures(spec, measure_fields)
                if field is not None
            ],
            *join_lineage,
        ],
        why=spec.why,
    )


def _zip_measures(
    spec: FormulaSpec,
    resolved_fields: list[_ResolvedField],
) -> list[tuple[object, _ResolvedField | None]]:
    """Pair measures with resolved fields while preserving count(*) gaps."""
    pairs: list[tuple[object, _ResolvedField | None]] = []
    field_iter = iter(resolved_fields)
    for measure in spec.measures:
        pairs.append((measure, None if measure.field is None else next(field_iter)))
    return pairs
