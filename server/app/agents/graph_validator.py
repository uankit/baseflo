"""GraphValidator — Phase 4, deterministic edge verification.

Takes each edge the RelationshipMapper proposed and runs a tiny SQL probe
to check that the join actually produces rows. Edges that don't materialize
are dropped (and the reason is logged on the EntityGraph notes).

Pure runtime. No agent calls. No semantics. Just SQL.
"""

from __future__ import annotations

import asyncio
import logging
from uuid import UUID

from app.agentic import _quote_ident
from app.agents._contracts import EntityGraph, GraphEdge, GraphNode
from app.substrate import safe_query

logger = logging.getLogger("baseflo.agents.graph_validator")

_VALIDATION_LIMIT = 1


async def _probe_edge(org_id: UUID, edge: GraphEdge) -> bool:
    """Return True if at least one row joins on the proposed keys."""
    sql = (
        f"SELECT 1 AS hit FROM {_quote_ident(edge.left_table)} AS lhs "
        f"INNER JOIN {_quote_ident(edge.right_table)} AS rhs "
        f"ON lhs.{_quote_ident(edge.left_key)} = rhs.{_quote_ident(edge.right_key)} "
        f"LIMIT {_VALIDATION_LIMIT}"
    )
    try:
        rows = await asyncio.to_thread(safe_query, org_id, sql, max_rows=_VALIDATION_LIMIT)
        return bool(rows)
    except Exception as exc:
        logger.warning("graph edge probe failed for %s↔%s: %s", edge.left_table, edge.right_table, exc)
        return False


def _allowed_entities_from_business_model(business_model: dict | None) -> set[str] | None:
    if not business_model:
        return None
    entities = business_model.get("entities") or []
    names = {
        entity.get("name")
        for entity in entities
        if isinstance(entity, dict) and isinstance(entity.get("name"), str)
    }
    return {name for name in names if name}


def _looks_like_business_entity(value: str) -> bool:
    return bool(value) and "__" not in value and "." not in value


async def validate_graph(
    org_id: UUID,
    graph: EntityGraph,
    *,
    business_model: dict | None = None,
) -> EntityGraph:
    """Probe each edge and enforce the canonical business entity namespace."""
    allowed_entities = _allowed_entities_from_business_model(business_model)
    kept_nodes: list[GraphNode] = []
    dropped_notes: list[str] = list(graph.notes)
    for node in graph.nodes:
        if not _looks_like_business_entity(node.entity):
            dropped_notes.append(
                f"Node {node.entity} dropped: entity ids must be business words, not table names."
            )
            continue
        if allowed_entities is not None and node.entity not in allowed_entities:
            dropped_notes.append(
                f"Node {node.entity} dropped: it is not in the BusinessModel entities."
            )
            continue
        kept_nodes.append(node)
    kept_entity_names = {node.entity for node in kept_nodes}

    prefiltered_edges: list[GraphEdge] = []
    for edge in graph.edges:
        if edge.left_entity not in kept_entity_names or edge.right_entity not in kept_entity_names:
            dropped_notes.append(
                f"Edge {edge.left_entity}<->{edge.right_entity} dropped: one side has no validated entity node."
            )
            continue
        prefiltered_edges.append(edge)

    graph = graph.model_copy(update={"nodes": kept_nodes, "edges": prefiltered_edges, "notes": dropped_notes})
    if not graph.edges:
        return graph

    results = await asyncio.gather(*[_probe_edge(org_id, edge) for edge in graph.edges])

    kept: list[GraphEdge] = []
    dropped_notes = list(graph.notes)
    for edge, ok in zip(graph.edges, results, strict=True):
        if ok:
            kept.append(edge.model_copy(update={"validated": True}))
        else:
            dropped_notes.append(
                f"Edge {edge.left_table}.{edge.left_key} ↔ {edge.right_table}.{edge.right_key} "
                "dropped: sample join returned no rows."
            )

    return graph.model_copy(update={"edges": kept, "notes": dropped_notes})
