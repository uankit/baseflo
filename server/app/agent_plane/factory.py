"""Factory for Agent Plane capability agents."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic_ai import Agent

from app.agent_plane.specs import AgentSpec

_PROMPT_ROOT = Path(__file__).resolve().parent / "prompts"


class AgentFactoryError(Exception):
    pass


class AgentFactory:
    def __init__(self, *, prompt_root: Path = _PROMPT_ROOT) -> None:
        self.prompt_root = prompt_root
        self._cache: dict[str, Agent[None, Any]] = {}

    def prompt_for(self, spec: AgentSpec) -> str:
        path = self.prompt_root / spec.prompt_path
        if not path.exists():
            raise AgentFactoryError(f"Prompt missing for {spec.name}: {path}")
        return path.read_text(encoding="utf-8").strip()

    def create(self, spec: AgentSpec) -> Agent[None, Any]:
        cached = self._cache.get(spec.name)
        if cached is not None:
            return cached
        agent: Agent[None, Any] = Agent(
            output_type=spec.output_type,
            system_prompt=self.prompt_for(spec),
        )
        self._cache[spec.name] = agent
        return agent
