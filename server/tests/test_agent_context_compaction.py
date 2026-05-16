from __future__ import annotations

import json


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


def test_business_overview_payload_stays_small_for_wide_workbooks() -> None:
    from app.agent_plane.context import business_overview_payload
    from app.agent_plane.contracts import AssetEvidence, CanonicalContextPack, FieldEvidence

    assets = []
    for asset_index in range(40):
        fields = [
            FieldEvidence(
                field_id=f"field-{asset_index}-{field_index}",
                asset_id=f"asset-{asset_index}",
                name=f"Very Detailed Operational Field {asset_index} {field_index}",
                ordinal=field_index,
                storage_type="varchar",
                observed_type="text",
                nullable=True,
                sample_values=[
                    "long historical cell value that should be trimmed before reaching the model",
                    "another value",
                    "third value",
                ],
                profile={
                    "profiler": {
                        "candidates": [{"kind": "measure" if field_index % 7 == 0 else "label", "confidence": 0.7}],
                    }
                },
            )
            for field_index in range(120)
        ]
        assets.append(
            AssetEvidence(
                asset_id=f"asset-{asset_index}",
                data_source_id="source-1",
                snapshot_id="snapshot-1",
                asset_key=f"tab_{asset_index}",
                qualified_name=f"sheet__tab_{asset_index}",
                storage_table=f"sheet__tab_{asset_index}",
                label=f"Sheet Tab {asset_index}",
                asset_type="table",
                row_count=1000,
                field_count=len(fields),
                profile={
                    "profiler": {
                        "measure_field_ids": [f"field-{asset_index}-{index}" for index in range(0, 60, 7)],
                        "label_field_ids": [f"field-{asset_index}-1"],
                    }
                },
                fields=fields,
            )
        )
    context = CanonicalContextPack(
        organization_id="org-1",
        snapshots=[],
        assets=assets,
        graph_edges=[],
        memories=[],
    )

    payload = business_overview_payload(context)
    encoded = json.dumps(payload, separators=(",", ":"), sort_keys=True)

    assert len(payload["assets"]) == 16
    assert all(len(asset["fields"]) <= 12 for asset in payload["assets"])
    assert len(encoded) < 80_000


def test_relationship_mapper_payload_stays_small_for_wide_workbooks() -> None:
    from app.agent_plane.context import relationship_mapper_payload
    from app.agent_plane.contracts import (
        AssetEvidence,
        AssetRole,
        BusinessModel,
        CanonicalContextPack,
        FieldEvidence,
        FieldRole,
        GraphEdgeEvidence,
    )

    assets = []
    asset_roles = []
    field_roles = []
    graph_edges = []
    for asset_index in range(40):
        asset_id = f"asset-{asset_index}"
        fields = [
            FieldEvidence(
                field_id=f"field-{asset_index}-{field_index}",
                asset_id=asset_id,
                name=f"Detailed Field {asset_index} {field_index}",
                ordinal=field_index,
                storage_type="varchar",
                observed_type="text",
                nullable=True,
                sample_values=["long sample value that should not be carried into relationship mapper"],
            )
            for field_index in range(120)
        ]
        assets.append(
            AssetEvidence(
                asset_id=asset_id,
                data_source_id="source-1",
                snapshot_id="snapshot-1",
                asset_key=f"tab_{asset_index}",
                qualified_name=f"sheet__tab_{asset_index}",
                storage_table=f"sheet__tab_{asset_index}",
                label=f"Sheet Tab {asset_index}",
                asset_type="table",
                row_count=1000,
                field_count=len(fields),
                fields=fields,
            )
        )
        asset_roles.append(
            AssetRole(
                asset_id=asset_id,
                role="records",
                entity_type=f"entity_{asset_index}",
                label=f"Sheet Tab {asset_index}",
                tags=["source"],
                why="A compact reason that should be trimmed if too long.",
                confidence=0.8,
            )
        )
        for field_index in range(120):
            role = "identifier" if field_index % 11 == 0 else "measure"
            field_roles.append(
                FieldRole(
                    field_id=f"field-{asset_index}-{field_index}",
                    asset_id=asset_id,
                    field_name=f"Detailed Field {asset_index} {field_index}",
                    semantic_type="identifier" if role == "identifier" else "amount",
                    role=role,
                    why="This role was inferred from compact profiler evidence.",
                    confidence=0.7,
                )
            )

    for edge_index in range(160):
        left_asset = edge_index % 40
        right_asset = (edge_index + 1) % 40
        graph_edges.append(
            GraphEdgeEvidence(
                edge_id=f"edge-{edge_index}",
                snapshot_id="snapshot-1",
                subject_type="canonical_field",
                subject_id=f"canonical_field:field-{left_asset}-0",
                predicate="RELATIONSHIP_CANDIDATE",
                object_type="canonical_field",
                object_id=f"canonical_field:field-{right_asset}-0",
                status="active",
                confidence=0.9,
                created_by="data_profiler_v1",
                evidence={
                    "left_asset_id": f"asset-{left_asset}",
                    "left_field_id": f"field-{left_asset}-0",
                    "right_asset_id": f"asset-{right_asset}",
                    "right_field_id": f"field-{right_asset}-0",
                    "cardinality": "many_to_many",
                    "overlap_ratio": 0.8,
                    "shared_value_count": 200,
                    "sample_shared_values": ["Acme", "Globex", "Very long shared value" * 20],
                    "reasons": ["High value overlap", "Compatible profiler roles"],
                },
            )
        )
    graph_edges.append(
        GraphEdgeEvidence(
            edge_id="lineage-edge",
            snapshot_id="snapshot-1",
            subject_type="canonical_asset",
            subject_id="canonical_asset:asset-1",
            predicate="HAS_FIELD",
            object_type="canonical_field",
            object_id="canonical_field:field-1-1",
            status="active",
            confidence=1.0,
            created_by="canonicalizer",
            evidence={"large": "lineage edge should not be included" * 100},
        )
    )
    context = CanonicalContextPack(
        organization_id="org-1",
        snapshots=[],
        assets=assets,
        graph_edges=graph_edges,
        memories=[],
    )
    business_model = BusinessModel(
        paragraph="A compact business summary.",
        business_kind="operations",
        entities=[],
        primary_kpis=[],
        confidence=0.8,
    )

    payload = relationship_mapper_payload(
        context,
        business_model=business_model,
        asset_roles=asset_roles,
        field_roles=field_roles,
    )
    encoded = json.dumps(payload, separators=(",", ":"), sort_keys=True)

    assert len(payload["graph_edges"]) == 40
    assert all(edge["predicate"] == "RELATIONSHIP_CANDIDATE" for edge in payload["graph_edges"])
    assert len(payload["field_roles"]) <= 480
    assert len(encoded) < 95_000
