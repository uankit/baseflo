from __future__ import annotations


def test_semantic_layer_governs_entities_fields_metrics_and_surfaces() -> None:
    from app.business_surface_plane import mine_business_surfaces
    from app.semantic_layer import build_semantic_layer
    from tests.test_business_surface_plane import _receivables_run

    run = _receivables_run()
    run["business_model"] = {
        "paragraph": "This business tracks receivables by party.",
        "business_kind": "trading",
        "entities": [
            {
                "name": "party",
                "plural": "parties",
                "description": "Customers or vendors with bill balances.",
                "primary_asset_id": "bill_detail",
                "related_asset_ids": ["payments"],
            }
        ],
        "primary_kpis": [],
        "confidence": 0.82,
    }
    run["business_surfaces"] = mine_business_surfaces(run)

    package = build_semantic_layer(run)

    assert any(entity.entity_id == "party" for entity in package.entities)
    assert any(dimension.kind == "party" for dimension in package.dimensions)
    assert any(measure.kind == "pending_amount" for measure in package.measures)
    assert package.metrics
    assert package.surfaces
    assert package.surfaces[0].measure_refs
    assert package.generated_from["surface_count"] == 1
