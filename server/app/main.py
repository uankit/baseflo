"""FastAPI app + lifespan + middleware.

Per docs/40-features/SDK-AND-API.md, every response carries a `request_id`
header. Errors flow through `app.api.errors` for the standard envelope.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app import __version__
from app.api.errors import install_exception_handlers, request_id_var
from app.api.v1.router import router as v1_router
from app.core.config import get_config
from app.observability.logging import configure_logging, get_logger


@asynccontextmanager
async def _lifespan(_app: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    logger = get_logger("startup")
    config = get_config()
    logger.info(
        "baseflo_server_starting",
        version=__version__,
        env=config.env.value,
        agent_provider=config.agent_provider.value,
    )
    try:
        yield
    finally:
        logger.info("baseflo_server_shutting_down")


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Set / propagate `X-Request-ID` and bind it to a context var.

    Generates a UUID4 if the client did not supply one. Echoes the value back
    in the response so the same id is visible in client and server logs.
    """

    async def dispatch(  # type: ignore[no-untyped-def]
        self, request: Request, call_next,
    ) -> Response:
        config = get_config()
        header = config.request_id_header
        existing = request.headers.get(header)
        request_id = existing if existing else f"req_{uuid.uuid4().hex}"
        token = request_id_var.set(request_id)
        try:
            response: Response = await call_next(request)
            response.headers[header] = request_id
            return response
        finally:
            request_id_var.reset(token)


def create_app() -> FastAPI:
    config = get_config()
    app = FastAPI(
        title="Baseflo",
        version=__version__,
        lifespan=_lifespan,
        # Expose docs only in non-production environments.
        docs_url="/docs" if not config.is_production_like() else None,
        redoc_url="/redoc" if not config.is_production_like() else None,
        openapi_url="/openapi.json",
    )
    app.add_middleware(RequestIdMiddleware)
    # Dev-mode auth (header-based). Real auth replaces this.
    from app.auth.middleware import install_auth_middleware  # noqa: PLC0415

    install_auth_middleware(app)
    install_exception_handlers(app)
    app.include_router(v1_router)
    return app


app: FastAPI = create_app()
