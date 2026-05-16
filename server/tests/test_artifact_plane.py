from __future__ import annotations

from uuid import uuid4


def _run(mode: str = "scan") -> dict:
    run_id = str(uuid4())
    return {
        "run_id": run_id,
        "mode": mode,
        "organization_id": str(uuid4()),
        "question": "Which customers need attention?" if mode == "ask" else None,
        "status": "completed",
        "started_at": "2026-05-16T08:00:00+00:00",
        "completed_at": "2026-05-16T08:01:00+00:00",
        "context_summary": {
            "asset_count": 2,
            "field_count": 10,
            "graph_edge_count": 1,
            "row_count": 42,
        },
        "brief": {
            "headline": "Today needs follow-up",
            "summary_points": ["One revenue cohort is warm but inactive."],
            "urgent_artifact_ids": [],
            "why": "The run found a high-confidence follow-up cohort.",
        },
        "business_view": {
            "headline": "Commerce operating view",
            "summary": "Baseflo generated one operating view.",
            "why": "Generated from semantic roles and materialized evidence.",
            "confidence": 0.8,
            "generated_from": {"asset_count": 2, "row_count": 42},
            "sections": [
                {
                    "section_id": "receivables",
                    "kind": "receivables",
                    "title": "Receivables",
                    "description": "Pending amounts and follow-up parties.",
                    "why_built": (
                        "Because this data has party names and pending amounts, "
                        "Baseflo built Receivables."
                    ),
                    "confidence": 0.8,
                    "tags": ["receivables"],
                    "metrics": [],
                    "source_asset_ids": ["customers"],
                    "field_refs": ["customers.pending_amount"],
                    "graph_refs": ["warm_inactive_customers"],
                    "insight_refs": ["insight:warm_inactive_customers"],
                    "table_refs": ["table:warm_inactive_customers"],
                    "chart_refs": [],
                    "action_refs": ["action:a1"],
                    "suggested_questions": ["Which parties have the highest pending amount?"],
                    "drilldowns": [],
                }
            ],
            "entity_views": [],
        },
        "business_surfaces": {
            "headline": "1 generated operating surface",
            "summary": "Baseflo mined 2 candidate views, 1 cohort, and 2 action packs.",
            "why": "Generated from semantic roles and execution evidence.",
            "algorithms": ["semantic_surface_detection", "cube_rollup"],
            "confidence": 0.8,
            "generated_from": {"row_count": 42},
            "surfaces": [
                {
                    "surface_id": "receivables",
                    "kind": "receivables",
                    "title": "Receivables Workbench",
                    "description": "Pending amounts and parties.",
                    "entity": "party",
                    "why_built": "Because this data has pending amounts.",
                    "source_asset_ids": ["customers"],
                    "field_refs": ["customers.pending_amount"],
                    "graph_refs": ["warm_inactive_customers"],
                    "dimensions": [],
                    "measures": [],
                    "candidate_views": [],
                    "cohorts": [],
                    "action_packs": [],
                    "confidence": 0.8,
                }
            ],
            "insight_graph": {"nodes": [], "edges": []},
        },
        "semantic_layer": {
            "entities": [
                {
                    "entity_id": "customer",
                    "name": "customer",
                    "plural": "customers",
                    "description": "Customer records.",
                    "primary_asset_id": "customers",
                    "source_asset_ids": ["customers"],
                    "field_refs": ["customers.email"],
                    "why": "Customers were identified from connected roles.",
                    "confidence": 0.82,
                }
            ],
            "dimensions": [],
            "measures": [],
            "metrics": [],
            "surfaces": [],
            "generated_from": {"field_role_count": 1},
            "confidence": 0.82,
        },
        "chart_grammar": {
            "charts": [
                {
                    "chart_id": "chart-warm-inactive",
                    "title": "Warm inactive customers",
                    "why": "A table keeps the customers inspectable.",
                    "data_ref": "warm_inactive_customers",
                    "mark": "text",
                    "vega_lite": {"data": {"values": []}, "mark": "text"},
                    "lineage_refs": ["customers.email"],
                }
            ],
            "generated_from": {"chart_spec_count": 1},
        },
        "insight_ranking": {
            "ranked": [
                {
                    "rank": 1,
                    "item_id": "insight:warm_inactive_customers",
                    "item_kind": "insight",
                    "title": "7 warm customers have not reordered.",
                    "score": 0.8,
                    "score_breakdown": {
                        "money": 0.4,
                        "volume": 0.3,
                        "deviation": 0.7,
                        "actionability": 0.9,
                        "confidence": 0.91,
                    },
                    "why_ranked": "Ranked here because actionability is the strongest signal.",
                    "refs": {"graph_id": "warm_inactive_customers"},
                    "tags": ["insight"],
                }
            ],
            "generated_from": {"candidate_count": 1},
            "scoring_version": "baseflo_ranker_v1",
        },
        "entity_resolution": {
            "plans": [
                {
                    "plan_id": "er:receivables",
                    "surface_id": "receivables",
                    "view_id": "receivables:entity_resolution:party",
                    "entity": "party",
                    "link_type": "link_only",
                    "fields": [],
                    "blocking_fields": [],
                    "threshold_match_probability": 0.85,
                    "why": "Match parties.",
                    "engine": "splink",
                }
            ],
            "executions": [{"plan_id": "er:receivables", "status": "planned"}],
            "generated_from": {"engine": "splink"},
        },
        "knowledge_graph": {
            "status": "completed",
            "backend": "kuzu",
            "graph_path": "/tmp/baseflo.kuzu",
            "node_count": 3,
            "edge_count": 2,
            "query_examples": [],
            "error": None,
        },
        "lineage": {
            "runs": [
                {
                    "run_id": f"{run_id}:warm_inactive_customers",
                    "event_type": "COMPLETE",
                    "event_time": "2026-05-16T08:01:00+00:00",
                    "job": {"namespace": "baseflo", "name": "analysis_graph:warm_inactive_customers", "facets": {}},
                    "inputs": [],
                    "outputs": [],
                    "fields": [],
                    "column_lineage": [],
                    "facets": {},
                }
            ],
            "datasets": [],
            "generated_from": {"execution_count": 1},
        },
        "patterns": {
            "hypotheses": [
                {
                    "hypothesis_id": "h1",
                    "pattern_type": "relationship_gap",
                    "target_entity": "customer",
                    "target_asset_id": "customers",
                    "question": "Which customers are warm but inactive?",
                    "why_this_matters": "Warm inactive customers are likely recoverable.",
                    "priority": 0.86,
                }
            ]
        },
        "executions": [
            {
                "graph_id": "warm_inactive_customers",
                "hypothesis_id": "h1",
                "status": "completed",
                "plan": {
                    "graph_id": "warm_inactive_customers",
                    "hypothesis_id": "h1",
                    "operators": [],
                    "output": "result",
                    "audience": {"entity": "customer"},
                    "why": "Find customers with engagement but no recent revenue.",
                },
                "result": {
                    "graph_id": "warm_inactive_customers",
                    "row_count": 7,
                    "result_preview": [{"customer": "Niharini", "days_since_order": 60}],
                    "lineage": [{"field_id": "customers.email"}],
                },
            }
        ],
        "interpretations": [
            {
                "claim": "7 warm customers have not reordered.",
                "why": "They engaged recently but have no recent orders.",
                "confidence": 0.91,
            }
        ],
        "chart_specs": [
            {
                "artifact_id": "chart-warm-inactive",
                "viz_type": "table",
                "title": "Warm inactive customers",
                "why": "A table keeps the customers inspectable.",
                "data_ref": "warm_inactive_customers",
            }
        ],
        "action_batches": [
            {
                "actions": [
                    {
                        "action_id": "a1",
                        "action_type": "email_draft",
                        "title": "Draft winback email",
                        "why": "The cohort is warm enough for a direct follow-up.",
                        "why_now": "They have recent engagement but no recent orders.",
                        "capability_required": "email.draft",
                        "execution_mode": "prepare_for_user",
                        "approval_scope": {"requires_user_approval": True},
                        "risk": "May annoy customers if sent too often.",
                    }
                ]
            }
        ],
        "narratives": [
            {
                "headline": "7 warm customers need a nudge",
                "summary": "These customers are engaged but inactive.",
                "why": "The statement is grounded in the execution result.",
                "style": "brief",
            }
        ],
        "errors": [],
    }


def test_artifact_plane_assembles_ui_ready_artifacts_from_run() -> None:
    from app.artifact_plane import assemble_operating_artifacts

    drafts = assemble_operating_artifacts(_run())
    by_kind = {draft.kind for draft in drafts}
    by_key = {draft.artifact_key: draft for draft in drafts}

    assert {
        "brief",
        "business_view",
        "business_surfaces",
        "semantic_layer",
        "chart_grammar",
        "insight_ranking",
        "entity_resolution",
        "knowledge_graph",
        "insight",
        "inbox_item",
        "table",
        "chart",
        "lineage",
        "audience",
        "action",
        "run_summary",
    }.issubset(by_kind)
    assert by_key["insight:warm_inactive_customers"].why
    assert by_key["business_view:2026-05-16"].payload["sections"][0]["section_id"] == "receivables"
    assert by_key["business_surfaces:2026-05-16"].payload["surfaces"][0]["kind"] == "receivables"
    assert by_key["semantic_layer:2026-05-16"].payload["semantic_layer"]["entities"][0]["entity_id"] == "customer"
    assert by_key["chart_grammar:2026-05-16"].payload["charts"][0]["chart_id"] == "chart-warm-inactive"
    assert by_key["insight_ranking:2026-05-16"].payload["ranked"][0]["item_id"] == "insight:warm_inactive_customers"
    assert by_key["entity_resolution:2026-05-16"].payload["plans"][0]["engine"] == "splink"
    assert by_key["knowledge_graph:2026-05-16"].payload["knowledge_graph"]["backend"] == "kuzu"
    assert by_key["lineage_package:2026-05-16"].payload["lineage"]["generated_from"]["execution_count"] == 1
    assert by_key["inbox:warm_inactive_customers"].payload["insight_key"] == (
        "insight:warm_inactive_customers"
    )
    assert by_key["action:a1"].payload["action"]["execution_mode"] == "prepare_for_user"


def test_artifact_plane_creates_ask_answer_artifact_for_ask_runs() -> None:
    from app.artifact_plane import assemble_operating_artifacts

    drafts = assemble_operating_artifacts(_run(mode="ask"))

    ask = next(draft for draft in drafts if draft.kind == "ask_answer")
    assert ask.title == "Which customers need attention?"
    assert "materialized analysis results" in ask.why
