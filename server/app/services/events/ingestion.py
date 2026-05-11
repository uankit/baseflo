"""Event ingestion service.

Per docs/40-features/ANALYTICS.md §4. Validates a batch of incoming events
against the project's current event taxonomy, persists the accepted ones,
and returns a typed report of accepted + rejected.

The taxonomy resolution order (cheapest → most expensive):
  1. project_version.intelligence_taxonomy is non-empty → parse it directly.
  2. project_version.schema_ir is non-empty → derive via build_event_taxonomy.
  3. neither → reject the request: the project has no schema yet, so we can't
     know which event names are valid. The SDK should retry once a version
     has been generated.

Idempotency: when an event carries `idempotency_key`, the repository's
`ON CONFLICT DO NOTHING` makes safe-retries cost zero conflicts. The result
records each conflict as `accepted=True, persisted=False` so the SDK can
distinguish "first time" from "already there".
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.core.context import TenantCtx
from app.core.errors import NotFoundError, ValidationError
from app.core.ids import new_uuid7
from app.db.models.analytics_event import AnalyticsEvent, EventSource
from app.db.session import open_session
from app.engines.analytics.event_validation import (
    EventDescriptor,
    validate_event,
)
from app.engines.analytics.taxonomy import (
    EventTaxonomy,
    build_event_taxonomy,
)
from app.engines.schema.ir import SchemaIR
from app.observability.logging import get_logger
from app.repositories.analytics_events import AnalyticsEventRepository
from app.repositories.projects import ProjectRepository


logger = get_logger("services.events.ingestion")


# ---------- Input / output models ----------


class EventIngestionInput(BaseModel):
    """One event the SDK posts. The route accepts a list of these."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=2, max_length=120, pattern=r"^[a-z][a-z0-9_]*$")
    distinct_id: str = Field(min_length=1, max_length=255)
    entity_id: str | None = Field(default=None, max_length=255)
    properties: dict[str, Any] = Field(default_factory=dict)
    occurred_at: datetime | None = None
    idempotency_key: str | None = Field(default=None, max_length=120)


@dataclass(frozen=True, slots=True)
class RejectedEvent:
    """Carries the index in the input batch + the reason."""

    index: int
    name: str
    reason: str


@dataclass(frozen=True, slots=True)
class EventIngestionResult:
    """Tally of what happened with a batch of events."""

    accepted: int
    """How many events validated (regardless of dedup)."""
    persisted: int
    """How many actually wrote a new row (rest were idempotent dedups)."""
    rejected: tuple[RejectedEvent, ...]


# ---------- Service ----------


class EventIngestionService:
    """Use-case orchestrator.

    Constructed once per request via DI; uses `open_session()` so the tenant
    RLS scope is set automatically.
    """

    async def ingest(
        self,
        *,
        tenant: TenantCtx,
        project_id: UUID,
        events: Sequence[EventIngestionInput],
        source: EventSource = EventSource.SDK,
    ) -> EventIngestionResult:
        if not events:
            return EventIngestionResult(accepted=0, persisted=0, rejected=())

        async with open_session() as session:
            project_repo = ProjectRepository(session)
            event_repo = AnalyticsEventRepository(session)

            # The project lookup also enforces the tenant scope (RLS).
            project = await project_repo.get(project_id)
            if project.organization_id != tenant.organization_id:
                # Belt-and-suspenders; RLS already filters this out.
                raise NotFoundError(
                    message=f"Project {project_id} not found.",
                    error_code="BF-API-001",
                )

            version = await project_repo.get_current_version(project_id)
            taxonomy = _resolve_taxonomy(version)
            version_id = version.id if version is not None else None

            accepted_rows: list[AnalyticsEvent] = []
            rejected: list[RejectedEvent] = []
            now = datetime.now(UTC)

            for index, descriptor in enumerate(events):
                outcome = validate_event(
                    descriptor=EventDescriptor(
                        name=descriptor.name, properties=descriptor.properties
                    ),
                    taxonomy=taxonomy,
                )
                if not outcome.valid:
                    assert outcome.reason is not None
                    rejected.append(
                        RejectedEvent(
                            index=index, name=descriptor.name, reason=outcome.reason
                        )
                    )
                    continue
                accepted_rows.append(
                    AnalyticsEvent(
                        id=new_uuid7(),
                        organization_id=tenant.organization_id,
                        project_id=project_id,
                        project_version_id=version_id,
                        event_name=descriptor.name,
                        distinct_id=descriptor.distinct_id,
                        entity_id=descriptor.entity_id,
                        properties=dict(descriptor.properties),
                        source=source.value,
                        idempotency_key=descriptor.idempotency_key,
                        occurred_at=descriptor.occurred_at or now,
                    )
                )

            inserted, conflicts = await event_repo.insert_batch(accepted_rows)

        logger.info(
            "events_ingested",
            project_id=str(project_id),
            accepted=len(accepted_rows),
            persisted=inserted,
            conflicts=conflicts,
            rejected=len(rejected),
        )
        return EventIngestionResult(
            accepted=len(accepted_rows),
            persisted=inserted,
            rejected=tuple(rejected),
        )


# ---------- Internal: taxonomy resolution ----------


def _resolve_taxonomy(version: Any) -> EventTaxonomy:
    """Pick the cheapest valid taxonomy source.

    Raises `ValidationError` (BF-API-005) when the project has no schema yet.
    """
    if version is None:
        raise ValidationError(
            message=(
                "Project has no schema version yet; events cannot be validated. "
                "Generate a project first, then retry ingestion."
            ),
            error_code="BF-API-005",
        )

    cached = version.intelligence_taxonomy or {}
    if cached:
        try:
            return EventTaxonomy.model_validate(cached)
        except Exception as exc:  # noqa: BLE001 — fall through to schema_ir below
            logger.warning(
                "intelligence_taxonomy_parse_failed",
                project_version_id=str(version.id),
                error=repr(exc),
            )

    raw_ir = version.schema_ir or {}
    if not raw_ir:
        raise ValidationError(
            message=(
                "Project version has no schema_ir; events cannot be validated."
            ),
            error_code="BF-API-005",
        )

    schema = SchemaIR.model_validate(raw_ir)
    return build_event_taxonomy(schema)
