"""v1 API router aggregator."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.routes import (
    agents,
    artifacts,
    auth,
    connector_webhooks,
    connectors,
    conversations,
    events,
    exports,
    health,
    oauth,
    orgs,
    refinements,
    share_links,
    web_routes,
)

router = APIRouter(prefix="/api/v1")
router.include_router(health.router)
router.include_router(auth.router)
router.include_router(conversations.router)
router.include_router(events.router)
router.include_router(orgs.router)
router.include_router(oauth.router)
router.include_router(connectors.router)
router.include_router(connector_webhooks.router)
router.include_router(refinements.router)
router.include_router(exports.router)
router.include_router(share_links.router)
router.include_router(artifacts.router)
router.include_router(agents.router)
router.include_router(web_routes.router)
