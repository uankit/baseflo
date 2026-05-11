"""Artifact type definitions for the Baseflo agent OS.

Artifacts are immutable, versioned, typed outputs that agents produce
and the deterministic execution layer consumes.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.db.base import Base as DBBase
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import relationship


# ---------------------------------------------------------------------------
# Core artifact primitives
# ---------------------------------------------------------------------------

class ArtifactProvenance(BaseModel):
    """Traceability metadata for every artifact."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    input_artifact_ids: list[UUID] = Field(default_factory=list)
    agent_name: str
    model_name: str | None = None
    prompt_hash: str | None = None
    tokens_prompt: int = 0
    tokens_completion: int = 0
    latency_ms: float = 0.0
    started_at: datetime
    finished_at: datetime


class ArtifactHeader(BaseModel):
    """Lightweight header for listing artifacts without loading full payload."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    artifact_id: UUID
    project_id: UUID
    artifact_type: str
    version: int
    produced_by: str
    created_at: datetime


class Artifact[T](BaseModel):
    """A versioned, typed artifact produced by an agent."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    header: ArtifactHeader
    payload: T
    provenance: ArtifactProvenance


# ---------------------------------------------------------------------------
# SourceMap — output of SourceAgent
# ---------------------------------------------------------------------------

class SourceColumn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    semantic_type: Literal[
        "IDENTITY",
        "MONEY",
        "STATUS",
        "TEMPORAL",
        "PII_EMAIL",
        "PII_PHONE",
        "PII_ADDRESS",
        "PII_NAME",
        "PII_ID_NUMBER",
        "CATEGORY",
        "FREE_TEXT",
        "BOOLEAN",
        "COUNT",
        "DERIVED",
        "UNKNOWN",
    ]
    physical_type: Literal[
        "UUID", "BIGINT", "INT", "TEXT", "VARCHAR", "TIMESTAMPTZ",
        "DATE", "JSONB", "BOOLEAN", "NUMERIC",
    ]
    nullable: bool
    sample_values: list[str] = Field(default_factory=list)
    distinct_count: int | None = None
    null_rate: float | None = None


class SourceTable(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    source_name: str
    row_count: int | None = None
    columns: list[SourceColumn]
    primary_key: list[str] = Field(default_factory=list)
    description: str | None = None


class SourceMap(BaseModel):
    """Understanding of a single data source."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    connector_id: UUID
    connector_kind: str
    tables: list[SourceTable]
    freshness: datetime | None = None
    assumptions: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# EntityGraph — output of ReconciliationAgent
# ---------------------------------------------------------------------------

class EntitySourceMapping(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    source: str
    source_id_field: str
    source_id_value: str
    canonical_id: UUID
    confidence: float = Field(ge=0.0, le=1.0)
    merge_rule: str | None = None


class CanonicalEntity(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    canonical_id: UUID
    entity_kind: str
    display_name: str
    sources: list[EntitySourceMapping]
    authoritative_source: str | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)


class EntityGraph(BaseModel):
    """Cross-source entity reconciliation result."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    entities: list[CanonicalEntity]
    unresolved: list[EntitySourceMapping] = Field(default_factory=list)
    merge_rules: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# SchemaIR — output of SchemaAgent (reuses existing engine schema IR)
# ---------------------------------------------------------------------------

# Re-export the existing well-designed SchemaIR from engines.schema.ir
# to keep compatibility with DDL compiler and validators.
from app.engines.schema.ir import SchemaIR  # noqa: E402


# ---------------------------------------------------------------------------
# InsightBoard — output of InsightAgent
# ---------------------------------------------------------------------------

class KPIResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    kpi_id: str
    name: str
    value: float | int | str | None
    previous_value: float | int | str | None = None
    change_percent: float | None = None
    grain: str | None = None
    time_range: str | None = None
    sql: str | None = None


class SegmentResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    segment_id: str
    name: str
    description: str
    count: int
    criteria_sql: str | None = None
    sample_ids: list[UUID] = Field(default_factory=list)


class ExpectedRange(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    low: float
    high: float


class AnomalyResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    anomaly_id: str
    severity: Literal["low", "medium", "high", "critical"]
    title: str
    description: str
    affected_entity_kind: str | None = None
    affected_count: int | None = None
    metric_name: str | None = None
    expected_range: ExpectedRange | None = None
    actual_value: float | None = None


class RecommendedAction(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    action_id: str
    action_type: Literal["alert", "tag", "export", "webhook"]
    title: str
    description: str
    target_segment_id: str | None = None
    target_entity_kind: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    auto_execute: bool = False
    requires_approval: bool = True


class InsightBoard(BaseModel):
    """Snapshot of business intelligence at a point in time."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kpis: list[KPIResult] = Field(default_factory=list)
    segments: list[SegmentResult] = Field(default_factory=list)
    anomalies: list[AnomalyResult] = Field(default_factory=list)
    recommended_actions: list[RecommendedAction] = Field(default_factory=list)
    narrative: str | None = None
    generated_for_question: str | None = None


# ---------------------------------------------------------------------------
# ActionPlan — deterministic execution payload
# ---------------------------------------------------------------------------

class ActionStep(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    step_id: str
    step_type: Literal[
        "sql_query", "api_call", "email_send", "webhook_post", "tag_update"
    ]
    target_connector_kind: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    depends_on: list[str] = Field(default_factory=list)


class ActionPlan(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    plan_id: UUID
    project_id: UUID
    triggered_by: str
    steps: list[ActionStep]
    estimated_impact: str | None = None


# ---------------------------------------------------------------------------
# Database model for persisting artifacts
# ---------------------------------------------------------------------------

class ArtifactRecord(DBBase):
    """Postgres table for immutable artifact storage."""

    __tablename__ = "artifacts"

    artifact_id = Column(PGUUID(as_uuid=True), primary_key=True)
    project_id = Column(PGUUID(as_uuid=True), ForeignKey("projects.id"), nullable=False, index=True)
    artifact_type = Column(String(64), nullable=False, index=True)
    version = Column(Integer, nullable=False)
    payload = Column(JSONB, nullable=False)
    provenance = Column(JSONB, nullable=False)
    produced_by = Column(String(64), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        {"schema": "public"},
    )


# ---------------------------------------------------------------------------
# Artifact store (repository pattern)
# ---------------------------------------------------------------------------

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from uuid import uuid4


class ArtifactStore:
    """Persistence layer for artifacts."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save[T](self, project_id: UUID, artifact_type: str, payload: T, produced_by: str, provenance: ArtifactProvenance) -> Artifact[T]:
        """Persist a new artifact, auto-incrementing version."""
        latest = await self._session.scalar(
            select(ArtifactRecord.version)
            .where(ArtifactRecord.project_id == project_id)
            .where(ArtifactRecord.artifact_type == artifact_type)
            .order_by(desc(ArtifactRecord.version))
            .limit(1)
        )
        version = (latest or 0) + 1
        artifact_id = uuid4()
        created_at = datetime.utcnow()

        record = ArtifactRecord(
            artifact_id=artifact_id,
            project_id=project_id,
            artifact_type=artifact_type,
            version=version,
            payload=payload.model_dump(mode="json") if isinstance(payload, BaseModel) else payload,
            provenance=provenance.model_dump(mode="json"),
            produced_by=produced_by,
            created_at=created_at,
        )
        self._session.add(record)
        await self._session.flush()

        header = ArtifactHeader(
            artifact_id=artifact_id,
            project_id=project_id,
            artifact_type=artifact_type,
            version=version,
            produced_by=produced_by,
            created_at=created_at,
        )
        return Artifact(header=header, payload=payload, provenance=provenance)

    async def get_latest[T](self, project_id: UUID, artifact_type: str, payload_cls: type[T]) -> Artifact[T] | None:
        """Load the latest artifact of a given type for a project.

        Handles legacy payload shapes where the artifact was stored as the full
        agent output wrapper (e.g., InsightAgentOutput) instead of the inner
        payload (e.g., InsightBoard).
        """
        from pydantic import ValidationError

        record = await self._session.scalar(
            select(ArtifactRecord)
            .where(ArtifactRecord.project_id == project_id)
            .where(ArtifactRecord.artifact_type == artifact_type)
            .order_by(desc(ArtifactRecord.version))
            .limit(1)
        )
        if record is None:
            return None

        header = ArtifactHeader(
            artifact_id=record.artifact_id,
            project_id=record.project_id,
            artifact_type=record.artifact_type,
            version=record.version,
            produced_by=record.produced_by,
            created_at=record.created_at,
        )
        provenance = ArtifactProvenance.model_validate(record.provenance)

        try:
            payload = payload_cls.model_validate(record.payload)
        except ValidationError:
            # Try legacy wrapper shape (agent output types that wrap the payload)
            payload = self._try_legacy_payload(artifact_type, record.payload, payload_cls)

        return Artifact(header=header, payload=payload, provenance=provenance)

    def _try_legacy_payload[T](self, artifact_type: str, raw_payload: object, target_cls: type[T]) -> T:
        """Attempt to parse a legacy wrapped payload and extract the inner value."""
        from pydantic import ValidationError

        # Local imports to avoid circular dependencies
        if artifact_type == "source_map":
            from app.agents.source_agent.types import SourceAgentOutput
            try:
                return SourceAgentOutput.model_validate(raw_payload).source_map  # type: ignore[return-value]
            except ValidationError:
                pass
        elif artifact_type == "entity_graph":
            from app.agents.reconciliation_agent.types import ReconciliationAgentOutput
            try:
                return ReconciliationAgentOutput.model_validate(raw_payload).entity_graph  # type: ignore[return-value]
            except ValidationError:
                pass
        elif artifact_type == "schema_ir":
            from app.agents.schema_agent.types import SchemaAgentOutput
            try:
                return SchemaAgentOutput.model_validate(raw_payload).schema_ir  # type: ignore[return-value]
            except ValidationError:
                pass
        elif artifact_type == "insight_board":
            from app.agents.insight_agent.types import InsightAgentOutput
            try:
                return InsightAgentOutput.model_validate(raw_payload).insight_board  # type: ignore[return-value]
            except ValidationError:
                pass

        # If nothing worked, fall back to the original validation to get the proper error
        return target_cls.model_validate(raw_payload)

    async def list_headers(self, project_id: UUID) -> list[ArtifactHeader]:
        """List all artifact headers for a project."""
        records = await self._session.scalars(
            select(ArtifactRecord)
            .where(ArtifactRecord.project_id == project_id)
            .order_by(desc(ArtifactRecord.created_at))
        )
        return [
            ArtifactHeader(
                artifact_id=r.artifact_id,
                project_id=r.project_id,
                artifact_type=r.artifact_type,
                version=r.version,
                produced_by=r.produced_by,
                created_at=r.created_at,
            )
            for r in records
        ]
