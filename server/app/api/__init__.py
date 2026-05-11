"""API routes."""

from fastapi import APIRouter

from app.api import auth, connectors, insights, kpis, projects, query, semantic

router = APIRouter()

router.include_router(auth.router, prefix="/auth", tags=["auth"])
router.include_router(projects.router, prefix="/projects", tags=["projects"])
router.include_router(connectors.router, prefix="/connectors", tags=["connectors"])
router.include_router(semantic.router, prefix="/semantic", tags=["semantic"])
router.include_router(insights.router, prefix="/insights", tags=["insights"])
router.include_router(kpis.router, prefix="/kpis", tags=["kpis"])
router.include_router(query.router, prefix="/query", tags=["query"])
