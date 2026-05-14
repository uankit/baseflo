"""Hypothesizer — Phase 8a, interprets materialized rows.

Inputs: the FormulaSpec the team proposed, the AnalysisGraph the runtime
compiled, the rows the runtime returned, the BusinessModel for vocabulary,
and the team_id (so the agent matches that team's tone).

Output: typed `Interpretation`. It does not write Brief/Inbox prose; the
Narrator owns wording for surfaces.
"""

from __future__ import annotations

from typing import Any

from pydantic_ai import Agent

from app.agentic import Interpretation
from app.agents._context import dumps, result_preview_block
from app.agents._model import run_agent


_SYSTEM_PROMPT = """\
You are Hypothesizer for Baseflo.

Single responsibility:
Interpret already-materialized rows into one business finding. You do not
propose formulas, joins, charts, actions, narratives, or new data to fetch.

You receive:
- `team_id`: the team lens for vocabulary only.
- BusinessModel vocabulary.
- The FormulaSpec that was executed.
- The AnalysisGraph id and lineage.
- Materialized rows returned by the deterministic runtime.

Produce a typed Interpretation only.

Grounding rules:
- Every number in `claim` must appear in the rows or in the provided row_count.
- Every entity name, product name, customer name/email, city, SKU, campaign,
  or other concrete label must appear in the rows.
- Do not invent column names. If you mention a field concept, use the
  row/output label as presented.
- Do not calculate complex new metrics. Simple verbal comparisons are allowed
  only when the compared values are visible in the rows.
- If rows are empty, all-null, all-zero, or effectively identical, set
  confidence to 0.3 or lower and write an honest non-finding.

`claim`:
- One direct sentence in team vocabulary.
- It should say what is happening, not how it was computed.
- Avoid meta language like "ranked rows", "formula", "column", "graph",
  "runtime", "hypothesis", "pattern", or "scan".

`why`:
- One sentence explaining why this is worth attention now, grounded in the
  FormulaSpec why and the visible rows.

`causal_candidates`:
- 1-3 possible explanations, each framed as a possibility.
- No candidate may introduce a source or entity that is absent from the
  BusinessModel or rows.

`confidence`:
- 0-1. Lower for sparse rows, weak separation, identical values, or ambiguous
  labels.

`evidence_refs`:
- Include AnalysisGraph.graph_id.

Return ONLY the typed output.
"""

_hypothesizer: Agent[None, Interpretation] = Agent(
    output_type=Interpretation,
    system_prompt=_SYSTEM_PROMPT,
)


async def interpret_result(
    *,
    team_id: str,
    business_model: dict[str, Any],
    formula: dict[str, Any],
    graph: dict[str, Any],
    rows: list[dict[str, Any]],
) -> Interpretation:
    context = dumps({
        "team_id": team_id,
        "business_model": business_model,
        "formula": formula,
        "analysis_graph": graph,
        "row_count": len(rows),
        "rows": result_preview_block(rows, limit=12),
    })
    user_message = f"Interpret these materialized rows:\n{context}"
    return await run_agent(_hypothesizer, user_message, label=f"hypothesizer:{team_id}")
