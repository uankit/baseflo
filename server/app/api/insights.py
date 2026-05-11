"""Insight feed routes."""

from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_auth
from app.core.context import TenantCtx
from app.core.errors import BasefloError
from app.db.models import Insight
from app.db.session import open_session

router = APIRouter()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class InsightOut(BaseModel):
    id: str
    kind: str
    severity: str
    title: str
    description: str
    confidence: float
    sql: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)
    is_read: bool = False
    is_dismissed: bool = False
    created_at: str


class InsightListResponse(BaseModel):
    items: list[InsightOut]
    total: int
    unread_count: int


class InsightStatsResponse(BaseModel):
    total: int
    unread: int
    by_severity: dict[str, int]


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("", response_model=InsightListResponse)
async def list_insights(
    tenant: Annotated[TenantCtx, Depends(require_auth)],
    project_id: UUID,
    unread_only: bool = False,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> InsightListResponse:
    """List insights for a project, newest first."""
    async with open_session() as session:
        base_filter = select(Insight).where(
            Insight.project_id == project_id,
            Insight.is_dismissed == False,
        )
        if unread_only:
            base_filter = base_filter.where(Insight.is_read == False)

        # Total count
        count_stmt = select(func.count()).select_from(base_filter.subquery())
        total_result = await session.execute(count_stmt)
        total = total_result.scalar_one()

        # Unread count (regardless of offset/limit)
        unread_stmt = select(func.count()).where(
            Insight.project_id == project_id,
            Insight.is_dismissed == False,
            Insight.is_read == False,
        )
        unread_result = await session.execute(unread_stmt)
        unread_count = unread_result.scalar_one()

        # Paginated items
        stmt = (
            base_filter
            .order_by(desc(Insight.created_at))
            .offset(offset)
            .limit(limit)
        )
        result = await session.execute(stmt)
        insights = result.scalars().all()

    return InsightListResponse(
        items=[
            InsightOut(
                id=str(ins.id),
                kind=ins.kind,
                severity=ins.severity,
                title=ins.title,
                description=ins.description,
                confidence=float(ins.confidence) if ins.confidence else 0.0,
                sql=ins.sql,
                data=ins.data or {},
                is_read=ins.is_read,
                is_dismissed=ins.is_dismissed,
                created_at=ins.created_at.isoformat() if ins.created_at else "",
            )
            for ins in insights
        ],
        total=total,
        unread_count=unread_count,
    )


@router.post("/{insight_id}/read")
async def mark_read(
    tenant: Annotated[TenantCtx, Depends(require_auth)],
    insight_id: UUID,
) -> dict[str, Any]:
    """Mark an insight as read."""
    async with open_session() as session:
        insight = await session.get(Insight, insight_id)
        if insight is None:
            raise BasefloError(
                message="Insight not found",
                error_code="BF-INS-001",
                status_code=404,
            )
        insight.is_read = True
        await session.commit()

    return {"id": str(insight_id), "is_read": True}


@router.post("/{insight_id}/dismiss")
async def dismiss_insight(
    tenant: Annotated[TenantCtx, Depends(require_auth)],
    insight_id: UUID,
) -> dict[str, Any]:
    """Dismiss an insight (hides from feed)."""
    async with open_session() as session:
        insight = await session.get(Insight, insight_id)
        if insight is None:
            raise BasefloError(
                message="Insight not found",
                error_code="BF-INS-002",
                status_code=404,
            )
        insight.is_dismissed = True
        await session.commit()

    return {"id": str(insight_id), "is_dismissed": True}


@router.get("/stats", response_model=InsightStatsResponse)
async def insight_stats(
    tenant: Annotated[TenantCtx, Depends(require_auth)],
    project_id: UUID,
) -> InsightStatsResponse:
    """Get insight statistics for a project."""
    async with open_session() as session:
        # Total undismissed
        total_stmt = select(func.count()).where(
            Insight.project_id == project_id,
            Insight.is_dismissed == False,
        )
        total_result = await session.execute(total_stmt)
        total = total_result.scalar_one()

        # Unread
        unread_stmt = select(func.count()).where(
            Insight.project_id == project_id,
            Insight.is_dismissed == False,
            Insight.is_read == False,
        )
        unread_result = await session.execute(unread_stmt)
        unread = unread_result.scalar_one()

        # By severity
        severity_stmt = (
            select(Insight.severity, func.count())
            .where(
                Insight.project_id == project_id,
                Insight.is_dismissed == False,
            )
            .group_by(Insight.severity)
        )
        severity_result = await session.execute(severity_stmt)
        by_severity = {row[0]: row[1] for row in severity_result.all()}

    return InsightStatsResponse(
        total=total,
        unread=unread,
        by_severity=by_severity,
    )
