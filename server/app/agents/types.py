"""Typed contracts for the agent runtime.

Strict typing per docs/05-coding-rules.md §2: no `Any` in critical paths,
no `dict[str, Any]` in agent input/output models.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from enum import StrEnum
from typing import Generic, TypeVar
from uuid import UUID

from pydantic import BaseModel, Field, model_validator
from pydantic.json_schema import SkipJsonSchema


class ModelTier(StrEnum):
    FAST = "fast"
    BALANCED = "balanced"
    REASONING = "reasoning"


class AgentRunStatus(StrEnum):
    PASSED = "passed"
    WARNING = "warning"
    FAILED = "failed"
    NEEDS_CLARIFICATION = "needs_clarification"


class TokenUsage(BaseModel, frozen=True):
    """Provider-reported token usage for one agent run.

    Real values must come from `pydantic_ai.RunResult.usage()`. Hardcoded zeros
    are forbidden (the audit caught a regression here we are not repeating).
    """

    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    cache_read_tokens: int = Field(default=0, ge=0)
    cache_write_tokens: int = Field(default=0, ge=0)
    requests: int = Field(default=0, ge=0)


# Per-agent input/output models are nominal subclasses of BaseModel; the
# runtime pins them via type vars on the spec.
InputT = TypeVar("InputT", bound=BaseModel)
OutputT = TypeVar("OutputT", bound=BaseModel)


class AgentSpec(BaseModel, Generic[InputT, OutputT]):
    """Static description of an agent. Registered once; immutable thereafter."""

    model_config = {"frozen": True, "arbitrary_types_allowed": True}

    name: str = Field(min_length=2, max_length=80, pattern=r"^[A-Z][A-Za-z0-9]+$")
    input_type: type[BaseModel]
    output_type: type[BaseModel]
    instructions: str = Field(min_length=200)  # ≥200 words enforced by tests; this is char-floor
    model_tier: ModelTier
    max_repair_attempts: int = Field(default=2, ge=1, le=5)
    output_validators: SkipJsonSchema[tuple[Callable[..., OutputT], ...]] = Field(
        default_factory=tuple,
        exclude=True,
    )
    cache_key_fn: Callable[[BaseModel], str] | None = None

    @model_validator(mode="after")
    def _instructions_long_enough(self) -> AgentSpec[InputT, OutputT]:
        # Soft check — exact word count enforced in test_prompt_invariants per agent.
        if len(self.instructions.split()) < 50:
            raise ValueError(
                f"Agent {self.name!r} instructions are suspiciously short. "
                "Per docs/05-coding-rules.md §1.1 every agent ships with a real prompt."
            )
        return self


class AgentRunResult(BaseModel, Generic[OutputT]):
    """Result of a single AgentRuntime.run(...) call.

    `output` is parameterized by the agent's declared `output_type`, so callers
    receive precisely-typed results without `cast` / `isinstance` narrowing.
    """

    model_config = {"arbitrary_types_allowed": True}

    agent_name: str
    output: OutputT
    attempt_count: int = Field(ge=1)
    repair_attempted: bool
    escalated: bool                      # tier was bumped during this run
    final_status: AgentRunStatus
    model_tier_used: ModelTier
    model_name_used: str
    duration_ms: int = Field(ge=0)
    usage: TokenUsage
    started_at: datetime
    completed_at: datetime
    agent_run_id: UUID
