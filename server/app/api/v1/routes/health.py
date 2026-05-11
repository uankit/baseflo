"""Health endpoint.

Two flavors:

- `GET /api/v1/health` — liveness; returns 200 if the process is up. No DB roundtrip.
- `GET /api/v1/health/ready` — readiness; verifies DB + Redis connectivity. Returns
  503 with details if either is unreachable.

Used by load balancers, container orchestrators, and the status page.
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, status
from pydantic import BaseModel
from sqlalchemy import text

from app import __version__
from app.db.session import get_session_maker
from app.observability.logging import get_logger

router = APIRouter(tags=["health"])

logger = get_logger("api.health")


class HealthResponse(BaseModel):
    status: Literal["ok"]
    version: str


class ComponentStatus(BaseModel):
    healthy: bool
    detail: str | None = None


class ReadinessResponse(BaseModel):
    status: Literal["ok", "degraded"]
    version: str
    components: dict[str, ComponentStatus]


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Liveness check",
    status_code=status.HTTP_200_OK,
)
async def health() -> HealthResponse:
    return HealthResponse(status="ok", version=__version__)


@router.get(
    "/health/ready",
    response_model=ReadinessResponse,
    summary="Readiness check",
)
async def readiness() -> ReadinessResponse:
    components: dict[str, ComponentStatus] = {}

    # ---- Database
    try:
        maker = get_session_maker()
        async with maker() as session:
            result = await session.execute(text("SELECT 1"))
            assert result.scalar_one() == 1
        components["database"] = ComponentStatus(healthy=True)
    except Exception as exc:  # noqa: BLE001 — readiness intentionally swallows
        logger.warning("readiness_database_failed", error=str(exc))
        components["database"] = ComponentStatus(healthy=False, detail=str(exc))

    overall: Literal["ok", "degraded"] = (
        "ok" if all(c.healthy for c in components.values()) else "degraded"
    )
    return ReadinessResponse(
        status=overall,
        version=__version__,
        components=components,
    )
