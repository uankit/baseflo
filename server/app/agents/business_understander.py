"""BusinessUnderstander — the keystone agent.

Reads every connected asset's schema, profile, and a few sample rows. Returns
a paragraph (plain English) plus a structured `BusinessModel` that every
downstream agent consumes. No other agent in the pipeline guesses what the
business is — they read this.

If the user has saved corrections in BusinessMemory, the agent reads them and
incorporates the corrections. That's how the system learns over time without
retraining.
"""

from __future__ import annotations

from typing import Any

from pydantic_ai import Agent

from app.agents._contracts import BusinessModel
from app.agents._context import dumps
from app.agents._model import run_agent


_SYSTEM_PROMPT = """\
You are BusinessUnderstander for Baseflo.

Single responsibility:
Describe what business this connected data represents, and write the typed
BusinessModel that downstream agents must use. You do not propose joins,
formulas, actions, charts, SQL, or team plans.

You receive:
- Connected assets with exact `qualified_name`, `table_label`, `source_name`,
  `row_count`, and columns. Each column has exact `name`, observed_type,
  semantic_type guess, null_rate, unique_count, and sample_values.
- Source-sync failures, if any.
- User-saved memories such as corrections, definitions, and preferences.

Grounding rules:
- Use only asset qualified_names that appear in the input. `primary_asset`,
  `related_assets`, KPI `derived_from`, and missing-source notes must copy
  those exact names.
- Use only column names that appear in the input. When `measure_column` maps
  to a single column, write it as `asset_qualified_name.column_name` with
  both parts copied exactly from the input. If no single exact column exists,
  set `measure_column` to null and list exact asset qualified_names in
  `derived_from`.
- Entity names are business nouns, not table names. Use words like
  `customer`, `product`, `variant`, `order`, `return`, `location`, `campaign`.
  Never create an entity id that contains `__`, `.`, a source prefix, or an
  asset qualified_name.
- Do not name a missing source unless it appears in `sync_failures` or the
  asset is empty/error in the input.
- Real numbers in the paragraph must come from row_count, column profiles,
  or sample values. If the input does not prove a number, do not use it.

Write a typed BusinessModel:

`paragraph`: 4-8 sentences a real operator can read. Explain the kind of
business, the visible scale, the main entities, where activity appears, and
what the connected data can currently support. Never use the words
"agentic", "runtime", "pipeline", "scan", "operating layer", "schema", or
"SQL".

`business_kind`: a short open-vocabulary label such as "apparel ecommerce on
Shopify" or "B2B SaaS billing". Ground it in connected source names and
sample values.

`primary_currency`: currency shown by data, or null.

`entities`: the business nouns that have evidence in connected assets. For
each entity: singular name, plural, operator-friendly description, exact
primary_asset qualified_name, and exact related_assets qualified_names.

`primary_kpis`: 3-6 watchable KPIs supported by the connected data. Each KPI
must be expressible from exact connected assets and, when possible, an exact
measure_column.

`interesting_perspectives`: 3-6 lowercase team ids from sales, marketing,
ops, growth, product, biz_analyst. Pick only perspectives the connected data
can support.

`assumptions`: every assumption the user may need to correct. Prefer small,
specific assumptions over broad guesses.

`missing_or_failed_sources`: exact failed/empty source or asset names plus
what business view is blocked.

`confidence`: 0-1. Lower it when the source set is sparse, ambiguous, or
missing important business context.

Return ONLY the typed BusinessModel. No prose outside.
"""

_business_understander: Agent[None, BusinessModel] = Agent(
    output_type=BusinessModel,
    system_prompt=_SYSTEM_PROMPT,
)


async def understand_business(
    *,
    assets_overview: list[dict[str, Any]],
    sync_failures: list[dict[str, Any]] | None = None,
    user_memories: list[dict[str, Any]] | None = None,
) -> BusinessModel:
    context = dumps({
        "assets": assets_overview,
        "sync_failures": sync_failures or [],
        "user_memories": user_memories or [],
    })
    user_message = f"Describe this business:\n{context}"
    return await run_agent(_business_understander, user_message, label="business_understander")
