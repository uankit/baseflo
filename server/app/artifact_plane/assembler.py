"""Deterministically assemble product artifacts from operating run output."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from app.artifact_plane.contracts import ArtifactDraft


def assemble_operating_artifacts(run: Any) -> list[ArtifactDraft]:
    run_data = _dump(run)
    run_id = str(run_data.get("run_id", ""))
    mode = str(run_data.get("mode", "scan"))
    run_date = _run_date(run_data)

    drafts: list[ArtifactDraft] = []
    drafts.extend(_brief_artifacts(run_data, run_id, mode, run_date))
    drafts.extend(_business_view_artifacts(run_data, run_id, run_date))
    drafts.extend(_business_surface_artifacts(run_data, run_id, run_date))
    drafts.extend(_semantic_layer_artifacts(run_data, run_id, run_date))
    drafts.extend(_chart_grammar_artifacts(run_data, run_id, run_date))
    drafts.extend(_insight_ranking_artifacts(run_data, run_id, run_date))
    drafts.extend(_entity_resolution_artifacts(run_data, run_id, run_date))
    drafts.extend(_knowledge_graph_artifacts(run_data, run_id, run_date))
    drafts.extend(_lineage_package_artifacts(run_data, run_id, run_date))
    drafts.extend(_execution_artifacts(run_data, run_id, mode))
    if mode == "ask":
        drafts.append(_ask_answer_artifact(run_data, run_id))
    drafts.append(_run_summary_artifact(run_data, run_id, mode))

    by_key: dict[str, ArtifactDraft] = {}
    for draft in drafts:
        by_key[draft.artifact_key] = draft
    return list(by_key.values())


def artifact_fingerprint(draft: ArtifactDraft) -> str:
    return hashlib.sha256(
        json.dumps(
            {
                "kind": draft.kind,
                "title": draft.title,
                "summary": draft.summary,
                "why": draft.why,
                "tags": sorted(set(draft.tags)),
                "priority": draft.priority,
                "source_refs": draft.source_refs,
                "payload": draft.payload,
            },
            sort_keys=True,
            default=str,
        ).encode("utf-8")
    ).hexdigest()


def _brief_artifacts(
    run_data: dict[str, Any],
    run_id: str,
    mode: str,
    run_date: str,
) -> list[ArtifactDraft]:
    brief = _record(run_data.get("brief"))
    if not brief:
        return []
    headline = _text(brief.get("headline"), f"{mode.title()} brief")
    summary_points = _list(brief.get("summary_points"))
    return [
        ArtifactDraft(
            artifact_key=f"brief:{mode}:{run_date}",
            kind="brief",
            title=headline,
            summary="\n".join(_text(point) for point in summary_points if _text(point)),
            why=_text(brief.get("why"), "Baseflo synthesized this from the latest operating run."),
            tags=_compact(["brief", mode, "latest"]),
            priority=0.9,
            source_refs={"run_id": run_id},
            payload={
                "brief": brief,
                "summary_points": summary_points,
                "urgent_artifact_ids": _list(brief.get("urgent_artifact_ids")),
            },
        )
    ]


def _business_view_artifacts(
    run_data: dict[str, Any],
    run_id: str,
    run_date: str,
) -> list[ArtifactDraft]:
    business_view = _record(run_data.get("business_view"))
    if not business_view:
        return []
    sections = _record_list(business_view.get("sections"))
    entity_views = _record_list(business_view.get("entity_views"))
    return [
        ArtifactDraft(
            artifact_key=f"business_view:{run_date}",
            kind="business_view",
            title=_text(business_view.get("headline"), "Business operating view"),
            summary=_text(
                business_view.get("summary"),
                f"{len(sections)} generated business sections are ready.",
            ),
            why=_text(
                business_view.get("why"),
                "Baseflo generated this from semantic roles and materialized evidence.",
            ),
            tags=_compact(
                [
                    "business_view",
                    "operating_room",
                    *[_text(section.get("kind")) for section in sections],
                ]
            ),
            priority=0.88,
            source_refs={"run_id": run_id},
            payload={
                "business_view": business_view,
                "sections": sections,
                "entity_views": entity_views,
            },
        )
    ]


def _business_surface_artifacts(
    run_data: dict[str, Any],
    run_id: str,
    run_date: str,
) -> list[ArtifactDraft]:
    business_surfaces = _record(run_data.get("business_surfaces"))
    if not business_surfaces:
        return []
    surfaces = _record_list(business_surfaces.get("surfaces"))
    candidate_count = sum(len(_record_list(surface.get("candidate_views"))) for surface in surfaces)
    cohort_count = sum(len(_record_list(surface.get("cohorts"))) for surface in surfaces)
    action_pack_count = sum(len(_record_list(surface.get("action_packs"))) for surface in surfaces)
    return [
        ArtifactDraft(
            artifact_key=f"business_surfaces:{run_date}",
            kind="business_surfaces",
            title=_text(business_surfaces.get("headline"), "Generated operating surfaces"),
            summary=_text(
                business_surfaces.get("summary"),
                f"{len(surfaces)} surfaces, {candidate_count} views, {cohort_count} cohorts.",
            ),
            why=_text(
                business_surfaces.get("why"),
                "Baseflo mined reusable workbenches from semantic roles and execution evidence.",
            ),
            tags=_compact(
                [
                    "business_surfaces",
                    "operating_room",
                    *[_text(surface.get("kind")) for surface in surfaces],
                ]
            ),
            priority=0.9,
            source_refs={"run_id": run_id},
            payload={
                "business_surfaces": business_surfaces,
                "surfaces": surfaces,
                "candidate_view_count": candidate_count,
                "cohort_count": cohort_count,
                "action_pack_count": action_pack_count,
            },
        )
    ]


def _semantic_layer_artifacts(
    run_data: dict[str, Any],
    run_id: str,
    run_date: str,
) -> list[ArtifactDraft]:
    semantic_layer = _record(run_data.get("semantic_layer"))
    if not semantic_layer:
        return []
    return [
        ArtifactDraft(
            artifact_key=f"semantic_layer:{run_date}",
            kind="semantic_layer",
            title="Semantic layer",
            summary=(
                f"{len(_record_list(semantic_layer.get('entities')))} entities, "
                f"{len(_record_list(semantic_layer.get('metrics')))} metrics."
            ),
            why="The semantic layer governs entities, dimensions, measures, metrics, and surface bindings.",
            tags=["semantic_layer"],
            priority=0.86,
            source_refs={"run_id": run_id},
            payload={"semantic_layer": semantic_layer},
        )
    ]


def _chart_grammar_artifacts(
    run_data: dict[str, Any],
    run_id: str,
    run_date: str,
) -> list[ArtifactDraft]:
    chart_grammar = _record(run_data.get("chart_grammar"))
    if not chart_grammar:
        return []
    charts = _record_list(chart_grammar.get("charts"))
    return [
        ArtifactDraft(
            artifact_key=f"chart_grammar:{run_date}",
            kind="chart_grammar",
            title=f"{len(charts)} Vega-Lite chart specs",
            summary="Typed chart grammar ready for UI rendering.",
            why="Chart grammar prevents the UI from parsing prose or guessing visualization mappings.",
            tags=["chart_grammar", "vega_lite"],
            priority=0.76 if charts else 0.35,
            source_refs={"run_id": run_id},
            payload={"chart_grammar": chart_grammar, "charts": charts},
        )
    ]


def _insight_ranking_artifacts(
    run_data: dict[str, Any],
    run_id: str,
    run_date: str,
) -> list[ArtifactDraft]:
    ranking = _record(run_data.get("insight_ranking"))
    if not ranking:
        return []
    ranked = _record_list(ranking.get("ranked"))
    return [
        ArtifactDraft(
            artifact_key=f"insight_ranking:{run_date}",
            kind="insight_ranking",
            title=f"{len(ranked)} ranked operating items",
            summary="Insights, cohorts, views, surfaces, and action packs ranked by business value.",
            why="Ranking uses money affected, volume, deviation, actionability, and confidence.",
            tags=["insight_ranking"],
            priority=0.87 if ranked else 0.3,
            source_refs={"run_id": run_id},
            payload={"insight_ranking": ranking, "ranked": ranked},
        )
    ]


def _entity_resolution_artifacts(
    run_data: dict[str, Any],
    run_id: str,
    run_date: str,
) -> list[ArtifactDraft]:
    entity_resolution = _record(run_data.get("entity_resolution"))
    if not entity_resolution:
        return []
    plans = _record_list(entity_resolution.get("plans"))
    executions = _record_list(entity_resolution.get("executions"))
    return [
        ArtifactDraft(
            artifact_key=f"entity_resolution:{run_date}",
            kind="entity_resolution",
            title=f"{len(plans)} entity-resolution plans",
            summary=(
                f"Splink-backed entity resolution is ready for {len(plans)} generated "
                "matching jobs."
            ),
            why=(
                "Entity resolution lets Baseflo connect messy party, customer, product, "
                "and offline-online records into one business graph."
            ),
            tags=["entity_resolution", "splink"],
            priority=0.82 if plans else 0.35,
            source_refs={"run_id": run_id},
            payload={
                "entity_resolution": entity_resolution,
                "plans": plans,
                "executions": executions,
            },
        )
    ]


def _knowledge_graph_artifacts(
    run_data: dict[str, Any],
    run_id: str,
    run_date: str,
) -> list[ArtifactDraft]:
    knowledge_graph = _record(run_data.get("knowledge_graph"))
    if not knowledge_graph:
        return []
    return [
        ArtifactDraft(
            artifact_key=f"knowledge_graph:{run_date}",
            kind="knowledge_graph",
            title="Kuzu insight graph",
            summary=(
                f"{knowledge_graph.get('node_count', 0)} nodes and "
                f"{knowledge_graph.get('edge_count', 0)} edges materialized."
            ),
            why="Kuzu stores the generated operating graph for fast graph traversal and lineage queries.",
            tags=["knowledge_graph", "kuzu"],
            priority=0.78 if _text(knowledge_graph.get("status")) == "completed" else 0.3,
            source_refs={"run_id": run_id},
            payload={"knowledge_graph": knowledge_graph},
        )
    ]


def _lineage_package_artifacts(
    run_data: dict[str, Any],
    run_id: str,
    run_date: str,
) -> list[ArtifactDraft]:
    lineage = _record(run_data.get("lineage"))
    if not lineage:
        return []
    runs = _record_list(lineage.get("runs"))
    datasets = _record_list(lineage.get("datasets"))
    return [
        ArtifactDraft(
            artifact_key=f"lineage_package:{run_date}",
            kind="lineage",
            title=f"{len(runs)} lineage runs",
            summary=f"{len(datasets)} datasets represented in OpenLineage-style lineage.",
            why="Lineage explains which canonical assets, analysis graphs, and packages produced each output.",
            tags=["lineage", "openlineage"],
            priority=0.7,
            source_refs={"run_id": run_id},
            payload={"lineage": lineage, "runs": runs, "datasets": datasets},
        )
    ]


def _execution_artifacts(run_data: dict[str, Any], run_id: str, mode: str) -> list[ArtifactDraft]:
    drafts: list[ArtifactDraft] = []
    patterns = _record(run_data.get("patterns"))
    hypotheses = {
        _text(hypothesis.get("hypothesis_id")): hypothesis
        for hypothesis in _record_list(patterns.get("hypotheses"))
    }
    interpretations = _record_list(run_data.get("interpretations"))
    charts = _record_list(run_data.get("chart_specs"))
    narratives = _record_list(run_data.get("narratives"))
    action_batches = _record_list(run_data.get("action_batches"))

    for index, execution in enumerate(_record_list(run_data.get("executions"))):
        graph_id = _text(execution.get("graph_id"), f"graph-{index + 1}")
        hypothesis_id = _text(execution.get("hypothesis_id"))
        plan = _record(execution.get("plan"))
        result = _record(execution.get("result"))
        interpretation = _record_at(interpretations, index)
        chart = _record_at(charts, index)
        narrative = _record_at(narratives, index)
        action_batch = _record_at(action_batches, index)
        actions = _record_list(action_batch.get("actions"))
        hypothesis = hypotheses.get(hypothesis_id, {})
        pattern_type = _text(hypothesis.get("pattern_type"))
        target_entity = _text(hypothesis.get("target_entity"))
        title = _title(graph_id, narrative, interpretation)
        summary = _summary(narrative, interpretation)
        why = _why(plan, narrative, interpretation, hypothesis)
        priority = _priority(hypothesis, interpretation)
        tags = _compact(
            [
                mode,
                "insight",
                pattern_type,
                target_entity,
                *[_text(action.get("action_type")) for action in actions],
            ]
        )
        source_refs = {
            "run_id": run_id,
            "graph_id": graph_id,
            "hypothesis_id": hypothesis_id,
            "chart_artifact_id": chart.get("artifact_id"),
        }
        base_payload = {
            "analysis_graph": plan,
            "hypothesis": hypothesis,
            "execution": execution,
            "result": result,
            "interpretation": interpretation,
            "narrative": narrative,
            "chart_spec": chart,
            "actions": actions,
        }

        drafts.append(
            ArtifactDraft(
                artifact_key=f"insight:{graph_id}",
                kind="insight",
                title=title,
                summary=summary,
                why=why,
                tags=tags,
                priority=priority,
                source_refs=source_refs,
                payload=base_payload,
            )
        )
        drafts.append(
            ArtifactDraft(
                artifact_key=f"inbox:{graph_id}",
                kind="inbox_item",
                title=title,
                summary=summary,
                why=why,
                tags=_compact([*tags, "inbox"]),
                priority=priority,
                source_refs={**source_refs, "insight_key": f"insight:{graph_id}"},
                payload={
                    **base_payload,
                    "insight_key": f"insight:{graph_id}",
                    "table_key": f"table:{graph_id}",
                    "audience_key": f"audience:{graph_id}",
                    "lineage_key": f"lineage:{graph_id}",
                },
            )
        )
        if result:
            drafts.append(
                ArtifactDraft(
                    artifact_key=f"table:{graph_id}",
                    kind="table",
                    title=f"Evidence table: {title}",
                    summary=f"{result.get('row_count', 0)} rows matched this analysis.",
                    why="The table preserves the materialized evidence behind the inference.",
                    tags=_compact([mode, "evidence", target_entity]),
                    priority=priority,
                    source_refs=source_refs,
                    payload={
                        "result_preview": _list(result.get("result_preview")),
                        "row_count": result.get("row_count", 0),
                        "data_ref": graph_id,
                    },
                )
            )
            drafts.append(
                ArtifactDraft(
                    artifact_key=f"lineage:{graph_id}",
                    kind="lineage",
                    title=f"Lineage: {title}",
                    summary="Fields, graph nodes, and execution references used for this result.",
                    why="Lineage lets Baseflo explain where the inference came from.",
                    tags=_compact([mode, "lineage", target_entity]),
                    priority=priority,
                    source_refs=source_refs,
                    payload={"lineage": _list(result.get("lineage")), "analysis_graph": plan},
                )
            )
        if chart:
            chart_id = _text(chart.get("artifact_id"), graph_id)
            drafts.append(
                ArtifactDraft(
                    artifact_key=f"chart:{chart_id}",
                    kind="chart",
                    title=_text(chart.get("title"), f"Chart: {title}"),
                    summary=_text(chart.get("viz_type"), "chart"),
                    why=_text(chart.get("why"), "The chart renders the materialized data shape."),
                    tags=_compact([mode, "chart", _text(chart.get("viz_type")), target_entity]),
                    priority=priority,
                    source_refs=source_refs,
                    payload={"chart_spec": chart},
                )
            )
        if narrative:
            drafts.append(
                ArtifactDraft(
                    artifact_key=f"narrative:{graph_id}",
                    kind="narrative",
                    title=_text(narrative.get("headline"), title),
                    summary=_text(narrative.get("summary"), summary),
                    why=_text(narrative.get("why"), why),
                    tags=_compact([mode, "narrative", _text(narrative.get("style")), target_entity]),
                    priority=priority,
                    source_refs=source_refs,
                    payload={"narrative": narrative},
                )
            )
        audience = _record(plan.get("audience"))
        if audience or result:
            drafts.append(
                ArtifactDraft(
                    artifact_key=f"audience:{graph_id}",
                    kind="audience",
                    title=f"Audience: {title}",
                    summary=f"{result.get('row_count', 0) if result else 0} records in scope.",
                    why="Audience defines what records this inference and its actions affect.",
                    tags=_compact([mode, "audience", target_entity]),
                    priority=priority,
                    source_refs=source_refs,
                    payload={"audience": audience, "row_count": result.get("row_count", 0) if result else 0},
                )
            )
        for action in actions:
            action_id = _text(action.get("action_id"), _stable_suffix(action))
            drafts.append(
                ArtifactDraft(
                    artifact_key=f"action:{action_id}",
                    kind="action",
                    title=_text(action.get("title"), "Recommended action"),
                    summary=_text(action.get("why_now"), _text(action.get("why"))),
                    why=_text(action.get("why"), "Baseflo proposed this action from the evidence."),
                    tags=_compact([mode, "action", _text(action.get("action_type")), target_entity]),
                    priority=priority,
                    source_refs={**source_refs, "action_id": action_id},
                    payload={"action": action, "insight_key": f"insight:{graph_id}"},
                )
            )
    return drafts


def _ask_answer_artifact(run_data: dict[str, Any], run_id: str) -> ArtifactDraft:
    question = _text(run_data.get("question"), "Ask answer")
    narratives = _record_list(run_data.get("narratives"))
    summary = "\n\n".join(
        _text(narrative.get("summary"))
        for narrative in narratives
        if _text(narrative.get("summary"))
    )
    if not summary:
        summary = "\n".join(
            _text(error.get("message"))
            for error in _record_list(run_data.get("errors"))
            if _text(error.get("message"))
        )
    return ArtifactDraft(
        artifact_key=f"ask:{run_id}",
        kind="ask_answer",
        title=question,
        summary=summary,
        why="Ask answers are assembled from materialized analysis results, not invented prose.",
        tags=["ask"],
        priority=0.8,
        source_refs={"run_id": run_id},
        payload={
            "question": question,
            "narratives": narratives,
            "chart_specs": _record_list(run_data.get("chart_specs")),
            "executions": _record_list(run_data.get("executions")),
            "action_batches": _record_list(run_data.get("action_batches")),
        },
    )


def _run_summary_artifact(run_data: dict[str, Any], run_id: str, mode: str) -> ArtifactDraft:
    status = _text(run_data.get("status"), "completed")
    context = _record(run_data.get("context_summary"))
    return ArtifactDraft(
        artifact_key=f"run_summary:{run_id}",
        kind="run_summary",
        title=f"{mode.title()} run {status}",
        summary=(
            f"{context.get('asset_count', 0)} assets, {context.get('field_count', 0)} fields, "
            f"{context.get('row_count', 0)} rows."
        ),
        why="Run summary anchors this artifact batch to the operating pipeline execution.",
        tags=[mode, status, "run"],
        priority=0.3,
        source_refs={"run_id": run_id},
        payload={"run": run_data},
    )


def _run_date(run_data: dict[str, Any]) -> str:
    raw = _text(run_data.get("completed_at"), _text(run_data.get("started_at")))
    if not raw:
        return "undated"
    return raw[:10]


def _title(graph_id: str, narrative: dict[str, Any], interpretation: dict[str, Any]) -> str:
    return _text(
        narrative.get("headline"),
        _text(interpretation.get("claim"), graph_id.replace("_", " ").title()),
    )


def _summary(narrative: dict[str, Any], interpretation: dict[str, Any]) -> str:
    return _text(narrative.get("summary"), _text(interpretation.get("why")))


def _why(
    plan: dict[str, Any],
    narrative: dict[str, Any],
    interpretation: dict[str, Any],
    hypothesis: dict[str, Any],
) -> str:
    return _text(
        narrative.get("why"),
        _text(
            interpretation.get("why"),
            _text(hypothesis.get("why_this_matters"), _text(plan.get("why"))),
        ),
    )


def _priority(hypothesis: dict[str, Any], interpretation: dict[str, Any]) -> float:
    raw = hypothesis.get("priority", interpretation.get("confidence", 0.5))
    return max(0.0, min(float(raw) if isinstance(raw, int | float) else 0.5, 1.0))


def _record_at(items: list[dict[str, Any]], index: int) -> dict[str, Any]:
    return items[index] if index < len(items) else {}


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


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _text(value: Any, fallback: str = "") -> str:
    return value.strip() if isinstance(value, str) and value.strip() else fallback


def _compact(values: list[Any]) -> list[str]:
    return sorted({value.strip() for value in values if isinstance(value, str) and value.strip()})


def _dump(value: Any) -> dict[str, Any]:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return value
    return {}


def _stable_suffix(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode("utf-8")).hexdigest()[:12]
