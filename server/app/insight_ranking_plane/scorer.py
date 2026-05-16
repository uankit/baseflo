"""Rank insights, generated views, cohorts, and action packs."""

from __future__ import annotations

import math
from typing import Any

from app.insight_ranking_plane.contracts import (
    InsightRankingPackage,
    RankedInsight,
    RankingScoreBreakdown,
)


def rank_operating_insights(run: Any) -> InsightRankingPackage:
    run_data = _dump(run)
    candidates: list[dict[str, Any]] = []
    candidates.extend(_execution_candidates(run_data))
    candidates.extend(_surface_candidates(run_data))

    ranked = [
        _ranked(index, candidate)
        for index, candidate in enumerate(
            sorted(candidates, key=lambda candidate: candidate["score"], reverse=True),
            start=1,
        )
    ]
    return InsightRankingPackage(
        ranked=ranked[:100],
        generated_from={
            "execution_count": len(_record_list(run_data.get("executions"))),
            "surface_count": len(_record_list(_record(run_data.get("business_surfaces")).get("surfaces"))),
            "candidate_count": len(candidates),
        },
    )


def _execution_candidates(run_data: dict[str, Any]) -> list[dict[str, Any]]:
    patterns = _record(run_data.get("patterns"))
    hypotheses = {
        _text(hypothesis.get("hypothesis_id")): hypothesis
        for hypothesis in _record_list(patterns.get("hypotheses"))
    }
    interpretations = _record_list(run_data.get("interpretations"))
    candidates: list[dict[str, Any]] = []
    for index, execution in enumerate(_record_list(run_data.get("executions"))):
        if _text(execution.get("status")) != "completed":
            continue
        result = _record(execution.get("result"))
        hypothesis = hypotheses.get(_text(execution.get("hypothesis_id")), {})
        interpretation = _record_at(interpretations, index)
        row_count = _int(result.get("row_count"), 0)
        confidence = max(
            _float(hypothesis.get("priority"), 0.5),
            _float(interpretation.get("confidence"), 0.5),
        )
        money = _money_signal(result)
        volume = _volume_score(row_count)
        deviation = 0.72 if _has_any(hypothesis, ("gap", "divergence", "anomaly", "outlier", "drop")) else 0.45
        actionability = 0.74 if row_count > 0 else 0.25
        candidates.append(
            _candidate(
                item_id=f"insight:{_text(execution.get('graph_id'))}",
                item_kind="insight",
                title=_text(
                    interpretation.get("claim"),
                    _text(hypothesis.get("question"), _text(execution.get("graph_id"), "Insight")),
                ),
                money=money,
                volume=volume,
                deviation=deviation,
                actionability=actionability,
                confidence=confidence,
                refs={
                    "graph_id": execution.get("graph_id"),
                    "hypothesis_id": execution.get("hypothesis_id"),
                    "row_count": row_count,
                },
                tags=_compact(["insight", _text(hypothesis.get("pattern_type")), _text(hypothesis.get("target_entity"))]),
            )
        )
    return candidates


def _surface_candidates(run_data: dict[str, Any]) -> list[dict[str, Any]]:
    surfaces = _record_list(_record(run_data.get("business_surfaces")).get("surfaces"))
    candidates: list[dict[str, Any]] = []
    for surface in surfaces:
        surface_id = _text(surface.get("surface_id"))
        confidence = _float(surface.get("confidence"), 0.5)
        candidates.append(
            _candidate(
                item_id=f"surface:{surface_id}",
                item_kind="surface",
                title=_text(surface.get("title"), surface_id),
                money=_surface_money(surface),
                volume=_volume_score(len(_record_list(surface.get("field_refs"))) + len(_record_list(surface.get("graph_refs")))),
                deviation=0.45,
                actionability=_actionability(surface),
                confidence=confidence,
                refs={"surface_id": surface_id},
                tags=_compact(["surface", _text(surface.get("kind"))]),
            )
        )
        for view in _record_list(surface.get("candidate_views")):
            priority = _float(view.get("priority"), 0.5)
            candidates.append(
                _candidate(
                    item_id=f"candidate_view:{_text(view.get('view_id'))}",
                    item_kind="candidate_view",
                    title=_text(view.get("title"), _text(view.get("question"), "Candidate view")),
                    money=_surface_money(surface),
                    volume=_volume_score(len(_list(view.get("dimensions"))) + len(_list(view.get("measures")))),
                    deviation=0.78 if _text(view.get("algorithm")) in {"deviation_scan", "extreme_rank", "long_tail_scan"} else 0.55,
                    actionability=priority,
                    confidence=confidence,
                    refs={"surface_id": surface_id, "view_id": view.get("view_id"), "algorithm": view.get("algorithm")},
                    tags=_compact(["candidate_view", _text(surface.get("kind")), _text(view.get("algorithm"))]),
                )
            )
        for cohort in _record_list(surface.get("cohorts")):
            actionability = _float(cohort.get("actionability"), 0.5)
            candidates.append(
                _candidate(
                    item_id=f"cohort:{_text(cohort.get('cohort_id'))}",
                    item_kind="cohort",
                    title=_text(cohort.get("label"), "Business cohort"),
                    money=_surface_money(surface),
                    volume=0.72 if _text(cohort.get("size_hint")) == "computed at execution time" else 0.45,
                    deviation=0.7 if "gap" in _text(cohort.get("cohort_id")) else 0.5,
                    actionability=actionability,
                    confidence=confidence,
                    refs={"surface_id": surface_id, "cohort_id": cohort.get("cohort_id")},
                    tags=_compact(["cohort", _text(surface.get("kind")), _text(cohort.get("entity"))]),
                )
            )
        for action in _record_list(surface.get("action_packs")):
            priority = _float(action.get("priority"), 0.5)
            candidates.append(
                _candidate(
                    item_id=f"action_pack:{_text(action.get('action_pack_id'))}",
                    item_kind="action_pack",
                    title=_text(action.get("title"), "Action pack"),
                    money=_surface_money(surface),
                    volume=0.65,
                    deviation=0.45,
                    actionability=priority,
                    confidence=confidence,
                    refs={"surface_id": surface_id, "action_pack_id": action.get("action_pack_id")},
                    tags=_compact(["action_pack", _text(surface.get("kind")), _text(action.get("action_type"))]),
                )
            )
    return candidates


def _candidate(
    *,
    item_id: str,
    item_kind: str,
    title: str,
    money: float,
    volume: float,
    deviation: float,
    actionability: float,
    confidence: float,
    refs: dict[str, Any],
    tags: list[str],
) -> dict[str, Any]:
    score = (
        money * 0.25
        + volume * 0.2
        + deviation * 0.2
        + actionability * 0.25
        + confidence * 0.1
    )
    return {
        "item_id": item_id,
        "item_kind": item_kind,
        "title": title,
        "score": round(min(1.0, max(0.0, score)), 3),
        "breakdown": RankingScoreBreakdown(
            money=round(money, 3),
            volume=round(volume, 3),
            deviation=round(deviation, 3),
            actionability=round(actionability, 3),
            confidence=round(confidence, 3),
        ),
        "refs": refs,
        "tags": tags,
    }


def _ranked(index: int, candidate: dict[str, Any]) -> RankedInsight:
    breakdown: RankingScoreBreakdown = candidate["breakdown"]
    strongest = max(
        [
            ("money affected", breakdown.money),
            ("volume", breakdown.volume),
            ("deviation", breakdown.deviation),
            ("actionability", breakdown.actionability),
            ("confidence", breakdown.confidence),
        ],
        key=lambda item: item[1],
    )
    return RankedInsight(
        rank=index,
        item_id=candidate["item_id"],
        item_kind=candidate["item_kind"],
        title=candidate["title"],
        score=candidate["score"],
        score_breakdown=breakdown,
        why_ranked=f"Ranked here because {strongest[0]} is the strongest signal.",
        refs=candidate["refs"],
        tags=candidate["tags"],
    )


def _money_signal(result: dict[str, Any]) -> float:
    rows = _record_list(result.get("result_preview"))
    values: list[float] = []
    for row in rows:
        for key, value in row.items():
            if any(term in str(key).lower() for term in ("amount", "revenue", "cost", "pending", "total", "price")):
                number = _float(value, 0.0)
                if number:
                    values.append(abs(number))
    if not values:
        return 0.35
    return min(1.0, math.log10(sum(values) + 1) / 7)


def _surface_money(surface: dict[str, Any]) -> float:
    measures = _record_list(surface.get("measures"))
    if any(_text(measure.get("unit")) == "money" for measure in measures):
        return 0.78
    if any(
        _text(measure.get("kind")) in {"amount", "pending_amount", "bill_amount", "revenue", "cost", "expense"}
        for measure in measures
    ):
        return 0.74
    return 0.35


def _actionability(surface: dict[str, Any]) -> float:
    action_count = len(_record_list(surface.get("action_packs")))
    cohort_count = len(_record_list(surface.get("cohorts")))
    return min(1.0, 0.35 + action_count * 0.08 + cohort_count * 0.06)


def _volume_score(row_count: int) -> float:
    if row_count <= 0:
        return 0.2
    return min(1.0, math.log10(row_count + 1) / 4)


def _has_any(value: Any, terms: tuple[str, ...]) -> bool:
    blob = str(value).lower()
    return any(term in blob for term in terms)


def _dump(value: Any) -> dict[str, Any]:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    return value if isinstance(value, dict) else {}


def _record(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    return {}


def _record_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [_record(item) for item in value if _record(item)]


def _record_at(values: list[dict[str, Any]], index: int) -> dict[str, Any]:
    return values[index] if index < len(values) else {}


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _text(value: Any, fallback: str = "") -> str:
    return value.strip() if isinstance(value, str) and value.strip() else fallback


def _int(value: Any, fallback: int) -> int:
    return value if isinstance(value, int) else fallback


def _float(value: Any, fallback: float) -> float:
    if isinstance(value, int | float):
        return float(value)
    try:
        return float(str(value).replace(",", "").replace("₹", ""))
    except (TypeError, ValueError):
        return fallback


def _compact(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        clean = value.strip()
        if clean and clean not in result:
            result.append(clean)
    return result
