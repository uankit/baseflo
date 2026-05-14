"""Narrator — Phase 8b, turns structured findings into surface prose.

Inputs: BusinessModel vocabulary, the FormulaSpec/AnalysisGraph lineage,
materialized row preview, and the Hypothesizer's Interpretation.

Output: typed `NarrativeSpec`. It does not interpret data, draft actions,
choose charts, or propose new analyses.
"""

from __future__ import annotations

from typing import Any

from pydantic_ai import Agent

from app.agentic import NarrativeSpec
from app.agents._context import dumps, result_preview_block
from app.agents._model import run_agent


_SYSTEM_PROMPT = """\
You are Narrator for Baseflo.

Single responsibility:
Turn one structured Interpretation into short user-facing prose for a product
surface. You do not reinterpret data, propose actions, create charts, or invent
facts.

You receive:
- `team_id`: the team lens for tone only.
- BusinessModel vocabulary.
- FormulaSpec and AnalysisGraph lineage for evidence context.
- Materialized row preview.
- Interpretation from Hypothesizer.
- `style`: brief, inbox, or ask.

Grounding rules:
- Every number in `headline` and `summary` must appear in the Interpretation
  or row preview.
- Every concrete label in `headline` and `summary` must appear in the
  Interpretation or row preview.
- Use the Interpretation claim and why as the source of truth.
- Do not introduce new causal candidates, new columns, new entities, or new
  source names.
- Avoid internal words: formula, graph, runtime, SQL, schema, agent, scan,
  hypothesis, typed plan.

Output NarrativeSpec:
- `headline`: under 80 chars; the finding in newspaper style.
- `summary`: one supporting sentence.
- `why`: copy or lightly compress Interpretation.why.
- `style`: copy the requested style.

If the Interpretation confidence is low or the row preview is weak, keep the
headline cautious rather than dramatic.

Return ONLY the typed NarrativeSpec.
"""


_narrator: Agent[None, NarrativeSpec] = Agent(
    output_type=NarrativeSpec,
    system_prompt=_SYSTEM_PROMPT,
)


async def narrate_interpretation(
    *,
    team_id: str,
    business_model: dict[str, Any],
    formula: dict[str, Any],
    graph: dict[str, Any],
    interpretation: dict[str, Any],
    rows: list[dict[str, Any]],
    style: str = "brief",
) -> NarrativeSpec:
    context = dumps({
        "team_id": team_id,
        "business_model": business_model,
        "formula": formula,
        "analysis_graph": graph,
        "interpretation": interpretation,
        "row_count": len(rows),
        "rows": result_preview_block(rows, limit=12),
        "style": style,
    })
    user_message = f"Write the {style} narrative for this interpretation:\n{context}"
    return await run_agent(_narrator, user_message, label=f"narrator:{team_id}")
