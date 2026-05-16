from __future__ import annotations


def test_compact_context_payload_bounds_samples_profiles_and_previews() -> None:
    from app.agent_plane.context import compact_asset_payload, compact_context_payload
    from app.agent_plane.contracts import AssetEvidence, CanonicalContextPack, FieldEvidence

    long_text = "x" * 500
    field = FieldEvidence(
        field_id="field-1",
        asset_id="asset-1",
        name="VERY LONG CUSTOMER NOTES",
        ordinal=1,
        storage_type="varchar",
        observed_type="text",
        nullable=True,
        sample_values=[long_text, "second", "third", "fourth", "fifth"],
        profile={
            "profiler": {
                "row_count": 5000,
                "non_null_rate": 0.8,
                "distinct_count": 4900,
                "uniqueness_rate": 0.98,
                "top_values": [{"value": long_text, "count": 100}],
                "candidates": [
                    {"kind": "label", "confidence": 0.9, "reasons": [long_text, "useful name"]}
                ],
                "quality_flags": ["long_text"],
            }
        },
    )
    asset = AssetEvidence(
        asset_id="asset-1",
        data_source_id="source-1",
        snapshot_id="snapshot-1",
        asset_key="customers",
        qualified_name="customers",
        storage_table="customers",
        label="Customers",
        asset_type="table",
        row_count=5000,
        field_count=1,
        profile={"profiler": {"density": 0.8, "measure_field_ids": ["field-1"]}},
        fields=[field],
        preview_rows=[{f"col_{index}": long_text for index in range(20)} for _row in range(5)],
    )
    context = CanonicalContextPack(
        organization_id="org-1",
        snapshots=[],
        assets=[asset],
        graph_edges=[],
        memories=[],
    )

    context_payload = compact_context_payload(context)
    compact_asset = context_payload["assets"][0]

    assert "preview_rows" not in compact_asset
    assert len(compact_asset["fields"][0]["sample_values"]) == 4
    assert len(compact_asset["fields"][0]["sample_values"][0]) < len(long_text)
    assert "top_values" not in compact_asset["fields"][0]["profile"]

    asset_payload = compact_asset_payload(asset, include_preview_rows=True)
    assert len(asset_payload["preview_rows"]) == 2
    assert len(asset_payload["preview_rows"][0]) == 12
