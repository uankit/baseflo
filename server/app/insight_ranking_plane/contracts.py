"""Contracts for ranked insight candidates."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

RankedItemKind = Literal["insight", "candidate_view", "cohort", "action_pack", "surface"]


class RankingModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RankingScoreBreakdown(RankingModel):
    money: float = Field(ge=0.0, le=1.0)
    volume: float = Field(ge=0.0, le=1.0)
    deviation: float = Field(ge=0.0, le=1.0)
    actionability: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)


class RankedInsight(RankingModel):
    rank: int
    item_id: str
    item_kind: RankedItemKind
    title: str
    score: float = Field(ge=0.0, le=1.0)
    score_breakdown: RankingScoreBreakdown
    why_ranked: str
    refs: dict[str, Any] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)


class InsightRankingPackage(RankingModel):
    ranked: list[RankedInsight] = Field(default_factory=list)
    generated_from: dict[str, Any] = Field(default_factory=dict)
    scoring_version: str = "baseflo_ranker_v1"
