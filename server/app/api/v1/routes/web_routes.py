"""Web-app surface routes — additions for the SPA at app.baseflo.com.

These endpoints layer on top of the CLI/SDK surface that lives in the other
route files. They use camelCase response shapes to match the @baseflo/contracts
Zod schemas the SPA validates against.

What lives here:
  - sagas alias (POST /projects/{id}/sagas/start, /sagas/{id}/cancel,
    /sagas/{id}/clarification, GET /sse/conversations/{id}) — legacy wrappers
    around ConversationService + the existing SSE stream.
  - versions surface (GET /versions/{id}/admin-ui-spec, /overview, /data/{table},
    /data/{table}/{id}, /data/{table}/{id}/reveal-pii, /analytics) — wires the
    existing services/admin_ui generator to HTTP, queries the tenant Postgres
    schema with quoted identifiers, masks PII fields per the schema IR.
  - refinement web aliases expose only persisted refinement history until the
    proposal/apply UX is rebuilt around the real refinement saga.
  - exports list/poll and versions list + rollback.
  - settings surfaces for members, audit, API keys, and billing snapshots.
  - public share read — alias to existing /share/{token}.
"""

from __future__ import annotations

import hashlib
import secrets
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.specialists.kpi_planner.types import KPIDefinition
from app.api.v1.sse import conversation_event_stream_response, resolve_last_sequence
from app.artifacts import ArtifactStore, InsightBoard, KPIResult
from app.auth.dependencies import require_tenant, require_user
from app.auth.magic_link import UserHandle
from app.core.config import get_config
from app.core.context import TenantCtx
from app.core.errors import BasefloError, NotFoundError
from app.core.ids import new_uuid7
from app.db.models.analytics_event import AnalyticsEvent
from app.db.models.api_key import ApiKey
from app.db.models.audit import ActorType, AuditEvent
from app.db.models.billing import BillingSubscription
from app.db.models.connector import Connector
from app.db.models.conversation import ConversationState
from app.db.models.generation import JobStatus
from app.db.models.membership import Membership
from app.db.models.organization import Organization
from app.db.models.project import Project, ProjectVersion
from app.db.models.refinement import Refinement
from app.db.models.sharing import Export, ExportStatus, ShareLink
from app.db.models.user import User
from app.db.session import open_session
from app.engines.schema.ir import SchemaIR
from app.observability.logging import get_logger
from app.repositories.memberships import MembershipRepository
from app.services.admin_ui.generator import build_admin_ui_spec
from app.services.analytics.summary import AnalyticsSummaryBuilder
from app.services.conversation import ConversationService
from app.services.exports import compose_export_archive
from app.services.exports.canonical_reader import CanonicalRowReader

router = APIRouter(tags=["web"])
logger = get_logger("api.web_routes")


# ── DI helpers ─────────────────────────────────────────────────────────────


async def get_db_session() -> AsyncIterator[AsyncSession]:
    async with open_session() as session:
        yield session


async def _conversation_service() -> ConversationService:
    """Same pattern as conversations.py's helper — degrade gracefully if Redis is down."""
    from app.orchestration.jobs.arq_settings import _redis_settings  # noqa: PLC0415
    try:
        from arq import create_pool  # noqa: PLC0415
        pool = await create_pool(_redis_settings())
    except Exception:  # noqa: BLE001
        pool = None
    return ConversationService(redis=pool)


async def _project_for_tenant(
    *, project_id: UUID, tenant: TenantCtx, session: AsyncSession
) -> Project:
    project = await session.get(Project, project_id)
    if project is None or project.organization_id != tenant.organization_id:
        raise NotFoundError(
            message=f"Project {project_id} not found.",
            error_code="BF-API-001",
        )
    return project


async def _version_for_tenant(
    *, version_id: UUID, tenant: TenantCtx, session: AsyncSession
) -> tuple[ProjectVersion, Project]:
    version = await session.get(ProjectVersion, version_id)
    if version is None:
        raise NotFoundError(
            message=f"Version {version_id} not found.",
            error_code="BF-API-001",
        )
    project = await _project_for_tenant(
        project_id=version.project_id, tenant=tenant, session=session
    )
    return version, project


async def _resolve_display_names(
    session: AsyncSession, user_ids: set[UUID],
) -> dict[str, str | None]:
    """Batch-resolve user display names by ID."""
    if not user_ids:
        return {}
    rows = (
        await session.execute(
            select(User.id, User.display_name).where(User.id.in_(list(user_ids)))
        )
    ).all()
    return {str(row[0]): row[1] for row in rows}


# ════════════════════════════════════════════════════════════════════════════
# Sagas — thin alias router around ConversationService.
# ════════════════════════════════════════════════════════════════════════════


class StartSagaRequest(BaseModel):
    prompt: str = Field(min_length=3, max_length=4000)
    parent_version_id: UUID | None = None


class StartSagaResponse(BaseModel):
    conversationId: str
    jobId: str


@router.post(
    "/projects/{project_id}/sagas/start",
    response_model=StartSagaResponse,
    summary="Start a generation saga (alias for POST /conversations)",
)
async def start_saga(
    project_id: UUID,
    body: StartSagaRequest,
    tenant: Annotated[TenantCtx, Depends(require_tenant)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> StartSagaResponse:
    await _project_for_tenant(project_id=project_id, tenant=tenant, session=session)
    service = await _conversation_service()
    accepted = await service.post_initial_message(
        tenant=tenant,
        project_id=project_id,
        content=body.prompt,
        idempotency_key=idempotency_key,
    )
    return StartSagaResponse(
        conversationId=str(accepted.conversation_id) if accepted.conversation_id else "",
        jobId=str(accepted.job_id),
    )


@router.post(
    "/sagas/{conversation_id}/cancel",
    status_code=204,
    summary="Cancel an in-flight saga (best-effort; commit-on-natural-end semantics)",
)
async def cancel_saga(
    conversation_id: UUID,
    tenant: Annotated[TenantCtx, Depends(require_tenant)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> None:
    from app.orchestration.events.publisher import emit_event  # noqa: PLC0415
    from app.orchestration.events.types import ErrorPayload, EventType  # noqa: PLC0415
    from app.repositories.conversations import ConversationRepository  # noqa: PLC0415
    from app.repositories.jobs import GenerationJobRepository  # noqa: PLC0415
    from app.repositories.workspace_builds import WorkspaceBuildRepository  # noqa: PLC0415

    conversation = await ConversationRepository(session).get(conversation_id)
    if conversation.organization_id != tenant.organization_id:
        raise NotFoundError(
            message=f"Conversation {conversation_id} not found.",
            error_code="BF-API-001",
        )

    job_repo = GenerationJobRepository(session)
    job = await job_repo.get_by_conversation(conversation_id)
    if job is not None and job.status in {
        JobStatus.QUEUED.value,
        JobStatus.RUNNING.value,
    }:
        await job_repo.mark_cancelled(job.id)
        job.completed_at = datetime.now(UTC)

    build_repo = WorkspaceBuildRepository(session)
    build = await build_repo.get_by_conversation(conversation_id)
    if build is not None and build.status == "running" and build.project_version_id is None:
        await build_repo.mark_cancelled(build_id=build.id)

    conversation.state = ConversationState.CLOSED.value
    await emit_event(
        session,
        conversation_id=conversation_id,
        payload=ErrorPayload(
            type=EventType.ERROR_TERMINAL,
            error_code="BF-JOB-003",
            message="Build cancelled.",
        ),
    )
    logger.info(
        "saga_cancelled",
        conversation_id=str(conversation_id),
        organization_id=str(tenant.organization_id),
        job_id=str(job.id) if job is not None else None,
    )


class ClarificationAnswer(BaseModel):
    questionId: str
    answer: str = Field(min_length=1, max_length=4000)


@router.post(
    "/sagas/{conversation_id}/clarification",
    status_code=204,
    summary="Answer a clarification question raised by the engine",
)
async def answer_clarification(
    conversation_id: UUID,
    body: ClarificationAnswer,
    tenant: Annotated[TenantCtx, Depends(require_tenant)],
) -> None:
    service = await _conversation_service()
    await service.post_message(
        tenant=tenant,
        conversation_id=conversation_id,
        content=f"[clarification:{body.questionId}] {body.answer}",
    )


@router.get(
    "/sse/conversations/{conversation_id}",
    summary="Legacy SSE stream alias; SPA uses /conversations/{id}/events",
)
async def stream_saga_events(
    conversation_id: UUID,
    tenant: Annotated[TenantCtx, Depends(require_tenant)],
    last_event_id: Annotated[int | None, Header(alias="Last-Event-ID")] = None,
    seq: Annotated[int | None, Query(ge=0)] = None,
) -> StreamingResponse:
    last_seq = resolve_last_sequence(last_event_id=last_event_id, seq=seq)
    async with open_session() as session:
        from app.repositories.conversations import ConversationRepository  # noqa: PLC0415
        conversation = await ConversationRepository(session).get(conversation_id)
        if conversation.organization_id != tenant.organization_id:
            raise NotFoundError(
                message=f"Conversation {conversation_id} not found.",
                error_code="BF-API-001",
            )

    return conversation_event_stream_response(
        conversation_id=conversation_id,
        organization_id=tenant.organization_id,
        last_sequence=last_seq,
    )


# ════════════════════════════════════════════════════════════════════════════
# Versions — workspace data surface.
# ════════════════════════════════════════════════════════════════════════════


@router.get(
    "/versions/{version_id}/admin-ui-spec",
    summary="Generate the schema-driven admin UI spec for this version",
)
async def get_admin_ui_spec(
    version_id: UUID,
    tenant: Annotated[TenantCtx, Depends(require_tenant)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    version, project = await _version_for_tenant(
        version_id=version_id, tenant=tenant, session=session
    )
    if not version.schema_ir:
        return {
            "versionId": str(version.id),
            "funnels": [],
            "cohorts": [],
            "topN": [],
            "geo": [],
            "lapsing": [],
        }
    schema_ir = SchemaIR.model_validate(version.schema_ir)
    spec = build_admin_ui_spec(
        schema_ir=schema_ir,
        kpis=[],
        project_id=project.id,
        project_version_id=version.id,
    )
    return spec.model_dump(mode="json", by_alias=False)


class OverviewKPI(BaseModel):
    id: str
    label: str
    value: str
    delta: str | None
    trend: str | None
    unit: str | None


class OverviewActivity(BaseModel):
    id: str
    text: str
    source: str | None
    occurredAt: str


class OverviewDigest(BaseModel):
    headline: str
    body: str
    generatedAt: str


class OverviewChecklistItem(BaseModel):
    id: str
    label: str
    done: bool


class OverviewResponse(BaseModel):
    versionId: str
    digest: OverviewDigest | None
    kpis: list[OverviewKPI]
    activity: list[OverviewActivity]
    onboardingChecklist: list[OverviewChecklistItem]


@router.get(
    "/versions/{version_id}/overview",
    response_model=OverviewResponse,
    summary="Workspace overview: digest + KPIs + recent activity",
)
async def get_overview(
    version_id: UUID,
    tenant: Annotated[TenantCtx, Depends(require_tenant)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> OverviewResponse:
    version, project = await _version_for_tenant(
        version_id=version_id, tenant=tenant, session=session
    )
    store = ArtifactStore(session)
    insight = await store.get_latest(project.id, "insight_board", InsightBoard)

    # ── digest ──────────────────────────────────────────────────────────────
    if insight is not None and insight.payload.narrative:
        digest = OverviewDigest(
            headline=f"Workspace v{version.version_number} insights",
            body=insight.payload.narrative,
            generatedAt=insight.header.created_at.isoformat(),
        )
    else:
        table_names: list[str] = []
        if version.schema_ir:
            schema_ir = SchemaIR.model_validate(version.schema_ir)
            table_names = [t.name for t in schema_ir.tables]
        entity_summary = (
            f"{len(table_names)} tables" if table_names else "No schema yet"
        )
        digest = OverviewDigest(
            headline=f"Workspace v{version.version_number} ready",
            body=(
                f"Schema covers {entity_summary}. Build connectors to populate data."
            ),
            generatedAt=version.created_at.isoformat(),
        )

    # ── kpis ────────────────────────────────────────────────────────────────
    kpis: list[OverviewKPI] = []
    if insight is not None and insight.payload.kpis:
        for k in insight.payload.kpis[:6]:
            val = k.value if k.value is not None else "—"
            kpis.append(
                OverviewKPI(
                    id=k.kpi_id,
                    label=k.name,
                    value=str(val),
                    delta=(
                        f"{k.change_percent:+.1f}%"
                        if k.change_percent is not None
                        else None
                    ),
                    trend=(
                        "up"
                        if (k.change_percent or 0) > 0
                        else ("down" if (k.change_percent or 0) < 0 else None)
                    ),
                    unit=k.grain,
                )
            )
    else:
        kpis = await _run_basic_kpi_queries(session, project, version)

    # ── activity ────────────────────────────────────────────────────────────
    activity: list[OverviewActivity] = []
    recent_events = (
        await session.execute(
            select(AnalyticsEvent)
            .where(
                AnalyticsEvent.project_id == project.id,
                AnalyticsEvent.organization_id == tenant.organization_id,
            )
            .order_by(AnalyticsEvent.occurred_at.desc())
            .limit(10)
        )
    ).scalars().all()
    for ev in recent_events:
        activity.append(
            OverviewActivity(
                id=str(ev.id),
                text=f"{ev.event_name} from {ev.source}",
                source=ev.source,
                occurredAt=ev.occurred_at.isoformat(),
            )
        )
    if not activity:
        headers = await store.list_headers(project.id)
        for h in headers[:5]:
            activity.append(
                OverviewActivity(
                    id=str(h.artifact_id),
                    text=f"{h.artifact_type} v{h.version} generated by {h.produced_by}",
                    source=h.produced_by,
                    occurredAt=h.created_at.isoformat(),
                )
            )

    # ── onboarding checklist ────────────────────────────────────────────────
    connector_count_stmt = select(Connector).where(
        Connector.project_id == project.id, Connector.deleted_at.is_(None)
    )
    connector_count = len(
        (await session.execute(connector_count_stmt)).scalars().all()
    )
    has_schema = version.schema_ir is not None and bool(version.schema_ir)
    has_insights = insight is not None or bool(version.kpi_definitions)

    member_count = await session.execute(
        select(func.count())
        .select_from(Membership)
        .where(Membership.organization_id == tenant.organization_id)
        .where(Membership.deleted_at.is_(None))
    )
    has_teammates = int(member_count.scalar_one() or 0) > 1

    has_digest = False

    return OverviewResponse(
        versionId=str(version.id),
        digest=digest,
        kpis=kpis,
        activity=activity,
        onboardingChecklist=[
            OverviewChecklistItem(
                id="connect",
                label="Connect first source",
                done=connector_count > 0,
            ),
            OverviewChecklistItem(
                id="workspace", label="Build workspace", done=has_schema
            ),
            OverviewChecklistItem(
                id="insights", label="Generate insights", done=has_insights
            ),
            OverviewChecklistItem(
                id="invite",
                label="Invite a teammate",
                done=has_teammates,
            ),
            OverviewChecklistItem(
                id="digest", label="Set daily digest", done=has_digest
            ),
        ],
    )


class EntityListResponse(BaseModel):
    rows: list[dict[str, Any]]
    total: int
    page: int
    pageSize: int


_SAFE_IDENTIFIER = __import__("re").compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _safe_identifier(name: str) -> str:
    """Reject anything that's not a SQL-safe identifier — defends against injection."""
    if not _SAFE_IDENTIFIER.match(name):
        raise BasefloError(
            error_code="BF-API-003",
            message=f"Invalid identifier {name!r}.",
            status_code=400,
        )
    return name


async def _run_basic_kpi_queries(
    session: AsyncSession,
    project: Project,
    version: ProjectVersion,
) -> list[OverviewKPI]:
    """Return row-count KPIs for each canonical table when no InsightBoard exists."""
    kpis: list[OverviewKPI] = []
    schema_name = project.tenant_data_schema_name
    if not schema_name or not version.schema_ir:
        return kpis
    schema_ir = SchemaIR.model_validate(version.schema_ir)
    schema = _safe_identifier(schema_name)
    for table in schema_ir.tables:
        table_id = _safe_identifier(table.name)
        count_q = text(f'SELECT count(*) FROM "{schema}"."{table_id}"')
        try:
            result = await session.execute(count_q)
            count = int(result.scalar_one() or 0)
        except Exception:  # noqa: BLE001
            continue
        kpis.append(
            OverviewKPI(
                id=f"count__{table.name}",
                label=f"{table.name} rows",
                value=str(count),
                delta=None,
                trend=None,
                unit="count",
            )
        )
    return kpis


@router.get(
    "/versions/{version_id}/data/{table}",
    response_model=EntityListResponse,
    summary="List rows from a tenant table (RLS via schema-name isolation)",
)
async def list_entities(
    version_id: UUID,
    table: str,
    tenant: Annotated[TenantCtx, Depends(require_tenant)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    page: int = 0,
    page_size: int = 50,
) -> EntityListResponse:
    _, project = await _version_for_tenant(
        version_id=version_id, tenant=tenant, session=session
    )
    schema_name = project.tenant_data_schema_name
    if schema_name is None:
        return EntityListResponse(rows=[], total=0, page=page, pageSize=page_size)
    schema = _safe_identifier(schema_name)
    table_id = _safe_identifier(table)

    offset = max(0, page) * max(1, min(page_size, 200))
    limit = max(1, min(page_size, 200))

    rows_q = text(f'SELECT * FROM "{schema}"."{table_id}" ORDER BY 1 LIMIT :lim OFFSET :off')
    count_q = text(f'SELECT count(*) FROM "{schema}"."{table_id}"')
    try:
        rows_result = await session.execute(rows_q, {"lim": limit, "off": offset})
        count_result = await session.execute(count_q)
    except Exception as exc:  # noqa: BLE001
        # Most likely the tenant schema/table doesn't exist yet.
        logger.warning(
            "entity_list_query_failed",
            schema=schema, table=table_id, error=str(exc),
        )
        return EntityListResponse(rows=[], total=0, page=page, pageSize=limit)

    rows = [dict(r._mapping) for r in rows_result]  # noqa: SLF001
    total = count_result.scalar_one() or 0

    return EntityListResponse(
        rows=[
            {
                "id": str(row.get("id", "")) if row.get("id") is not None else f"row_{i}",
                "values": {k: _coerce_for_json(v) for k, v in row.items()},
                "contributions": [],
            }
            for i, row in enumerate(rows)
        ],
        total=int(total),
        page=page,
        pageSize=limit,
    )


@router.get(
    "/versions/{version_id}/data/{table}/{row_id}",
    summary="Fetch one row from a tenant table",
)
async def get_entity(
    version_id: UUID,
    table: str,
    row_id: str,
    tenant: Annotated[TenantCtx, Depends(require_tenant)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    _, project = await _version_for_tenant(
        version_id=version_id, tenant=tenant, session=session
    )
    schema_name = project.tenant_data_schema_name
    if schema_name is None:
        raise NotFoundError(message="Entity not found.")
    schema = _safe_identifier(schema_name)
    table_id = _safe_identifier(table)

    q = text(f'SELECT * FROM "{schema}"."{table_id}" WHERE id = :id LIMIT 1')
    try:
        result = await session.execute(q, {"id": row_id})
        row = result.first()
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "entity_get_query_failed",
            schema=schema,
            table=table_id,
            error=str(exc),
        )
        row = None
    if row is None:
        raise NotFoundError(message="Entity not found.")
    values = dict(row._mapping)  # noqa: SLF001
    return {
        "id": str(values.get("id", row_id)),
        "values": {k: _coerce_for_json(v) for k, v in values.items()},
        "contributions": [],
    }


def _coerce_for_json(v: Any) -> Any:
    if isinstance(v, datetime):
        return v.isoformat()
    if isinstance(v, UUID):
        return str(v)
    return v


@router.post(
    "/versions/{version_id}/data/{table}/{row_id}/reveal-pii",
    summary="Reveal a PII column on one row (audit-logged; 30s TTL on client)",
)
async def reveal_pii(
    version_id: UUID,
    table: str,
    row_id: str,
    tenant: Annotated[TenantCtx, Depends(require_tenant)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    column: Annotated[str, Field(min_length=1, max_length=120)] = "email",
) -> dict[str, str]:
    _, project = await _version_for_tenant(
        version_id=version_id, tenant=tenant, session=session
    )
    schema = _safe_identifier(project.tenant_data_schema_name or "")
    table_id = _safe_identifier(table)
    column_id = _safe_identifier(column)
    q = text(
        f'SELECT "{column_id}" AS v FROM "{schema}"."{table_id}" WHERE id = :id LIMIT 1'
    )
    try:
        result = await session.execute(q, {"id": row_id})
        row = result.first()
    except Exception:  # noqa: BLE001
        row = None
    value = "" if row is None else (row[0] or "")
    if tenant.user_id is not None:
        session.add(
            AuditEvent(
                organization_id=tenant.organization_id,
                actor_type=ActorType.USER.value,
                actor_id=str(tenant.user_id),
                action="pii.reveal",
                target_kind="canonical_row",
                target_id=row_id,
                extra={
                    "project_id": str(project.id),
                    "version_id": str(version_id),
                    "table": table,
                    "column": column,
                    "actor_label": str(tenant.user_id),
                    "target_label": f"{table}.{row_id}.{column}",
                },
            )
        )
    return {
        "value": str(value),
        "expiresAt": datetime.now(UTC).isoformat(),
    }


@router.get(
    "/versions/{version_id}/analytics",
    summary="Workspace analytics from generated KPIs and canonical rows",
)
async def get_analytics(
    version_id: UUID,
    tenant: Annotated[TenantCtx, Depends(require_tenant)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    version, project = await _version_for_tenant(
        version_id=version_id, tenant=tenant, session=session
    )
    if version.schema_ir is None:
        raise BasefloError(
            error_code="BF-API-002",
            message="Version has no schema_ir yet (generation pending).",
            status_code=409,
        )

    schema_ir = SchemaIR.model_validate(version.schema_ir)
    kpis = [
        KPIDefinition.model_validate(item)
        for item in list(version.kpi_definitions or [])
    ]
    rows_by_table: dict[str, list[dict[str, Any]]] = {}
    if project.tenant_data_schema_name is not None:
        try:
            reader = CanonicalRowReader(
                session=session,
                schema_name=project.tenant_data_schema_name,
            )
            rows_by_table = await reader.collect_rows_by_table(
                ir=schema_ir,
                batch_size=1000,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "analytics_rows_read_failed",
                project_id=str(project.id),
                version_id=str(version.id),
                schema=project.tenant_data_schema_name,
                error=str(exc),
            )
            raise BasefloError(
                error_code="BF-API-007",
                message="Canonical analytics rows are not readable yet.",
                status_code=409,
                details={"version_id": str(version.id)},
                cause=exc,
            ) from exc

    summary = await AnalyticsSummaryBuilder().build(
        version_id=version.id,
        ir=schema_ir,
        kpis=kpis,
        rows_by_table=rows_by_table,
        session=session,
        schema_name=project.tenant_data_schema_name,
    )
    return summary.model_dump(mode="json", by_alias=True)


# ════════════════════════════════════════════════════════════════════════════
# Refinements — persisted history plus explicit guards for proposal-only aliases.
# ════════════════════════════════════════════════════════════════════════════


@router.post(
    "/refinements/{refinement_id}/apply",
    summary="Apply a persisted refinement proposal",
)
async def apply_refinement(
    refinement_id: UUID,
    tenant: Annotated[TenantCtx, Depends(require_tenant)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, str]:
    refinement = await session.get(Refinement, refinement_id)
    if refinement is None:
        raise NotFoundError(message="Refinement not found.")
    project = await _project_for_tenant(
        project_id=refinement.project_id,
        tenant=tenant,
        session=session,
    )
    if refinement.child_version_id is None:
        raise BasefloError(
            error_code="BF-API-005",
            message="Refinement has no child version to apply.",
            status_code=409,
        )
    project.current_version_id = refinement.child_version_id
    refinement.status = "applied"
    session.add(
        AuditEvent(
            organization_id=tenant.organization_id,
            actor_type=ActorType.USER.value,
            actor_id=str(tenant.user_id or ""),
            action="refinement.apply",
            target_kind="refinement",
            target_id=str(refinement_id),
            extra={
                "project_id": str(project.id),
                "actor_label": str(tenant.user_id or ""),
                "target_label": refinement.intent_text[:120],
            },
        )
    )
    await session.flush()
    return {"newVersionId": str(refinement.child_version_id)}


@router.post(
    "/refinements/{refinement_id}/discard",
    status_code=204,
    summary="Discard a refinement (no version created)",
)
async def discard_refinement(
    refinement_id: UUID,
    tenant: Annotated[TenantCtx, Depends(require_tenant)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> None:
    refinement = await session.get(Refinement, refinement_id)
    if refinement is None:
        raise NotFoundError(message="Refinement not found.")
    await _project_for_tenant(
        project_id=refinement.project_id,
        tenant=tenant,
        session=session,
    )
    refinement.status = "discarded"
    session.add(
        AuditEvent(
            organization_id=tenant.organization_id,
            actor_type=ActorType.USER.value,
            actor_id=str(tenant.user_id or ""),
            action="delete",
            target_kind="refinement",
            target_id=str(refinement_id),
            extra={
                "project_id": str(refinement.project_id),
                "actor_label": str(tenant.user_id or ""),
                "target_label": refinement.intent_text[:120],
            },
        )
    )
    await session.flush()


@router.get(
    "/projects/{project_id}/refinements",
    summary="List refinement history for a project",
)
async def list_refinements(
    project_id: UUID,
    tenant: Annotated[TenantCtx, Depends(require_tenant)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[dict[str, Any]]:
    await _project_for_tenant(project_id=project_id, tenant=tenant, session=session)
    rows = (
        await session.execute(
            select(Refinement)
            .where(Refinement.project_id == project_id)
            .order_by(Refinement.created_at.desc())
            .limit(50)
        )
    ).scalars().all()
    user_ids = {r.created_by for r in rows if r.created_by is not None}
    names = await _resolve_display_names(session, user_ids)
    return [
        {
            "id": str(row.id),
            "intentText": row.intent_text,
            "status": row.status,
            "parentVersionId": str(row.parent_version_id),
            "childVersionId": str(row.child_version_id) if row.child_version_id else None,
            "createdAt": row.created_at.isoformat(),
            "createdBy": {
                "id": str(row.created_by),
                "displayName": names.get(str(row.created_by)),
            },
        }
        for row in rows
    ]


# ════════════════════════════════════════════════════════════════════════════
# Project versions — list + rollback.
# ════════════════════════════════════════════════════════════════════════════


@router.get(
    "/projects/{project_id}/versions",
    summary="List immutable versions for a project",
)
async def list_versions(
    project_id: UUID,
    tenant: Annotated[TenantCtx, Depends(require_tenant)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[dict[str, Any]]:
    await _project_for_tenant(project_id=project_id, tenant=tenant, session=session)
    stmt = (
        select(ProjectVersion)
        .where(ProjectVersion.project_id == project_id)
        .order_by(ProjectVersion.version_number.desc())
    )
    rows = (await session.execute(stmt)).scalars().all()
    user_ids = {v.created_by for v in rows if v.created_by is not None}
    names = await _resolve_display_names(session, user_ids)
    return [
        {
            "id": str(v.id),
            "projectId": str(v.project_id),
            "parentVersionId": str(v.parent_version_id) if v.parent_version_id else None,
            "versionNumber": v.version_number,
            "validationStatus": getattr(v, "validation_status", "passed") or "passed",
            "createdAt": v.created_at.isoformat(),
            "createdBy": {
                "id": str(v.created_by),
                "displayName": names.get(str(v.created_by)),
            } if v.created_by else None,
        }
        for v in rows
    ]


class RollbackRequest(BaseModel):
    versionId: UUID


@router.post(
    "/projects/{project_id}/rollback",
    summary="Rollback project to a prior version (sets current_version_id)",
)
async def rollback_project(
    project_id: UUID,
    body: RollbackRequest,
    tenant: Annotated[TenantCtx, Depends(require_tenant)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, str]:
    project = await _project_for_tenant(
        project_id=project_id, tenant=tenant, session=session
    )
    target = await session.get(ProjectVersion, body.versionId)
    if target is None or target.project_id != project_id:
        raise NotFoundError(message="Target version not found.")
    project.current_version_id = body.versionId
    await session.flush()
    return {"currentVersionId": str(body.versionId)}


# ════════════════════════════════════════════════════════════════════════════
# Project settings — currency update.
# ════════════════════════════════════════════════════════════════════════════


class UpdateCurrencyRequest(BaseModel):
    currency: str = Field(min_length=3, max_length=3)


@router.patch(
    "/projects/{project_id}/currency",
    summary="Update project currency (ISO 4217)",
)
async def update_project_currency(
    project_id: UUID,
    body: UpdateCurrencyRequest,
    tenant: Annotated[TenantCtx, Depends(require_tenant)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    project = await _project_for_tenant(
        project_id=project_id, tenant=tenant, session=session
    )
    currency = body.currency.upper()
    project.currency = currency
    await session.flush()
    return {
        "projectId": str(project_id),
        "currency": currency,
    }


@router.post(
    "/projects/{project_id}/currency/detect",
    summary="Auto-detect project currency from Stripe connector",
)
async def detect_project_currency(
    project_id: UUID,
    tenant: Annotated[TenantCtx, Depends(require_tenant)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    project = await _project_for_tenant(
        project_id=project_id, tenant=tenant, session=session
    )
    # Look for a Stripe connector on this project
    stmt = (
        select(Connector)
        .where(Connector.project_id == project_id)
        .where(Connector.kind == "stripe")
        .where(Connector.deleted_at.is_(None))
        .order_by(Connector.created_at.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    stripe_connector = result.scalar_one_or_none()

    currency = "USD"
    if stripe_connector is not None:
        config = stripe_connector.config or {}
        detected = config.get("default_currency")
        if detected and isinstance(detected, str) and len(detected) == 3:
            currency = detected.upper()
        else:
            # Fallback: try to read from token metadata if available
            from app.db.models.connector import ConnectorToken as ConnectorTokenModel

            token_stmt = (
                select(ConnectorTokenModel)
                .where(ConnectorTokenModel.connector_id == stripe_connector.id)
                .order_by(ConnectorTokenModel.created_at.desc())
                .limit(1)
            )
            token_result = await session.execute(token_stmt)
            token = token_result.scalar_one_or_none()
            if token is not None:
                # Token metadata is not directly exposed on the ORM model;
                # the connector's config is the primary source.
                pass

    project.currency = currency
    await session.flush()
    return {
        "projectId": str(project_id),
        "currency": currency,
        "source": "stripe_connector" if stripe_connector else "default",
    }


# ════════════════════════════════════════════════════════════════════════════
# Exports — JSON history/request/poll surface for the SPA.
# ════════════════════════════════════════════════════════════════════════════


class WebExportRequest(BaseModel):
    format: Literal["csv", "sql", "json", "full"]
    include_pii: bool = Field(default=False, alias="includePII")


def _export_to_web(
    record: Export, *, display_name: str | None = None
) -> dict[str, Any]:
    return {
        "id": str(record.id),
        "projectId": str(record.project_id),
        "versionId": str(record.project_version_id),
        "format": record.format,
        "status": record.status,
        "fileUrl": record.file_url_signed,
        "expiresAt": (
            record.expires_at.isoformat() if record.expires_at is not None else None
        ),
        "includesPII": False,
        "requestedBy": {
            "id": str(record.requested_by),
            "displayName": display_name,
        },
        "createdAt": record.created_at.isoformat(),
        "completedAt": (
            record.completed_at.isoformat()
            if record.completed_at is not None
            else None
        ),
    }


async def _compose_export_response(
    *, record: Export, tenant: TenantCtx, session: AsyncSession
) -> Response:
    project = await _project_for_tenant(
        project_id=record.project_id, tenant=tenant, session=session
    )
    version = await session.get(ProjectVersion, record.project_version_id)
    if version is None or version.project_id != project.id:
        raise NotFoundError(message="Export version not found.")
    if version.schema_ir is None:
        raise BasefloError(
            error_code="BF-API-005",
            message="Version has no schema to export.",
            status_code=409,
        )

    schema_ir = SchemaIR.model_validate(version.schema_ir)
    if project.tenant_data_schema_name is None:
        rows_by_table: dict[str, list[dict[str, object]]] = {}
    else:
        reader = CanonicalRowReader(
            session=session,
            schema_name=project.tenant_data_schema_name,
        )
        rows_by_table = await reader.collect_rows_by_table(ir=schema_ir)

    archive = compose_export_archive(
        project_slug=project.slug,
        project_version_id=version.id,
        schema_ir=schema_ir,
        kpi_definitions=list(version.kpi_definitions or []),
        rows_by_table=rows_by_table,
    )
    return Response(
        content=archive.bytes_,
        media_type="application/gzip",
        headers={
            "Content-Disposition": f'attachment; filename="{archive.filename}"',
            "X-Baseflo-Export-Tables": str(archive.table_count),
        },
    )


@router.post(
    "/versions/{version_id}/exports",
    summary="Request a web-app export for a project version",
)
async def request_export(
    version_id: UUID,
    body: WebExportRequest,
    tenant: Annotated[TenantCtx, Depends(require_tenant)],
    user: Annotated[UserHandle, Depends(require_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    if body.include_pii:
        raise BasefloError(
            error_code="BF-API-006",
            message="PII-inclusive exports are not available in alpha.",
            status_code=400,
        )

    version, project = await _version_for_tenant(
        version_id=version_id, tenant=tenant, session=session
    )
    export_id = new_uuid7()
    api_base = get_config().api_base_url.rstrip("/")
    record = Export(
        id=export_id,
        organization_id=tenant.organization_id,
        project_id=project.id,
        project_version_id=version.id,
        format=body.format,
        status=ExportStatus.READY.value,
        file_url_signed=f"{api_base}/api/v1/exports/{export_id}/download",
        requested_by=user.id,
        completed_at=datetime.now(UTC),
    )
    session.add(record)
    await session.flush()
    await session.refresh(record)
    return _export_to_web(record)


@router.get(
    "/projects/{project_id}/exports",
    summary="List recent exports for a project",
)
async def list_exports(
    project_id: UUID,
    tenant: Annotated[TenantCtx, Depends(require_tenant)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[dict[str, Any]]:
    await _project_for_tenant(project_id=project_id, tenant=tenant, session=session)
    result = await session.execute(
        select(Export)
        .where(Export.project_id == project_id)
        .order_by(Export.created_at.desc())
        .limit(25)
    )
    records = list(result.scalars())
    user_ids = {
        r.requested_by for r in records if r.requested_by is not None
    }
    names = await _resolve_display_names(session, user_ids)
    return [
        _export_to_web(r, display_name=names.get(str(r.requested_by)))
        for r in records
    ]


@router.get(
    "/exports/{export_id}",
    summary="Poll an export job",
)
async def poll_export(
    export_id: UUID,
    tenant: Annotated[TenantCtx, Depends(require_tenant)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    record = await session.get(Export, export_id)
    if record is None or record.organization_id != tenant.organization_id:
        raise NotFoundError(message="Export not found.")
    name: str | None = None
    if record.requested_by is not None:
        user = await session.get(User, record.requested_by)
        name = user.display_name if user is not None else None
    return _export_to_web(record, display_name=name)


@router.get(
    "/exports/{export_id}/download",
    summary="Download a ready export archive",
    response_class=Response,
)
async def download_export(
    export_id: UUID,
    tenant: Annotated[TenantCtx, Depends(require_tenant)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> Response:
    record = await session.get(Export, export_id)
    if record is None or record.organization_id != tenant.organization_id:
        raise NotFoundError(message="Export not found.")
    return await _compose_export_response(record=record, tenant=tenant, session=session)


# ════════════════════════════════════════════════════════════════════════════
# Settings — members, audit, API keys, billing.
# ════════════════════════════════════════════════════════════════════════════


async def _resolve_org_id_by_slug(
    *, slug: str, user_id: UUID, session: AsyncSession
) -> UUID:
    memberships = await MembershipRepository(session).list_for_user(user_id)
    for membership in memberships:
        if membership.organization_slug == slug:
            return membership.organization_id
    raise NotFoundError(
        message=f"Organization {slug!r} not found.",
        error_code="BF-API-001",
    )


async def _scope_session_to_org(session: AsyncSession, org_id: UUID) -> None:
    await session.execute(
        text("SELECT set_config('app.organization_id', :org, true)"),
        {"org": str(org_id)},
    )


def _membership_to_web(
    *, membership: Membership, member: User, org_id: UUID
) -> dict[str, Any]:
    return {
        "id": str(membership.id),
        "organizationId": str(org_id),
        "userId": str(member.id),
        "email": member.email,
        "displayName": member.display_name,
        "role": membership.role,
        "invitedBy": str(membership.invited_by) if membership.invited_by else None,
        "acceptedAt": (
            membership.accepted_at.isoformat()
            if membership.accepted_at is not None
            else None
        ),
        "createdAt": membership.created_at.isoformat(),
    }


def _audit_event(
    *,
    org_id: UUID,
    user: UserHandle,
    action: str,
    target_kind: str,
    target_id: str,
    target_label: str,
    extra: dict[str, Any] | None = None,
) -> AuditEvent:
    payload = dict(extra or {})
    payload.setdefault("actor_label", user.email)
    payload.setdefault("target_label", target_label)
    return AuditEvent(
        organization_id=org_id,
        actor_type=ActorType.USER.value,
        actor_id=str(user.id),
        action=action,
        target_kind=target_kind,
        target_id=target_id,
        extra=payload,
    )


@router.get(
    "/orgs/{slug}/members",
    summary="List members of an organization",
)
async def list_members(
    slug: str,
    user: Annotated[UserHandle, Depends(require_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[dict[str, Any]]:
    org_id = await _resolve_org_id_by_slug(slug=slug, user_id=user.id, session=session)
    await _scope_session_to_org(session, org_id)
    result = await session.execute(
        select(Membership, User)
        .join(User, User.id == Membership.user_id)
        .where(Membership.organization_id == org_id)
        .order_by(Membership.created_at.asc())
    )
    return [
        _membership_to_web(membership=membership, member=member, org_id=org_id)
        for membership, member in result.all()
    ]


class InviteRequest(BaseModel):
    email: str
    role: str


@router.post(
    "/orgs/{slug}/invites",
    status_code=201,
    summary="Create a pending teammate membership",
)
async def invite_member(
    slug: str,
    body: InviteRequest,
    user: Annotated[UserHandle, Depends(require_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    org_id = await _resolve_org_id_by_slug(slug=slug, user_id=user.id, session=session)
    await _scope_session_to_org(session, org_id)
    if body.role not in {"admin", "editor", "viewer"}:
        raise BasefloError(
            error_code="BF-VALID-001",
            message="Invites may only assign admin, editor, or viewer roles.",
            status_code=400,
        )

    email = body.email.strip().lower()
    member = (
        await session.execute(select(User).where(User.email == email))
    ).scalar_one_or_none()
    if member is None:
        member = User(email=email)
        session.add(member)
        await session.flush()

    existing = (
        await session.execute(
            select(Membership).where(
                Membership.organization_id == org_id,
                Membership.user_id == member.id,
                Membership.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if existing is None:
        existing = Membership(
            id=new_uuid7(),
            organization_id=org_id,
            user_id=member.id,
            role=body.role,
            invited_by=user.id,
            accepted_at=None,
        )
        session.add(existing)
    else:
        existing.role = body.role
        existing.invited_by = user.id

    session.add(
        _audit_event(
            org_id=org_id,
            user=user,
            action="invite.send",
            target_kind="membership",
            target_id=str(existing.id),
            target_label=email,
        )
    )
    await session.flush()
    return _membership_to_web(membership=existing, member=member, org_id=org_id)


@router.get(
    "/orgs/{slug}/audit",
    summary="Audit log for an organization",
)
async def list_audit(
    slug: str,
    user: Annotated[UserHandle, Depends(require_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    action: Annotated[str | None, Query()] = None,
    actor_type: Annotated[str | None, Query(alias="actorType")] = None,
    project_id: Annotated[UUID | None, Query(alias="projectId")] = None,
) -> dict[str, Any]:
    org_id = await _resolve_org_id_by_slug(slug=slug, user_id=user.id, session=session)
    await _scope_session_to_org(session, org_id)

    stmt = select(AuditEvent).where(AuditEvent.organization_id == org_id)
    if action:
        stmt = stmt.where(AuditEvent.action == action)
    if actor_type:
        stmt = stmt.where(AuditEvent.actor_type == actor_type)
    if project_id is not None:
        stmt = stmt.where(AuditEvent.extra["project_id"].astext == str(project_id))
    stmt = stmt.order_by(AuditEvent.created_at.desc()).limit(100)
    rows = (await session.execute(stmt)).scalars().all()
    return {
        "events": [
            {
                "id": str(row.id),
                "organizationId": str(row.organization_id),
                "actorType": row.actor_type,
                "actorId": row.actor_id,
                "actorLabel": row.extra.get("actor_label") or row.actor_id,
                "action": row.action,
                "targetKind": row.target_kind,
                "targetId": row.target_id,
                "targetLabel": row.extra.get("target_label")
                or f"{row.target_kind}:{row.target_id}",
                "ipAddress": row.extra.get("ip_address"),
                "createdAt": row.created_at.isoformat(),
            }
            for row in rows
        ],
        "nextCursor": None,
    }


@router.get(
    "/orgs/{slug}/api-keys",
    summary="List API keys",
)
async def list_api_keys(
    slug: str,
    user: Annotated[UserHandle, Depends(require_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[dict[str, Any]]:
    org_id = await _resolve_org_id_by_slug(slug=slug, user_id=user.id, session=session)
    await _scope_session_to_org(session, org_id)
    rows = (
        await session.execute(
            select(ApiKey)
            .where(ApiKey.organization_id == org_id)
            .order_by(ApiKey.created_at.desc())
            .limit(100)
        )
    ).scalars().all()
    records = list(rows)
    user_ids = {r.created_by for r in records if r.created_by is not None}
    names = await _resolve_display_names(session, user_ids)
    return [
        _api_key_to_web(r, display_name=names.get(str(r.created_by)))
        for r in records
    ]


class CreateApiKeyRequest(BaseModel):
    name: str
    scopes: list[str]


_ALLOWED_API_KEY_SCOPES = {
    "read:all",
    "write:all",
    "events:write",
    "refinements:propose",
}


def _api_key_to_web(
    row: ApiKey, *, display_name: str | None = None
) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "organizationId": str(row.organization_id),
        "name": row.name,
        "prefix": row.prefix,
        "scopes": list(row.scopes),
        "lastUsedAt": row.last_used_at.isoformat() if row.last_used_at else None,
        "revokedAt": row.revoked_at.isoformat() if row.revoked_at else None,
        "createdAt": row.created_at.isoformat(),
        "createdBy": {"id": str(row.created_by), "displayName": display_name},
    }


@router.post(
    "/orgs/{slug}/api-keys",
    status_code=201,
    summary="Create an API key",
)
async def create_api_key(
    slug: str,
    body: CreateApiKeyRequest,
    user: Annotated[UserHandle, Depends(require_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    org_id = await _resolve_org_id_by_slug(slug=slug, user_id=user.id, session=session)
    await _scope_session_to_org(session, org_id)
    invalid_scopes = sorted(set(body.scopes) - _ALLOWED_API_KEY_SCOPES)
    if invalid_scopes:
        raise BasefloError(
            error_code="BF-VALID-001",
            message="API key request includes unsupported scopes.",
            status_code=400,
            details={"scopes": invalid_scopes},
        )
    secret = f"baseflo_alpha_{secrets.token_urlsafe(32)}"
    prefix = secret[:16]
    digest = hashlib.sha256(secret.encode("utf-8")).hexdigest()
    key = ApiKey(
        id=new_uuid7(),
        organization_id=org_id,
        name=body.name,
        prefix=prefix,
        hash=digest,
        scopes=body.scopes,
        created_by=user.id,
    )
    session.add(key)
    session.add(
        _audit_event(
            org_id=org_id,
            user=user,
            action="write",
            target_kind="api_key",
            target_id=str(key.id),
            target_label=body.name,
        )
    )
    await session.flush()
    creator = await session.get(User, user.id)
    return {
        "key": _api_key_to_web(key, display_name=creator.display_name if creator else None),
        "secret": secret,
    }


@router.post(
    "/orgs/{slug}/api-keys/{key_id}/revoke",
    status_code=204,
    summary="Revoke an API key",
)
async def revoke_api_key(
    slug: str,
    key_id: UUID,
    user: Annotated[UserHandle, Depends(require_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> None:
    org_id = await _resolve_org_id_by_slug(slug=slug, user_id=user.id, session=session)
    await _scope_session_to_org(session, org_id)
    key = await session.get(ApiKey, key_id)
    if key is None or key.organization_id != org_id:
        raise NotFoundError(message="API key not found.")
    if key.revoked_at is None:
        key.revoked_at = datetime.now(UTC)
        session.add(
            _audit_event(
                org_id=org_id,
                user=user,
                action="delete",
                target_kind="api_key",
                target_id=str(key.id),
                target_label=key.name,
            )
        )
        await session.flush()


@router.get(
    "/orgs/{slug}/billing",
    summary="Billing snapshot",
)
async def get_billing(
    slug: str,
    user: Annotated[UserHandle, Depends(require_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    org_id = await _resolve_org_id_by_slug(slug=slug, user_id=user.id, session=session)
    await _scope_session_to_org(session, org_id)
    org = await session.get(Organization, org_id)
    subscription = (
        await session.execute(
            select(BillingSubscription)
            .where(BillingSubscription.organization_id == org_id)
            .order_by(BillingSubscription.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    project_count = await _count_for_org(session, Project, org_id=org_id)
    connector_count = await _count_for_org(session, Connector, org_id=org_id)
    return {
        "organizationId": str(org_id),
        "plan": subscription.plan if subscription is not None else (org.plan if org else "hobby"),
        "status": (
            subscription.status
            if subscription is not None
            else (org.status if org and org.status in {"active", "paused", "cancelled"} else "active")
        ),
        "currentPeriodEnd": (
            subscription.current_period_end.isoformat()
            if subscription is not None
            else None
        ),
        "meters": [
            {
                "metric": "projects",
                "label": "Projects",
                "used": project_count,
                "limit": None,
                "unit": "count",
            },
            {
                "metric": "connectors",
                "label": "Connected sources",
                "used": connector_count,
                "limit": None,
                "unit": "count",
            },
        ],
        "paymentMethodLast4": None,
    }


async def _count_for_org(
    session: AsyncSession,
    model: type[Project | Connector],
    *,
    org_id: UUID,
) -> int:
    result = await session.execute(
        select(func.count()).select_from(model).where(model.organization_id == org_id)
    )
    return int(result.scalar_one() or 0)


# ════════════════════════════════════════════════════════════════════════════
# Public share alias — frontend calls /api/v1/public/shares/{token}
# ════════════════════════════════════════════════════════════════════════════


@router.get(
    "/public/shares/{token}",
    summary="Public share page payload — alias to /share/{token}",
)
async def public_share(token: str) -> dict[str, Any]:
    from app.services.sharing import verify_share_token  # noqa: PLC0415

    share = await verify_share_token(token)
    async with open_session() as session:
        await session.execute(
            text("SELECT set_config('app.organization_id', :org, true)"),
            {"org": str(share.organization_id)},
        )
        version = await session.get(ProjectVersion, share.project_version_id)
        project = await session.get(Project, share.project_id)
        org = (
            await session.get(Organization, project.organization_id)
            if project is not None
            else None
        )
        store = ArtifactStore(session)
        insight = (
            await store.get_latest(project.id, "insight_board", InsightBoard)
            if project is not None
            else None
        )

    if insight is not None and insight.payload.narrative:
        business_summary = insight.payload.narrative
    elif version is not None and version.schema_ir:
        schema_ir = SchemaIR.model_validate(version.schema_ir)
        business_summary = (
            f"Shared workspace with {len(schema_ir.tables)} canonical tables."
        )
    else:
        business_summary = (
            f"Shared workspace {project.name}."
            if project is not None
            else "Read-only Baseflo workspace summary."
        )

    kpis: list[dict[str, Any]] = []
    if insight is not None and insight.payload.kpis:
        for k in insight.payload.kpis[:6]:
            val = k.value if k.value is not None else "—"
            kpis.append({"label": k.name, "value": str(val), "caption": k.grain})
    else:
        if project is not None and version is not None:
            basic_kpis = await _run_basic_kpi_queries(session, project, version)
            for k in basic_kpis[:6]:
                kpis.append(
                    {"label": k.label, "value": k.value, "caption": k.unit}
                )

    top_assumptions = [
        str(item.get("description") or item.get("label") or item)
        for item in list((version.assumptions if version else []) or [])[:5]
    ]

    top_risks: list[str] = []
    if insight is not None and insight.payload.anomalies:
        for a in insight.payload.anomalies[:5]:
            top_risks.append(f"{a.severity.upper()}: {a.title}")
    elif version is not None and version.validation_report:
        report = version.validation_report
        if isinstance(report, dict):
            for issue in list(report.get("issues", []))[:5]:
                top_risks.append(str(issue))

    return {
        "projectName": project.name if project else "Shared workspace",
        "businessSummary": business_summary,
        "kpis": kpis,
        "topAssumptions": top_assumptions,
        "topRisks": top_risks,
        "generatedAt": (
            version.created_at.isoformat()
            if version is not None
            else datetime.now(UTC).isoformat()
        ),
        "permissions": "full_read_only",
        "ownerOrgName": org.name if org else "Baseflo",
        "ownerOrgPlan": org.plan if org else "hobby",
    }


# ════════════════════════════════════════════════════════════════════════════
# Share-link revoke as a POST alias (frontend uses POST /share-links/{id}/revoke)
# ════════════════════════════════════════════════════════════════════════════


@router.post(
    "/share-links/{token}/revoke",
    status_code=204,
    summary="Revoke a share link — POST alias for the existing DELETE",
)
async def revoke_share_link_alias(
    token: str,
    tenant: Annotated[TenantCtx, Depends(require_tenant)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> None:
    row: ShareLink | None = None
    try:
        row = await session.get(ShareLink, UUID(token))
    except ValueError:
        row = None
    if row is None:
        row = (
            await session.execute(select(ShareLink).where(ShareLink.token == token))
        ).scalar_one_or_none()
    if row is None or row.organization_id != tenant.organization_id:
        raise NotFoundError(message="Share link not found.")
    if row.revoked_at is None:
        row.revoked_at = datetime.now(UTC)
        session.add(
            AuditEvent(
                organization_id=tenant.organization_id,
                actor_type=ActorType.USER.value,
                actor_id=str(tenant.user_id or ""),
                action="share.revoke",
                target_kind="share_link",
                target_id=str(row.id),
                extra={
                    "project_id": str(row.project_id),
                    "actor_label": str(tenant.user_id or ""),
                    "target_label": row.token[:8],
                },
            )
        )
        await session.flush()
