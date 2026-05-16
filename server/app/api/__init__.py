"""API routes."""

from fastapi import APIRouter

from app.api import actions, artifacts, auth, connectors, data, health, oauth, operating

router = APIRouter()

router.include_router(auth.router, prefix="/auth")
router.include_router(connectors.router, prefix="/connectors")
router.include_router(oauth.router, prefix="/oauth")
router.include_router(data.router)
router.include_router(health.router)
router.include_router(operating.router, prefix="/operating")
router.include_router(artifacts.router, prefix="/artifacts")
router.include_router(actions.router, prefix="/actions")
