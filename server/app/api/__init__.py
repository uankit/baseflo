"""API routes."""

from fastapi import APIRouter

from app.api import ask, auth, connectors, data, oauth, operating

router = APIRouter()

router.include_router(auth.router, prefix="/auth")
router.include_router(connectors.router, prefix="/connectors")
router.include_router(oauth.router, prefix="/oauth")
router.include_router(data.router)
router.include_router(ask.router, prefix="/ask")
router.include_router(operating.router, prefix="/operating")
