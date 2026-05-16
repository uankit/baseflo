from __future__ import annotations


def test_memory_candidates_capture_stable_business_semantics_only() -> None:
    from app.agent_plane.contracts import (
        AssetRole,
        BusinessEntity,
        BusinessGraph,
        BusinessKpi,
        BusinessModel,
        FieldRole,
    )
    from app.memory_plane import candidates_from_agent_artifacts

    candidates = candidates_from_agent_artifacts(
        business_model=BusinessModel(
            paragraph="The business sells through connected bills and inventory records.",
            business_kind="commerce",
            entities=[
                BusinessEntity(
                    name="party",
                    plural="parties",
                    description="People or firms appearing in bill records.",
                    primary_asset_id="asset-bills",
                )
            ],
            primary_kpis=[
                BusinessKpi(
                    name="Pending Amount",
                    description="Amount still pending against parties.",
                    field_refs=["field-pending"],
                    source_asset_ids=["asset-bills"],
                )
            ],
            confidence=0.9,
        ),
        asset_roles=[
            AssetRole(
                asset_id="asset-bills",
                role="billing_event",
                entity_type="party",
                label="Bills",
                why="Rows describe bills and pending amounts.",
                confidence=0.88,
            )
        ],
        field_roles=[
            FieldRole(
                field_id="field-pending",
                asset_id="asset-bills",
                field_name="PENDING",
                semantic_type="money",
                role="measure",
                measure_kind="pending_amount",
                why="Values behave like pending money amounts.",
                confidence=0.86,
            ),
            FieldRole(
                field_id="field-unknown",
                asset_id="asset-bills",
                field_name="MISC",
                semantic_type="text",
                role="unknown",
                why="Not enough evidence.",
                confidence=0.95,
            ),
        ],
        business_graph=BusinessGraph(nodes=[], edges=[]),
    )

    keys = {candidate.key for candidate in candidates}

    assert "business_summary" in keys
    assert "business_entity:party" in keys
    assert "asset_role:asset-bills" in keys
    assert "field_role:field-pending" in keys
    assert "field_role:field-unknown" not in keys
    assert all(candidate.statement for candidate in candidates)


def test_memory_candidate_key_rejects_spaces() -> None:
    import pytest

    from app.memory_plane import MemoryCandidate

    with pytest.raises(ValueError):
        MemoryCandidate(
            key="bad key",
            kind="glossary",
            scope="org",
            statement="This should fail.",
            confidence=0.9,
        )
