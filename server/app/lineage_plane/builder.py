"""Build OpenLineage-style run and column lineage."""

from __future__ import annotations

from typing import Any

from app.lineage_plane.contracts import (
    LineageColumnMapping,
    LineageDataset,
    LineageField,
    LineageJob,
    LineagePackage,
    LineageRun,
)


def build_lineage_package(run: Any) -> LineagePackage:
    run_data = _dump(run)
    datasets: dict[str, LineageDataset] = {}
    lineage_runs: list[LineageRun] = []

    for execution in _record_list(run_data.get("executions")):
        lineage_run = _execution_lineage(run_data, execution)
        lineage_runs.append(lineage_run)
        for dataset in [*lineage_run.inputs, *lineage_run.outputs]:
            datasets[dataset.name] = dataset

    for package_name in (
        "semantic_layer",
        "business_view",
        "business_surfaces",
        "entity_resolution",
        "knowledge_graph",
        "chart_grammar",
        "insight_ranking",
    ):
        artifact = _record(run_data.get(package_name))
        if artifact:
            lineage_run = _package_lineage(run_data, package_name, artifact)
            lineage_runs.append(lineage_run)
            for dataset in [*lineage_run.inputs, *lineage_run.outputs]:
                datasets[dataset.name] = dataset

    return LineagePackage(
        runs=lineage_runs,
        datasets=list(datasets.values()),
        generated_from={
            "execution_count": len(_record_list(run_data.get("executions"))),
            "run_id": _text(run_data.get("run_id")),
        },
    )


def _execution_lineage(run_data: dict[str, Any], execution: dict[str, Any]) -> LineageRun:
    graph_id = _text(execution.get("graph_id"), "unknown_graph")
    plan = _record(execution.get("plan"))
    result = _record(execution.get("result"))
    status = _text(execution.get("status"))
    input_assets = _source_asset_ids(plan)
    input_fields = _plan_field_ids(plan)
    output_name = f"analysis_result:{graph_id}"
    fields = [
        LineageField(
            field_id=field_id,
            asset_id=None,
            role="input",
            facets={"source": "analysis_graph"},
        )
        for field_id in input_fields
    ]
    output_lineage = [
        LineageColumnMapping(
            output_field=_text(item.get("alias"), _text(item.get("field_id"), "output")),
            input_fields=[_text(item.get("field_id"))] if _text(item.get("field_id")) else input_fields,
            transformation="analysis_graph_operator",
        )
        for item in _record_list(result.get("lineage"))
    ]
    return LineageRun(
        run_id=f"{_text(run_data.get('run_id'))}:{graph_id}",
        event_type="COMPLETE" if status == "completed" else "FAIL",
        job=LineageJob(
            name=f"analysis_graph:{graph_id}",
            facets={
                "hypothesis_id": execution.get("hypothesis_id"),
                "operator_count": len(_list(plan.get("operators"))),
            },
        ),
        inputs=[
            LineageDataset(
                name=f"canonical_asset:{asset_id}",
                facets={"asset_id": asset_id},
            )
            for asset_id in input_assets
        ],
        outputs=[
            LineageDataset(
                name=output_name,
                facets={
                    "graph_id": graph_id,
                    "row_count": result.get("row_count", 0),
                    "status": status,
                },
            )
        ],
        fields=fields,
        column_lineage=output_lineage,
        facets={
            "why": plan.get("why"),
            "audience": plan.get("audience", {}),
        },
    )


def _package_lineage(
    run_data: dict[str, Any],
    package_name: str,
    artifact: dict[str, Any],
) -> LineageRun:
    run_id = _text(run_data.get("run_id"))
    execution_outputs = [
        LineageDataset(
            name=f"analysis_result:{_text(execution.get('graph_id'))}",
            facets={"graph_id": execution.get("graph_id")},
        )
        for execution in _record_list(run_data.get("executions"))
        if _text(execution.get("status")) == "completed"
    ]
    return LineageRun(
        run_id=f"{run_id}:{package_name}",
        event_type="COMPLETE",
        job=LineageJob(
            name=f"package:{package_name}",
            facets={"package": package_name},
        ),
        inputs=execution_outputs,
        outputs=[
            LineageDataset(
                name=f"package:{package_name}",
                facets={"payload_keys": sorted(artifact.keys())},
            )
        ],
        facets={"source": "operating_pipeline"},
    )


def _source_asset_ids(plan: dict[str, Any]) -> list[str]:
    return _unique(
        _text(op.get("asset_id"))
        for op in _record_list(plan.get("operators"))
        if _text(op.get("op")) == "source"
    )


def _plan_field_ids(plan: dict[str, Any]) -> list[str]:
    fields: list[str] = []
    for op in _record_list(plan.get("operators")):
        if _text(op.get("op")) == "select":
            fields.extend(_list_of_text(op.get("field_ids")))
        elif _text(op.get("op")) == "filter":
            fields.extend(_text(predicate.get("field_id")) for predicate in _record_list(op.get("predicates")))
        elif _text(op.get("op")) == "join":
            fields.extend([_text(op.get("left_field_id")), _text(op.get("right_field_id"))])
        elif _text(op.get("op")) == "aggregate":
            fields.extend(_list_of_text(op.get("group_by_field_ids")))
            fields.extend(
                _text(measure.get("field_id"))
                for measure in _record_list(op.get("measures"))
                if _text(measure.get("field_id"))
            )
    return _unique(fields)


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


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _list_of_text(value: Any) -> list[str]:
    return _unique(_text(item) for item in _list(value))


def _text(value: Any, fallback: str = "") -> str:
    return value.strip() if isinstance(value, str) and value.strip() else fallback


def _unique(values: Any) -> list[str]:
    result: list[str] = []
    for value in values:
        if not isinstance(value, str):
            continue
        clean = value.strip()
        if clean and clean not in result:
            result.append(clean)
    return result
