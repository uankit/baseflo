"""Health and readiness routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from sqlalchemy import text

from app.db.session import engine

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_endpoint() -> dict[str, Any]:
    checks: dict[str, Any] = {}
    healthy = True
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
        checks["database"] = {"ok": True}
    except Exception as exc:
        healthy = False
        checks["database"] = {"ok": False, "error": str(exc)}
    return {"ok": healthy, "healthy": healthy, "checks": checks}
