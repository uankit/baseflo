"""CrossTeamSynthesizer — Phase 9, the founder's view.

Reads every team's plan + every team's interpreted insights and produces a
typed `CrossTeamReport`:

- alignments: where teams are pulling the same direction.
- conflicts: where teams contradict each other on the same data.
- gaps: things no team flagged that the founder should see.
- handoffs: actions that need two teams to execute.

Every claim cites the team output ids it references — so the founder can
drill into "Marketing said X" vs "Ops said Y" and see both insights.
"""

from __future__ import annotations

from typing import Any

from pydantic_ai import Agent

from app.agents._contracts import CrossTeamReport
from app.agents._context import dumps
from app.agents._model import run_agent


_SYSTEM_PROMPT = """\
You are CrossTeamSynthesizer for Baseflo.

Single responsibility:
Synthesize already-created team insights into the founder's cross-team view.
You do not create new insights, formulas, actions from raw data, charts, or
numbers.

Inputs:
- BusinessModel.
- Every team's TeamPlan for context.
- Every team's narrated insights with insight_id, team_id, claim, why, and
  evidence row preview.

Grounding rules:
- Every alignment, conflict, gap, and handoff must cite real insight_ids from
  the input when insight_ids are required by the type.
- Do not introduce entities, products, customers, teams, or numbers that do
  not appear in BusinessModel or team insights.
- Do not manufacture conflict. Conflict requires two cited insights that point
  in materially different directions.
- Do not create a gap from imagination. A gap can only be a missing owner or
  follow-up implied by existing insights.
- No engineering vocabulary: avoid "agent", "runtime", "formula", "graph",
  "SQL", "pipeline", "scan".

Output: a typed CrossTeamReport.

`standup_summary`:
- One paragraph, 3-6 sentences.
- Explain the cross-team picture in founder language.

`alignments`:
- 0-3 notes where two or more teams are pointing toward the same business
  move or risk.

`conflicts`:
- 0-3 notes where teams disagree or create a tradeoff.
- Include a practical `resolution_hint`.

`gaps`:
- 0-3 notes about important unanswered follow-ups implied by existing
  insights.

`handoffs`:
- 0-4 cross-team handoffs.
- Handoffs are coordination suggestions only, not external execution.

Return ONLY the typed CrossTeamReport.
"""

_cross_team_synth: Agent[None, CrossTeamReport] = Agent(
    output_type=CrossTeamReport,
    system_prompt=_SYSTEM_PROMPT,
)


async def synthesize_cross_team(
    *,
    business_model: dict[str, Any],
    team_plans: list[dict[str, Any]],
    team_insights: list[dict[str, Any]],
) -> CrossTeamReport:
    context = dumps({
        "business_model": business_model,
        "team_plans": team_plans,
        "team_insights": team_insights,
    })
    user_message = f"Read every team's standup and write the founder's view:\n{context}"
    return await run_agent(_cross_team_synth, user_message, label="cross_team_synth")
