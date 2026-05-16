from __future__ import annotations


def test_insight_ranking_scores_materialized_insights_and_surfaces() -> None:
    from app.business_surface_plane import mine_business_surfaces
    from app.insight_ranking_plane import rank_operating_insights
    from tests.test_business_surface_plane import _receivables_run

    run = _receivables_run()
    run["business_surfaces"] = mine_business_surfaces(run)
    run["interpretations"] = [
        {
            "claim": "500 parties have pending balances.",
            "why": "The execution found parties with non-zero pending amount.",
            "confidence": 0.91,
        }
    ]
    run["executions"][0]["result"]["result_preview"] = [
        {"party_name": "Acme", "pending_amount": 250000},
        {"party_name": "Beta", "pending_amount": 100000},
    ]

    package = rank_operating_insights(run)

    assert package.ranked
    assert any(item.item_kind == "insight" for item in package.ranked)
    assert any(item.item_kind == "action_pack" for item in package.ranked)
    assert package.ranked == sorted(package.ranked, key=lambda item: item.score, reverse=True)
    assert package.ranked[0].why_ranked
    assert package.generated_from["candidate_count"] >= 3
