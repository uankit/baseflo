"""FastAPI exception handlers — translate errors into the standard envelope.

Every error response carries `error_code`, `message`, `details`, `request_id`.
See docs/40-features/SDK-AND-API.md §3.2.
"""

from __future__ import annotations

import contextvars
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.errors import BasefloError, ValidationError
from app.observability.logging import get_logger

# Set per-request by middleware so handlers can attach it to error envelopes.
request_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "request_id_var", default=None
)


def _envelope(err: BasefloError, request_id: str | None) -> dict[str, Any]:
    return err.to_dict(request_id=request_id)


async def _handle_baseflo_error(request: Request, exc: BasefloError) -> JSONResponse:
    request_id = request_id_var.get() or request.headers.get("X-Request-ID")
    logger = get_logger("api.errors")
    logger.warning(
        "baseflo_error",
        error_code=exc.error_code,
        status_code=exc.status_code,
        message=exc.message,
        path=request.url.path,
        method=request.method,
    )
    return JSONResponse(status_code=exc.status_code, content=_envelope(exc, request_id))


async def _handle_validation_error(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    request_id = request_id_var.get() or request.headers.get("X-Request-ID")
    err = ValidationError(
        message="Request payload failed validation.",
        error_code="BF-VALID-001",
        details={"errors": exc.errors()},
    )
    return JSONResponse(status_code=err.status_code, content=_envelope(err, request_id))


async def _handle_http_exception(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    request_id = request_id_var.get() or request.headers.get("X-Request-ID")
    # Map well-known HTTP exceptions to BF codes; default to a generic envelope.
    err = BasefloError(
        error_code="BF-HTTP-001" if exc.status_code >= 500 else "BF-HTTP-000",
        message=str(exc.detail) if exc.detail else "HTTP error.",
        status_code=exc.status_code,
    )
    return JSONResponse(status_code=err.status_code, content=_envelope(err, request_id))


async def _handle_unhandled_error(request: Request, exc: Exception) -> JSONResponse:
    request_id = request_id_var.get() or request.headers.get("X-Request-ID")
    logger = get_logger("api.errors")
    logger.exception(
        "unhandled_error",
        path=request.url.path,
        method=request.method,
        exc_type=type(exc).__name__,
    )
    err = BasefloError(
        error_code="BF-INTERNAL-000",
        message="Internal server error.",
        status_code=500,
    )
    return JSONResponse(status_code=err.status_code, content=_envelope(err, request_id))


def install_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(BasefloError, _handle_baseflo_error)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, _handle_validation_error)  # type: ignore[arg-type]
    app.add_exception_handler(StarletteHTTPException, _handle_http_exception)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, _handle_unhandled_error)
