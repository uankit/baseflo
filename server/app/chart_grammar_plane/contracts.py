"""Typed chart grammar contracts backed by Vega-Lite JSON."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ChartGrammarModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


ChartMark = Literal["bar", "line", "point", "circle", "text", "rect"]


class VegaLiteChart(ChartGrammarModel):
    chart_id: str
    title: str
    why: str
    data_ref: str
    mark: ChartMark
    vega_lite: dict[str, Any]
    lineage_refs: list[str] = Field(default_factory=list)


class ChartGrammarPackage(ChartGrammarModel):
    charts: list[VegaLiteChart] = Field(default_factory=list)
    generated_from: dict[str, Any] = Field(default_factory=dict)
