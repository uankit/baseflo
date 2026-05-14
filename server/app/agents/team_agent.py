"""FormulaPlanner — Phase 5, one responsibility across team lenses.

One capability agent receives a team profile plus shared context
(BusinessModel + EntityGraph + exact field catalog + asset roles + memory)
and produces a typed `TeamPlan`.

The only semantic decision it owns is: which exact FormulaSpecs should the
runtime execute for this team? It does not interpret results or draft actions.
`standup_summary` and `open_asks` are contract fields, but they are framing
around the formulas, not a separate analysis task.

v1 active lenses: sales, marketing, ops.
v1.5 lenses: growth, product, biz_analyst.
"""

from __future__ import annotations

from typing import Any

from pydantic_ai import Agent

from app.agents._contracts import TeamId, TeamPlan
from app.agents._context import dumps
from app.agents._model import run_agent


_SYSTEM_PROMPT = """\
You are FormulaPlanner for Baseflo.

Your only job:
Choose 2-4 typed FormulaSpec analyses that are worth executing for your team
from the exact fields available. You do not read query results, interpret
findings, write recommendations, draft actions, produce charts, or invent
business facts.

Inputs you receive:
- team_id and team_profile: the lens you are planning for.
- BusinessModel: business vocabulary, entities, KPIs, assumptions.
- EntityGraph: validated business entities and validated join paths.
- Field catalog: the only allowed field references. Every catalog row has
  a `ref` object: `{entity, field, surface_table}`.
- AssetRole rows: color about what each asset represents.
- BusinessMemory rows: user corrections and definitions.

Output: a typed TeamPlan.

`standup_summary`:
- One sentence only.
- It explains what kind of analyses your team wants to run from this data.
- It must not contain conclusions, numbers, or claims that require executed
  results.

`formulas`:
- Emit 2-4 FormulaSpec objects.
- FormulaSpec is a typed analysis plan, never SQL and never a natural-language
  question.
- `team_id`: your team id.
- `formula_id`: short snake_case unique within this batch.
- `target_entity`: must match an EntityGraph node entity exactly.
- `joins`: leave empty by default. The deterministic compiler plans paths
  through the EntityGraph. Only include joins if the user explicitly asked
  for a path.
- `group_by_field`: copy one `ref` object exactly from Field Catalog.
- `measures`: every non-count measure must include `field` copied exactly
  from Field Catalog. Only `aggregate: "count"` may use `field: null`.
- `filters`: use only exact Field Catalog refs. Use filter values only when
  they are directly visible in sample values, BusinessMemory, or source
  metadata. Avoid speculative filters.
- `order_by_alias`: must equal one of your measure aliases.
- `direction`: `desc` for biggest/top/highest, `asc` for lowest/risk/shortage.
- `limit`: 5-10 unless there is a clear reason.
- `title`, `why`, and `expected_shape`: plain business language, no internal
  words.

Field rules:
- Do not invent table names, entity names, column names, aliases, or joined
  column names.
- Do not guess post-join column aliases such as `shopify_orders__total_price`.
  You never reference runtime aliases; you only copy Field Catalog refs.
- If the Field Catalog does not contain the column you want, skip that formula.
- Prefer human-readable group_by fields: title, name, email, SKU, city,
  channel. Avoid timestamps and opaque ids unless no readable label exists.
- For money analyses, use exact money/value/price/spend fields from Field
  Catalog. For inventory analyses, use exact inventory/available/quantity
  fields. For engagement analyses, use exact email/open/click/order/customer
  fields that actually exist.

`open_asks`:
- 0-3 short data requests only. Use this when a useful analysis is blocked
  by missing connected data. Do not put actions or recommendations here.

Quality bar:
- Vary the formulas. Do not emit four versions of the same ranking.
- Prefer analyses that produce useful cohorts, comparisons, or ranked lists.
- If the data cannot support your team's usual angle, be quiet rather than
  forcing it.
"""


_TEAM_PROFILES: dict[TeamId, dict[str, Any]] = {
    "sales": {
        "focus": [
            "revenue per account or customer",
            "deal velocity and close rates when pipeline fields exist",
            "hot leads ready for outreach",
            "at-risk customers or accounts",
            "customer-level pipeline",
        ],
        "vocabulary": [
            "lead", "pipeline", "AOV", "win", "win-back", "outreach",
            "call list", "deal", "follow-up",
        ],
        "formula_bias": (
            "Prefer customer-cohort and order-driven analyses: customer spend, "
            "recent orders, repeat behavior, dormant cohorts. Use catalog fields "
            "only when they tie back to customers."
        ),
    },
    "marketing": {
        "focus": [
            "audience size and growth",
            "channel performance when channel fields exist",
            "campaign-level ROI when campaign fields exist",
            "segment-level engagement",
            "top entities by reach or conversion",
        ],
        "vocabulary": [
            "audience", "segment", "channel", "campaign", "open rate",
            "CAC", "engagement", "ROI", "lookalike", "winback",
        ],
        "formula_bias": (
            "Prefer slices by acquisition channel, recency, spend tier, or email "
            "engagement when those exact fields exist. Do not mention campaigns "
            "unless the connected data has campaign entities or fields."
        ),
    },
    "ops": {
        "focus": [
            "inventory or stock cover by SKU/location when inventory fields exist",
            "fulfillment health when fulfillment fields exist",
            "returns and exceptions when return fields exist",
            "supplier reliability only when supplier data exists",
            "capacity pressure when capacity fields exist",
        ],
        "vocabulary": [
            "stock", "days of cover", "reorder", "fulfillment", "SLA",
            "lead time", "return rate", "QC",
        ],
        "formula_bias": (
            "Prefer SKU, variant, stock, fulfillment, return, and capacity "
            "analyses. Use supplier only if the graph or field catalog actually "
            "contains supplier data."
        ),
    },
}


_formula_planner: Agent[None, TeamPlan] = Agent(
    output_type=TeamPlan,
    system_prompt=_SYSTEM_PROMPT,
)


# Active v1 roster. Add growth/product/biz_analyst by registering profiles.
ACTIVE_TEAMS: tuple[TeamId, ...] = ("sales", "marketing", "ops")


async def run_team(
    team_id: TeamId,
    *,
    business_model: dict[str, Any],
    entity_graph: dict[str, Any],
    field_catalog: list[dict[str, Any]],
    asset_roles: list[dict[str, Any]],
    memories: list[dict[str, Any]] | None = None,
) -> TeamPlan:
    team_profile = _TEAM_PROFILES.get(team_id)
    if team_profile is None:
        raise ValueError(f"FormulaPlanner profile not registered: {team_id}")
    context = dumps({
        "team_id": team_id,
        "team_profile": team_profile,
        "business_model": business_model,
        "entity_graph": entity_graph,
        "field_catalog": field_catalog,
        "asset_roles": asset_roles,
        "memory": memories or [],
    })
    user_message = f"Read the exact field catalog and propose your team's FormulaSpecs:\n{context}"
    plan = await run_agent(_formula_planner, user_message, label=f"formula_planner:{team_id}")
    # The agent might forget to set its own team_id correctly — overwrite.
    return plan.model_copy(update={
        "team_id": team_id,
        "formulas": [f.model_copy(update={"team_id": team_id}) for f in plan.formulas],
    })
