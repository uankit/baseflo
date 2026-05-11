"""Typed I/O for ClarificationAgent.

Per docs/40-features/AGENT-CLAR.md §3.2.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class BusinessTopic(StrEnum):
    PRICING_MODEL = "pricing_model"
    USER_TYPES = "user_types"
    OFFERING_TYPE = "offering_type"
    LIFECYCLE = "lifecycle"
    MONEY_FLOW = "money_flow"
    OTHER = "other"


class DescriptionSignals(BaseModel):
    """Deterministic facts about the user's description.

    See `evidence.compute_description_signals`. The agent reads these as
    typed evidence; nothing in this module decides meaning.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    word_count: int = Field(ge=0)
    has_business_noun: bool
    references_pricing_words: bool
    references_user_types: bool
    references_offering: bool


class ClarificationInput(BaseModel):
    """Input handed to the agent.

    `parent_ir_summary` and `refinement_intent` are populated for refinement
    v1 only uses `description` + `description_signals`.
    """

    model_config = ConfigDict(extra="forbid")

    description: str = Field(min_length=1, max_length=4000)
    description_signals: DescriptionSignals
    refinement_intent: str | None = Field(default=None, max_length=2000)


class Question(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=10, max_length=200)
    business_topic: BusinessTopic
    options: list[str] | None = Field(default=None)
    """When set, the question is multiple-choice with exactly 2..4 options."""


class ClarificationOutput(BaseModel):
    """Output the agent returns.

    `blocking == True` iff at least one question is present. The validator
    enforces this invariant.
    """

    model_config = ConfigDict(extra="forbid")

    questions: list[Question] = Field(default_factory=list, max_length=3)
    blocking: bool
    rationale: str = Field(min_length=1, max_length=2000)
    """Trace-only; never user-surfaced."""
