from __future__ import annotations


def _receivables_run() -> dict:
    return {
        "context_summary": {"asset_count": 2, "field_count": 8, "row_count": 600},
        "business_view": {
            "headline": "Trading operating view",
            "summary": "Generated sections.",
            "why": "Generated from semantic roles.",
            "confidence": 0.8,
            "generated_from": {"row_count": 600},
            "sections": [
                {
                    "section_id": "receivables",
                    "kind": "receivables",
                    "title": "Receivables",
                    "description": "Pending amounts and parties.",
                    "why_built": (
                        "Because this data has party names, bill amounts, "
                        "and pending amounts, Baseflo built Receivables."
                    ),
                    "confidence": 0.88,
                    "tags": ["receivables"],
                    "metrics": [],
                    "source_asset_ids": ["bill_detail", "payments"],
                    "field_refs": [
                        "bill_detail.party_name",
                        "bill_detail.pending_amount",
                        "bill_detail.bill_amount",
                        "bill_detail.email",
                        "payments.party_name",
                    ],
                    "graph_refs": ["pending_by_party"],
                    "insight_refs": [],
                    "table_refs": [],
                    "chart_refs": [],
                    "action_refs": [],
                    "suggested_questions": [],
                    "drilldowns": [],
                }
            ],
            "entity_views": [],
        },
        "asset_roles": [
            {
                "asset_id": "bill_detail",
                "role": "ledger",
                "entity_type": "party",
                "label": "Bill Detail",
                "tags": ["bills"],
                "why": "Rows contain party names and pending amounts.",
                "confidence": 0.9,
            },
            {
                "asset_id": "payments",
                "role": "ledger",
                "entity_type": "party",
                "label": "Payments",
                "tags": ["collections"],
                "why": "Rows contain payment parties.",
                "confidence": 0.8,
            },
        ],
        "field_roles": [
            {
                "field_id": "bill_detail.party_name",
                "asset_id": "bill_detail",
                "field_name": "Party Name",
                "semantic_type": "party_name",
                "role": "label",
                "entity_hint": "party",
                "why": "Names repeat like parties.",
                "confidence": 0.9,
            },
            {
                "field_id": "payments.party_name",
                "asset_id": "payments",
                "field_name": "Party",
                "semantic_type": "party_name",
                "role": "label",
                "entity_hint": "party",
                "why": "Names repeat like parties.",
                "confidence": 0.86,
            },
            {
                "field_id": "bill_detail.pending_amount",
                "asset_id": "bill_detail",
                "field_name": "Pending Amount",
                "semantic_type": "money",
                "role": "measure",
                "measure_kind": "pending_amount",
                "why": "Pending balance.",
                "confidence": 0.94,
            },
            {
                "field_id": "bill_detail.bill_amount",
                "asset_id": "bill_detail",
                "field_name": "Bill Amount",
                "semantic_type": "money",
                "role": "measure",
                "measure_kind": "bill_amount",
                "why": "Bill value.",
                "confidence": 0.9,
            },
            {
                "field_id": "bill_detail.email",
                "asset_id": "bill_detail",
                "field_name": "Email",
                "semantic_type": "email",
                "role": "identifier",
                "entity_hint": "party",
                "why": "Contact field.",
                "confidence": 0.82,
            },
        ],
        "patterns": {
            "hypotheses": [
                {
                    "hypothesis_id": "h1",
                    "pattern_type": "receivable_gap",
                    "target_entity": "party",
                    "question": "Which parties have pending amount?",
                }
            ]
        },
        "executions": [
            {
                "graph_id": "pending_by_party",
                "hypothesis_id": "h1",
                "status": "completed",
                "result": {"row_count": 500, "result_preview": []},
            }
        ],
    }


def test_surface_miner_builds_receivables_workbench_with_bulk_action_packs() -> None:
    from app.business_surface_plane import mine_business_surfaces

    package = mine_business_surfaces(_receivables_run())
    receivables = next(surface for surface in package.surfaces if surface.kind == "receivables")

    assert "cube_rollup" in package.algorithms
    assert "probabilistic_entity_resolution" in package.algorithms
    assert receivables.measures[0].kind == "pending_amount"
    assert any(dimension.kind == "party" for dimension in receivables.dimensions)
    assert any(view.algorithm == "cube_rollup" for view in receivables.candidate_views)
    assert any(view.algorithm == "probabilistic_entity_resolution" for view in receivables.candidate_views)
    assert any(cohort.cohort_id == "receivables:highest_pending" for cohort in receivables.cohorts)
    assert any(action.action_type == "email_draft" for action in receivables.action_packs)
    assert package.insight_graph.nodes
    assert package.insight_graph.edges


def test_surface_miner_falls_back_to_semantic_surfaces_without_business_view() -> None:
    from app.business_surface_plane import mine_business_surfaces

    run = _receivables_run()
    run.pop("business_view")

    package = mine_business_surfaces(run)

    assert any(surface.kind == "receivables" for surface in package.surfaces)
    assert package.generated_from["business_view_section_count"] == 0
