"""RelationshipMapper — Phase 3, builds the cross-source entity graph.

Inputs:
- The BusinessModel (Phase 1).
- Every annotated asset (Phase 2a, AssetRole list).
- The raw value-overlap join candidates from the deterministic profiler.

Output: a typed `EntityGraph` — nodes are business entities, edges are
joins that connect them, each with cardinality and a one-sentence meaning.

The graph is then handed to a deterministic GraphValidator that runs
sample joins via SQL to verify each edge before any downstream agent uses
it. Edges that don't materialize are dropped.
"""

from __future__ import annotations

from typing import Any

from pydantic_ai import Agent

from app.agents._contracts import EntityGraph
from app.agents._context import dumps
from app.agents._model import run_agent


_SYSTEM_PROMPT = """\
You are RelationshipGraphBuilder for Baseflo.

Single responsibility:
Build the business entity graph. You only decide which existing business
entities have nodes and which exact existing table columns can connect them.
You do not propose formulas, actions, KPIs, narratives, charts, or team work.

Inputs:
- BusinessModel with entity names and exact primary/related asset names.
- Annotated AssetRole rows with exact qualified_name, entity_type, keys,
  measures, time_dim, and tags.
- Runtime raw value-overlap candidates with exact table and column names.

Hard grounding rules:
- Nodes may only use entity names present in BusinessModel.entities.
- A node's `asset_qualified_name` must be copied exactly from a connected
  asset in the input. Do not write a source name, role name, or guessed table.
- Never use a qualified table name as `entity`. Entity ids are business
  nouns such as `customer`, `product`, `order`, `variant`, `return`.
- Edges may only reference nodes you emitted. Do not create an edge to a
  missing entity such as `supplier` unless BusinessModel has a supplier node
  backed by an actual asset.
- `left_table` and `right_table` must copy exact asset qualified_names.
- `left_key` and `right_key` must copy exact column names that exist on those
  tables. Do not normalize, singularize, pluralize, or guess names.
- Prefer raw value-overlap candidates. You may propose a missed edge only
  when both exact key columns are present in asset roles and the business
  meaning is obvious. If not obvious, write a note instead of an edge.
- `validated` is always false. Runtime stamps true only after a sample join.

Nodes:
- Emit one GraphNode per BusinessModel entity that has at least one connected
  asset.
- `label` is the user-facing noun.
- `why` explains what this node represents in one plain sentence.

Edges:
- Emit only real business relationships, not accidental overlaps on status,
  country, currency, booleans, empty strings, or repeated labels.
- `meaning` must be user-verifiable, for example: "Each order belongs to one
  customer through customer_id."
- `confidence` is lower when the relationship is inferred rather than copied
  from a strong key/foreign-key shape.

Notes:
- Use `notes` for useful relationships the data hints at but cannot safely
  connect with exact keys.

Return ONLY the typed EntityGraph.
"""

_relationship_mapper: Agent[None, EntityGraph] = Agent(
    output_type=EntityGraph,
    system_prompt=_SYSTEM_PROMPT,
)


async def map_relationships(
    *,
    business_model: dict[str, Any],
    asset_roles: list[dict[str, Any]],
    raw_candidates: list[dict[str, Any]],
) -> EntityGraph:
    context = dumps({
        "business_model": business_model,
        "annotated_assets": asset_roles,
        "raw_join_candidates": raw_candidates,
    })
    user_message = f"Build the entity graph:\n{context}"
    return await run_agent(_relationship_mapper, user_message, label="relationship_mapper")
