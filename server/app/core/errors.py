"""Typed errors with `BF-AREA-NNN` codes.

Per docs/05-coding-rules.md §5.1, every failure path raises a `BasefloError`.
Per-feature codes are documented in `docs/40-features/<feature>.md`.
"""

from __future__ import annotations

import re
from typing import Any

# Identifier-safety regex: only legitimate semantic-free regex use in core.
# (See docs/05-coding-rules.md §1.2 — structural validation, not semantic.)
_ERROR_CODE_PATTERN = re.compile(r"^BF-[A-Z][A-Z0-9_-]+-[0-9]{3}$")


class BasefloError(Exception):
    """Typed error carrying a stable error code.

    All API responses surface `error_code`, `message`, `details`, and `request_id`.
    Subclassing is allowed and encouraged for domain-specific errors that bind
    a default `error_code` (e.g., `BadRequestError`, `UnauthorizedError`).

    Args:
        error_code: `BF-AREA-NNN` per the registry.
        message:    User-safe message; never includes raw secret values.
        status_code: HTTP status to return. Defaults to 500.
        details:    Optional dict of structured context. PII must be omitted.
        cause:      Original exception for chaining (`raise ... from cause`).

    Examples:
        >>> raise BasefloError(
        ...     error_code="BF-VALID-002",
        ...     message="Required field missing: customer_id",
        ...     status_code=400,
        ...     details={"field": "customer_id"},
        ... )
    """

    def __init__(
        self,
        *,
        error_code: str,
        message: str,
        status_code: int = 500,
        details: dict[str, Any] | None = None,
        cause: BaseException | None = None,
    ) -> None:
        if not _ERROR_CODE_PATTERN.match(error_code):
            raise ValueError(
                f"Error code {error_code!r} does not match BF-AREA-NNN format. "
                "See docs/05-coding-rules.md §5.1."
            )
        super().__init__(message)
        self.error_code = error_code
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        if cause is not None:
            self.__cause__ = cause

    def to_dict(self, request_id: str | None = None) -> dict[str, Any]:
        body: dict[str, Any] = {
            "error_code": self.error_code,
            "message": self.message,
            "details": self.details,
        }
        if request_id is not None:
            body["request_id"] = request_id
        return body

    def __repr__(self) -> str:
        return (
            f"BasefloError(error_code={self.error_code!r}, "
            f"status_code={self.status_code}, "
            f"message={self.message!r})"
        )


# ---------- Common subclasses (thin convenience wrappers) ----------


class ValidationError(BasefloError):
    """Request payload or input validation failed."""

    def __init__(
        self,
        message: str,
        *,
        error_code: str = "BF-VALID-001",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            error_code=error_code, message=message, status_code=400, details=details
        )


class UnauthorizedError(BasefloError):
    """Authentication required or invalid."""

    def __init__(
        self,
        message: str = "Authentication required.",
        *,
        error_code: str = "BF-AUTH-001",
    ) -> None:
        super().__init__(error_code=error_code, message=message, status_code=401)


class ForbiddenError(BasefloError):
    """Authenticated but insufficient permission."""

    def __init__(
        self,
        message: str = "Insufficient permission.",
        *,
        error_code: str = "BF-AUTH-002",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            error_code=error_code, message=message, status_code=403, details=details
        )


class NotFoundError(BasefloError):
    """Resource does not exist or is not visible to the actor."""

    def __init__(
        self,
        message: str = "Resource not found.",
        *,
        error_code: str = "BF-API-001",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            error_code=error_code, message=message, status_code=404, details=details
        )


class ConflictError(BasefloError):
    """State conflict (e.g., idempotency key reuse with different payload)."""

    def __init__(
        self,
        message: str,
        *,
        error_code: str = "BF-VALID-009",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            error_code=error_code, message=message, status_code=409, details=details
        )


class RateLimitedError(BasefloError):
    """Per-tenant or per-IP rate limit exceeded."""

    def __init__(
        self,
        message: str = "Rate limit exceeded.",
        *,
        retry_after_seconds: int | None = None,
        error_code: str = "BF-API-002",
    ) -> None:
        details: dict[str, Any] = {}
        if retry_after_seconds is not None:
            details["retry_after_seconds"] = retry_after_seconds
        super().__init__(
            error_code=error_code, message=message, status_code=429, details=details
        )
