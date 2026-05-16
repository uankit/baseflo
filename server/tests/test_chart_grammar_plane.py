from __future__ import annotations


def test_chart_grammar_emits_vega_lite_from_materialized_result_rows() -> None:
    from app.chart_grammar_plane import build_chart_grammar

    package = build_chart_grammar(
        {
            "executions": [
                {
                    "graph_id": "pending_by_party",
                    "status": "completed",
                    "result": {
                        "row_count": 2,
                        "result_preview": [
                            {"party_name": "Acme", "pending_amount": 12000},
                            {"party_name": "Beta", "pending_amount": 8000},
                        ],
                        "lineage": [
                            {"field_id": "bill_detail.party_name"},
                            {"field_id": "bill_detail.pending_amount"},
                        ],
                    },
                }
            ],
            "chart_specs": [
                {
                    "artifact_id": "chart-pending",
                    "viz_type": "bar",
                    "title": "Pending by party",
                    "why": "A bar chart compares pending value by party.",
                    "data_ref": "pending_by_party",
                }
            ],
        }
    )

    chart = package.charts[0]
    assert chart.mark == "bar"
    assert chart.vega_lite["$schema"].endswith("/v5.json")
    assert chart.vega_lite["data"]["values"][0]["party_name"] == "Acme"
    assert chart.vega_lite["encoding"]["x"]["field"] == "party_name"
    assert chart.vega_lite["encoding"]["y"]["field"] == "pending_amount"
    assert "bill_detail.pending_amount" in chart.lineage_refs
