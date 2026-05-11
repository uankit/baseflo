"""Unit tests for artifact types and validation."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.agents.source_agent.types import SourceAgentOutput
from app.api.v1.routes.artifacts import _unwrap_legacy_payload
from app.artifacts.types import (
    Artifact,
    ArtifactHeader,
    ArtifactProvenance,
    EntityGraph,
    EntitySourceMapping,
    KPIResult,
    RecommendedAction,
    SourceColumn,
    SourceMap,
    SourceTable,
)


class TestSourceMap:
    def test_valid_source_map(self) -> None:
        col = SourceColumn(
            name="customer_id",
            semantic_type="IDENTITY",
            physical_type="UUID",
            nullable=False,
            sample_values=["abc-123"],
        )
        table = SourceTable(
            name="customers",
            source_name="customers",
            columns=[col],
            primary_key=["customer_id"],
        )
        sm = SourceMap(
            connector_id=uuid4(),
            connector_kind="postgres",
            tables=[table],
        )
        assert sm.connector_kind == "postgres"
        assert len(sm.tables) == 1
        assert sm.tables[0].primary_key == ["customer_id"]

    def test_invalid_semantic_type(self) -> None:
        with pytest.raises(ValidationError):
            SourceColumn(
                name="x",
                semantic_type="INVALID",  # type: ignore[arg-type]
                physical_type="TEXT",
                nullable=True,
            )

    def test_source_agent_output_validation(self) -> None:
        sm = SourceMap(
            connector_id=uuid4(),
            connector_kind="csv",
            tables=[
                SourceTable(
                    name="orders",
                    source_name="orders",
                    columns=[
                        SourceColumn(
                            name="id",
                            semantic_type="IDENTITY",
                            physical_type="UUID",
                            nullable=False,
                        )
                    ],
                    primary_key=["id"],
                )
            ],
        )
        out = SourceAgentOutput(source_map=sm)
        assert out.confidence == 0.9


class TestEntityGraph:
    def test_entity_graph_validation(self) -> None:
        mapping = EntitySourceMapping(
            source="stripe",
            source_id_field="id",
            source_id_value="cus_123",
            canonical_id=uuid4(),
            confidence=0.95,
        )
        graph = EntityGraph(entities=[], unresolved=[mapping])
        assert len(graph.unresolved) == 1

    def test_legacy_entity_graph_artifact_unwraps(self) -> None:
        from app.agents.reconciliation_agent.types import ReconciliationAgentOutput

        graph = EntityGraph(entities=[], unresolved=[])
        wrapped = ReconciliationAgentOutput(entity_graph=graph, confidence=0.74)

        assert _unwrap_legacy_payload("entity_graph", wrapped) == graph


class TestInsightBoard:
    def test_kpi_sql_must_start_with_select(self) -> None:
        kpi = KPIResult(
            kpi_id="revenue",
            name="Total Revenue",
            value=48000,
            sql="SELECT SUM(amount) FROM payments",
        )
        assert kpi.sql is not None

    def test_recommended_action_types(self) -> None:
        action = RecommendedAction(
            action_id="a1",
            action_type="alert",
            title="Low inventory",
            description="Stock is below threshold",
            auto_execute=False,
            requires_approval=True,
        )
        assert action.action_type == "alert"


class TestArtifact:
    def test_artifact_immutable(self) -> None:
        header = ArtifactHeader(
            artifact_id=uuid4(),
            project_id=uuid4(),
            artifact_type="source_map",
            version=1,
            produced_by="SourceAgent",
            created_at=datetime.now(UTC),
        )
        prov = ArtifactProvenance(
            agent_name="SourceAgent",
            started_at=datetime.now(UTC),
            finished_at=datetime.now(UTC),
        )
        sm = SourceMap(
            connector_id=uuid4(),
            connector_kind="stripe",
            tables=[],
        )
        art = Artifact(header=header, payload=sm, provenance=prov)
        assert art.header.version == 1
