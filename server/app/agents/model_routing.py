"""Model routing — agent-name → model tier → model name.

Per docs/00-decisions.md §7B, OpenAI is the v1 primary; Anthropic is reachable
via env-only flip. The agent code never imports a provider SDK.

Each `AgentSpec` declares its own `model_tier`; the v1 reference table lives
in docs/03-agentic-workflow.md §6 (Clarification=FAST, ColumnClassifier=
BALANCED, the rest REASONING). Routing here just reads the spec.
"""

from __future__ import annotations

from app.agents.registry import AgentRegistry
from app.agents.types import ModelTier
from app.core.config import get_config


def tier_for_agent(agent_name: str) -> ModelTier:
    """Return the registered agent's declared tier.

    Raises `BF-AGENT-001` (via AgentRegistry.get) if the spec is unknown.
    """
    return AgentRegistry.get(agent_name).model_tier


def resolve_model_name(tier: ModelTier) -> str:
    """Look up the configured model name for the given tier."""
    config = get_config()
    return config.model_name_for_tier(tier.value)


def escalation_path(start: ModelTier) -> list[ModelTier]:
    """Tier escalation order when a run exhausts repair attempts.

    `fast` → `balanced` → `reasoning`.
    `balanced` → `reasoning`.
    `reasoning` → `reasoning` (no further escalation; raises BF-AGENT-005).
    """
    order = [ModelTier.FAST, ModelTier.BALANCED, ModelTier.REASONING]
    start_idx = order.index(start)
    return order[start_idx:]
