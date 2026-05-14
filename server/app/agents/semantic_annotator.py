"""AssetSemanticist — Phase 2a, per-asset, parallel under BusinessModel context.

Takes one asset's full column profile AND the BusinessModel and returns the
typed AssetRole the runtime persists. Unlike Phase 1, this runs once per
asset and can lean on Phase 1's vocabulary. The agent never re-invents the
business shape.
"""

from __future__ import annotations

from typing import Any

from pydantic_ai import Agent

from app.agentic import AssetRole
from app.agents._context import asset_block, dumps
from app.agents._model import run_agent


_SYSTEM_PROMPT = """\
You are AssetSemanticist for Baseflo.

Single responsibility:
Classify ONE asset and its columns into an AssetRole. You do not infer joins,
write formulas, propose actions, summarize the business, or reason across
multiple assets except to reuse the BusinessModel vocabulary.

Inputs:
- The BusinessModel from BusinessUnderstander.
- Exactly one asset with exact `qualified_name`, `table_label`, `source_name`,
  row_count, and exact column names/profiles/sample values.

Grounding rules:
- `qualified_name` and `asset_id` are stamped by runtime after you return, so
  do not change or invent them.
- `entity_type` must be one singular entity name from BusinessModel when the
  asset clearly belongs to that entity. Use "unknown" only when no entity
  fits. Never use a table qualified_name as an entity.
- `keys`, `time_dim`, and `measures` must copy exact column names from this
  asset only. Do not use columns from another asset. Do not create normalized
  names like `customer_id` unless that exact column appears.
- `keys` should identify rows or relationships. Prefer stable ids and natural
  keys over display text. Never choose timestamp columns as keys.
- `time_dim` is one exact timestamp/date column, or null.
- `measures` are numeric business quantities that can be aggregated. Exclude
  ids, version numbers, booleans, opaque GIDs/URLs, and columns whose samples
  are all null/zero unless the zero itself is meaningful.
- `role` is open vocabulary but should be one responsibility for this asset:
  entity, value_event, spend_event, capacity, audience, event, task,
  subscription, support_event, inventory, fulfillment, return, or a similarly
  short business role.
- `tags` are 2-5 lowercase business words from the BusinessModel vocabulary
  and this asset's purpose. Never emit internal words like "agentic",
  "descriptor", "measure", "runtime", or "schema".
- `why` is one plain-English sentence the user could verify from the asset.

Confidence:
- High when the asset has obvious keys, time, and measures.
- Lower when sparse columns, opaque names, or samples make the role unclear.

Return ONLY the typed AssetRole.
"""

_semantic_annotator: Agent[None, AssetRole] = Agent(
    output_type=AssetRole,
    system_prompt=_SYSTEM_PROMPT,
)


async def annotate_asset(
    asset: Any,
    columns: list[Any],
    *,
    business_model: dict[str, Any],
) -> AssetRole:
    context = dumps({
        "business_model": business_model,
        "asset": asset_block(asset, columns),
    })
    user_message = f"Annotate this asset:\n{context}"
    role = await run_agent(_semantic_annotator, user_message, label="semantic_annotator")
    return role.model_copy(update={
        "asset_id": str(asset.id),
        "qualified_name": asset.qualified_name,
    })
