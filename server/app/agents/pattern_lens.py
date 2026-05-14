"""PatternLens — propose what is worth investigating.

This is a single-responsibility PatternProposer. It reads asset semantics,
the relationship graph, and business memory, then emits ranked
`PatternHypothesis` objects only. It does not emit AnalysisGraph plans,
SQL, actions, charts, or prose. A separate instantiation step is responsible
for turning accepted hypotheses into executable plans.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field
from pydantic_ai import Agent

from app.agentic import PatternHypothesis
from app.agents._context import dumps
from app.agents._model import run_agent


class PatternBatch(BaseModel):
    hypotheses: list[PatternHypothesis] = Field(default_factory=list)

    @property
    def proposals(self) -> list[PatternHypothesis]:
        """Backward-compatible read alias for older callers."""
        return self.hypotheses


_SYSTEM_PROMPT = """\
You are PatternProposer for Baseflo.

Single responsibility:
Propose 3-6 useful PatternHypothesis objects from the connected business
shape. You do not emit AnalysisGraph, SQL, formulas, charts, actions, or
narrative. You only decide what is worth investigating.

Inputs:
- Asset summaries with exact asset ids, qualified table names, roles, entity
  types, keys, time dimensions, and measures.
- Relationship graph with validated business entities and joins.
- Business memory.

Grounding rules:
- `target_entity` must be an entity present in the relationship graph or
  asset summaries.
- `target_asset_id` must copy an exact asset id from the input.
- Every SignalSpec must use exact asset_id, exact table qualified_name, and
  exact measure column name from the asset summaries.
- Do not invent tables, fields, entities, channels, teams, or sources.
- If a useful hypothesis needs a missing field, do not create the hypothesis.

Pattern vocabulary:
- `pattern_type` is open vocabulary and snake_case. It should name the shape,
  not a fixed domain template. Examples: `ranked_entity_concentration`,
  `capacity_pressure`, `relationship_gap`, `cross_source_signal_mismatch`.
- `shape` describes what rows an instantiator should try to materialize.
- `why` explains why this investigation matters for the operator.
- `priority` is 0-1.

Quality bar:
- Prefer diverse hypotheses across entities and signals.
- Prefer hypotheses that could create a cohort, comparison, or ranked list.
- Avoid trivial counts when richer signals exist.
- Drop hypotheses with always-null/zero measures or only opaque identifiers.

Return a PatternBatch with hypotheses ordered by priority descending.
Emit only the typed output.
"""

_pattern_lens: Agent[None, PatternBatch] = Agent(
    output_type=PatternBatch,
    system_prompt=_SYSTEM_PROMPT,
)


async def propose_patterns(
    *,
    asset_summaries: list[dict[str, Any]],
    relationship_graph: dict[str, Any],
    memories: list[dict[str, Any]] | None = None,
) -> PatternBatch:
    context = dumps({
        "assets": asset_summaries,
        "relationship_graph": relationship_graph,
        "memory": memories or [],
    })
    user_message = f"Propose analyses worth running today:\n{context}"
    return await run_agent(_pattern_lens, user_message, label="pattern_lens")
