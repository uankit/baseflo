from __future__ import annotations


def test_lineage_package_captures_execution_and_package_lineage() -> None:
    from app.lineage_plane import build_lineage_package

    package = build_lineage_package(
        {
            "run_id": "run-1",
            "semantic_layer": {"entities": [], "metrics": []},
            "business_surfaces": {"surfaces": []},
            "chart_grammar": {"charts": []},
            "insight_ranking": {"ranked": []},
            "executions": [
                {
                    "graph_id": "pending_by_party",
                    "hypothesis_id": "h1",
                    "status": "completed",
                    "plan": {
                        "graph_id": "pending_by_party",
                        "hypothesis_id": "h1",
                        "operators": [
                            {"op": "source", "id": "bills", "asset_id": "bill_detail"},
                            {
                                "op": "select",
                                "id": "selected",
                                "input": "bills",
                                "field_ids": [
                                    "bill_detail.party_name",
                                    "bill_detail.pending_amount",
                                ],
                            },
                        ],
                        "output": "selected",
                        "why": "Find pending parties.",
                    },
                    "result": {
                        "graph_id": "pending_by_party",
                        "row_count": 2,
                        "lineage": [
                            {
                                "alias": "pending_amount",
                                "field_id": "bill_detail.pending_amount",
                            }
                        ],
                    },
                }
            ],
        }
    )

    names = {dataset.name for dataset in package.datasets}
    assert "canonical_asset:bill_detail" in names
    assert "analysis_result:pending_by_party" in names
    assert "package:semantic_layer" in names
    assert package.runs[0].job.name == "analysis_graph:pending_by_party"
    assert package.runs[0].column_lineage[0].output_field == "pending_amount"
    assert package.generated_from["execution_count"] == 1
