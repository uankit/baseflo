from __future__ import annotations


def test_business_view_generates_receivables_from_party_and_pending_fields() -> None:
    from app.business_view_plane import assemble_business_view

    view = assemble_business_view(
        {
            "business_model": {
                "business_kind": "trading",
                "entities": [
                    {
                        "name": "party",
                        "plural": "parties",
                        "description": "Business parties in the ledger.",
                        "primary_asset_id": "bills",
                    }
                ],
            },
            "context_summary": {"asset_count": 1, "field_count": 4, "row_count": 600},
            "asset_roles": [
                {
                    "asset_id": "bills",
                    "role": "ledger",
                    "entity_type": "party",
                    "label": "Bill Detail",
                    "tags": ["bills"],
                    "why": "Rows contain party names, bill amounts, and pending amounts.",
                    "confidence": 0.9,
                }
            ],
            "field_roles": [
                {
                    "field_id": "bills.party_name",
                    "asset_id": "bills",
                    "field_name": "PARTY NAME",
                    "semantic_type": "party_name",
                    "role": "label",
                    "why": "Names repeat like parties.",
                    "confidence": 0.9,
                },
                {
                    "field_id": "bills.pending_amount",
                    "asset_id": "bills",
                    "field_name": "PENDING",
                    "semantic_type": "money",
                    "role": "measure",
                    "measure_kind": "pending_amount",
                    "why": "Numeric pending balances.",
                    "confidence": 0.9,
                },
                {
                    "field_id": "bills.bill_amount",
                    "asset_id": "bills",
                    "field_name": "BILL AMT",
                    "semantic_type": "money",
                    "role": "measure",
                    "measure_kind": "bill_amount",
                    "why": "Numeric bill amounts.",
                    "confidence": 0.9,
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
                    "result": {"row_count": 25, "result_preview": []},
                }
            ],
        }
    )

    receivables = next(section for section in view.sections if section.kind == "receivables")

    assert view.headline == "Trading operating view"
    assert "Because this data has" in receivables.why_built
    assert "pending_amount" in receivables.why_built
    assert "bills.pending_amount" in receivables.field_refs
    assert "pending_by_party" in receivables.graph_refs
    assert "Which parties have the highest pending amount?" in receivables.suggested_questions
    assert view.entity_views[0].entity == "party"


def test_business_view_generates_profit_loss_when_revenue_and_cost_exist() -> None:
    from app.business_view_plane import assemble_business_view

    view = assemble_business_view(
        {
            "business_model": {"business_kind": "commerce", "entities": []},
            "context_summary": {"asset_count": 2, "field_count": 4, "row_count": 200},
            "asset_roles": [
                {
                    "asset_id": "sales",
                    "role": "revenue_event",
                    "entity_type": "order",
                    "label": "Sales",
                    "why": "Rows contain sales.",
                    "confidence": 0.8,
                },
                {
                    "asset_id": "expenses",
                    "role": "spend_event",
                    "entity_type": "expense",
                    "label": "Expenses",
                    "why": "Rows contain costs.",
                    "confidence": 0.8,
                },
            ],
            "field_roles": [
                {
                    "field_id": "sales.revenue",
                    "asset_id": "sales",
                    "field_name": "Revenue",
                    "semantic_type": "money",
                    "role": "measure",
                    "measure_kind": "revenue",
                    "why": "Revenue field.",
                    "confidence": 0.9,
                },
                {
                    "field_id": "expenses.cost",
                    "asset_id": "expenses",
                    "field_name": "Cost",
                    "semantic_type": "money",
                    "role": "measure",
                    "measure_kind": "cost",
                    "why": "Cost field.",
                    "confidence": 0.9,
                },
            ],
            "executions": [],
        }
    )

    profit_loss = next(section for section in view.sections if section.kind == "profit_loss")

    assert "revenue-like signals" in profit_loss.why_built
    assert "cost-like signals" in profit_loss.why_built
    assert "sales.revenue" in profit_loss.field_refs
    assert "expenses.cost" in profit_loss.field_refs
