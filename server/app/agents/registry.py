"""Agent registry — single source of truth for agent specs.

Per docs/40-features/ENG-RUNTIME.md §3.1, adding a new agent is:

1. Create `app/agents/specialists/<role>/agent.py` matching the anatomy.
2. Define an `AgentSpec` with typed input/output, instructions, model tier.
3. Call `register_agent(spec)` at module import.
4. Update `model_routing.AGENT_MODEL_TIERS` if a new agent is added.

The registry is read-only at runtime; population happens at import time.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.core.errors import BasefloError

if TYPE_CHECKING:
    from app.agents.types import AgentSpec


class AgentRegistry:
    """Process-wide AgentSpec registry."""

    _specs: dict[str, AgentSpec] = {}  # type: ignore[type-arg]

    @classmethod
    def register(cls, spec: AgentSpec) -> AgentSpec:  # type: ignore[type-arg]
        if spec.name in cls._specs:
            existing = cls._specs[spec.name]
            if existing is spec:
                # Idempotent re-import; safe.
                return spec
            raise BasefloError(
                error_code="BF-AGENT-001",
                message=f"Duplicate agent registration: {spec.name!r}",
                status_code=500,
            )
        cls._specs[spec.name] = spec
        return spec

    @classmethod
    def get(cls, name: str) -> AgentSpec:  # type: ignore[type-arg]
        if name not in cls._specs:
            raise BasefloError(
                error_code="BF-AGENT-001",
                message=f"Unknown agent: {name!r}",
                status_code=500,
            )
        return cls._specs[name]

    @classmethod
    def list_specialist_names(cls) -> list[str]:
        return sorted(cls._specs.keys())

    @classmethod
    def clear(cls) -> None:
        """Test-only: reset the registry between tests."""
        cls._specs.clear()


def register_agent(spec: AgentSpec) -> AgentSpec:  # type: ignore[type-arg]
    """Module-level convenience for `AgentRegistry.register(spec)`."""
    return AgentRegistry.register(spec)
