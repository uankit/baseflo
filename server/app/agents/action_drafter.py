"""ActionDrafter — Phase 8b, drafts team-appropriate moves.

Inputs: team_id, the team's interpretation of the rows, the BusinessModel,
the asset semantics, the row preview, and the registered capabilities. The
agent writes 1–3 team-shaped actions. Different teams want different action
shapes — sales wants a call list; marketing wants a segment; ops wants a
reorder. The system prompt makes the agent honor that.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field
from pydantic_ai import Agent

from app.agentic import ActionDraft
from app.agents._context import dumps, result_preview_block
from app.agents._model import run_agent


class ActionBatch(BaseModel):
    actions: list[ActionDraft] = Field(default_factory=list)


# v1 capabilities — no external writebacks yet. v2 will add Mailchimp /
# Shopify / Email / Slack adapters; the agent's contract doesn't change.
_CURRENT_CAPABILITIES = [
    {
        "name": "baseflo.prepare_list",
        "execution_mode": "prepare_for_user",
        "description": "Materialize the rows as a saved list for the team to review or export.",
    },
    {
        "name": "baseflo.draft_email",
        "execution_mode": "draft_only",
        "description": "Draft an email (subject + body) about the finding. Drafts only; no send.",
    },
    {
        "name": "baseflo.delegate_task",
        "execution_mode": "delegate_inside_baseflo",
        "description": "Create an internal task with the claim, evidence, and a named owner.",
    },
    {
        "name": "baseflo.open_in_ask",
        "execution_mode": "prepare_for_user",
        "description": "Open this finding as an Ask thread so the user can pivot or join other sources.",
    },
]


_SYSTEM_PROMPT = """\
You are ActionDrafter for Baseflo.

Single responsibility:
Turn one interpreted finding into approval-gated action drafts. You do not
reinterpret the data, propose new analyses, create charts, or invent evidence.

You receive:
- `team_id`: the team you are drafting for.
- BusinessModel vocabulary.
- The interpretation written by Hypothesizer.
- Asset semantics for the entity in focus.
- Row preview: the concrete cohort or ranked rows this finding is about.
- Capability registry: the only executable/preparable capabilities available.

Emit a typed ActionBatch with 1-3 ActionDrafts.

Grounding rules:
- Only propose actions whose `capability_required` exactly matches a registry
  capability name.
- `execution_mode` must copy the registry execution_mode.
- Payload values must come from the interpretation, BusinessModel, asset
  role, row preview, or capability description. Do not invent customer lists,
  emails, discounts, owners, campaigns, suppliers, or products absent from
  the input.
- If an external writeback capability is not registered, do not claim the
  system can send, discount, reorder, run ads, or update another tool. Use
  draft/list/task actions instead.
- Every action must include a `why` tied to the interpretation and a `risk`
  that explains what could go wrong.

Good action shapes by team:
- sales: prepare call list, draft follow-up, create win-back task.
- marketing: prepare segment, draft campaign copy, create channel review task.
- ops: prepare reorder list, create fulfillment exception task, flag QC review.
- growth: prepare cohort, draft retention experiment, create expansion task.
- product: prepare variant/review list, create catalog investigation task.
- biz_analyst: prepare report list, create margin/cash investigation task.

For each ActionDraft:
- `action_type`: short snake_case name.
- `title`: verb-led, under 60 chars.
- `summary`: one sentence describing what approval prepares or creates.
- `why`: why this action follows from the finding.
- `capability_required`: exact registry name.
- `execution_mode`: exact registry mode.
- `payload`: JSON-able dict with enough info for the runtime to prepare it.
- `approval_scope`: no external writes for v1 capabilities.
- `risk`: worst-case sentence.

Rules:
- First action is the recommended default.
- No near-duplicates.
- No engineering vocabulary.

Return ONLY the typed ActionBatch.
"""

_action_drafter: Agent[None, ActionBatch] = Agent(
    output_type=ActionBatch,
    system_prompt=_SYSTEM_PROMPT,
)


async def draft_actions(
    *,
    team_id: str,
    business_model: dict[str, Any],
    interpretation: dict[str, Any],
    asset_role: dict[str, Any],
    rows: list[dict[str, Any]],
) -> ActionBatch:
    context = dumps({
        "team_id": team_id,
        "business_model": business_model,
        "interpretation": interpretation,
        "asset": asset_role,
        "row_count": len(rows),
        "rows": result_preview_block(rows, limit=8),
        "capabilities": _CURRENT_CAPABILITIES,
    })
    user_message = f"Draft this team's next moves:\n{context}"
    return await run_agent(_action_drafter, user_message, label=f"action_drafter:{team_id}")
