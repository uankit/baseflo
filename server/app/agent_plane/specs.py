"""Agent specifications for the fresh Agent Plane."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel

AgentName = Literal[
    "business_understander",
    "asset_semanticist",
    "field_semanticist",
    "relationship_mapper",
    "pattern_proposer",
    "instantiator",
    "hypothesizer",
    "chart_spec_agent",
    "action_drafter",
    "narrator",
    "brief_synthesizer",
]


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    attempts: int = 4
    base_seconds: float = 1.0
    max_seconds: float = 20.0


@dataclass(frozen=True, slots=True)
class CachePolicy:
    enabled: bool = True
    include_memory_version: bool = True


@dataclass(frozen=True, slots=True)
class ModelProfile:
    model_name: str | None = None
    max_parallelism: int = 1
    temperature: float | None = None


@dataclass(frozen=True, slots=True)
class AgentSpec:
    name: AgentName
    display_name: str
    responsibility: str
    output_type: type[BaseModel]
    prompt_path: str
    model_profile: ModelProfile = field(default_factory=ModelProfile)
    retry_policy: RetryPolicy = field(default_factory=RetryPolicy)
    cache_policy: CachePolicy = field(default_factory=CachePolicy)
    input_contract: str = "json"
    batchable: bool = False
