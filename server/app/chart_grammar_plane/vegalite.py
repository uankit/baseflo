"""Convert Baseflo chart specs into typed Vega-Lite specs."""

from __future__ import annotations

from typing import Any

from app.chart_grammar_plane.contracts import ChartGrammarPackage, ChartMark, VegaLiteChart


def build_chart_grammar(run: Any) -> ChartGrammarPackage:
    run_data = _dump(run)
    executions = {
        _text(execution.get("graph_id")): execution
        for execution in _record_list(run_data.get("executions"))
    }
    charts: list[VegaLiteChart] = []
    for index, chart in enumerate(_record_list(run_data.get("chart_specs"))):
        data_ref = _text(chart.get("data_ref"))
        execution = executions.get(data_ref, {})
        result = _record(execution.get("result"))
        values = _record_list(result.get("result_preview"))
        chart_id = _text(chart.get("artifact_id"), f"chart:{data_ref or index}")
        mark = _mark(_text(chart.get("viz_type")))
        x_field, y_field = _fields(chart, values)
        spec = _vega_lite_spec(chart, values, mark, x_field, y_field)
        charts.append(
            VegaLiteChart(
                chart_id=chart_id,
                title=_text(chart.get("title"), "Chart"),
                why=_text(chart.get("why"), "Vega-Lite chart generated from materialized evidence."),
                data_ref=data_ref,
                mark=mark,
                vega_lite=spec,
                lineage_refs=_unique(
                    _text(item.get("field_id"))
                    for item in _record_list(result.get("lineage"))
                ),
            )
        )
    return ChartGrammarPackage(
        charts=charts,
        generated_from={
            "chart_spec_count": len(_record_list(run_data.get("chart_specs"))),
            "execution_count": len(executions),
        },
    )


def _vega_lite_spec(
    chart: dict[str, Any],
    values: list[dict[str, Any]],
    mark: str,
    x_field: str | None,
    y_field: str | None,
) -> dict[str, Any]:
    spec: dict[str, Any] = {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "title": _text(chart.get("title"), "Chart"),
        "data": {"values": values},
        "mark": mark,
        "encoding": {},
    }
    if mark == "text":
        spec["mark"] = {"type": "text", "align": "left"}
        spec["encoding"] = {"text": {"field": x_field or _first_key(values), "type": "nominal"}}
        return spec
    if x_field:
        spec["encoding"]["x"] = {"field": x_field, "type": _encoding_type(values, x_field)}
    if y_field:
        spec["encoding"]["y"] = {"field": y_field, "type": _encoding_type(values, y_field)}
    if not spec["encoding"] and values:
        first = _first_key(values)
        spec["encoding"] = {"x": {"field": first, "type": _encoding_type(values, first)}}
    if mark == "bar" and x_field and y_field:
        spec["encoding"]["tooltip"] = [
            {"field": x_field, "type": _encoding_type(values, x_field)},
            {"field": y_field, "type": _encoding_type(values, y_field)},
        ]
    return spec


def _fields(chart: dict[str, Any], values: list[dict[str, Any]]) -> tuple[str | None, str | None]:
    x_field = _text(chart.get("x_field")) or None
    y_field = _text(chart.get("y_field")) or None
    if x_field or y_field:
        return x_field, y_field
    if not values:
        return None, None
    keys = list(values[0])
    number_key = next((key for key in keys if _is_number(values[0].get(key))), None)
    label_key = next((key for key in keys if key != number_key), None)
    return label_key or keys[0], number_key


def _mark(viz_type: str) -> ChartMark:
    marks: dict[str, ChartMark] = {
        "bar": "bar",
        "line": "line",
        "scatter": "circle",
        "metric": "text",
        "table": "text",
    }
    return marks.get(viz_type, "bar")


def _encoding_type(values: list[dict[str, Any]], field: str) -> str:
    sample = next((row.get(field) for row in values if row.get(field) is not None), None)
    if _is_number(sample):
        return "quantitative"
    if _looks_temporal(sample):
        return "temporal"
    return "nominal"


def _first_key(values: list[dict[str, Any]]) -> str:
    return next(iter(values[0]), "value") if values else "value"


def _is_number(value: Any) -> bool:
    if isinstance(value, int | float):
        return True
    try:
        float(str(value).replace(",", "").replace("₹", ""))
        return True
    except (TypeError, ValueError):
        return False


def _looks_temporal(value: Any) -> bool:
    text = str(value)
    return len(text) >= 10 and text[4:5] == "-" and text[7:8] == "-"


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
