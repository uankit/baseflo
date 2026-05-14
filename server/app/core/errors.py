from __future__ import annotations

from typing import Any


class AppError(Exception):
    """Application-level error with structured metadata for API mapping.

    Shape matches `connectors.ConnectorError` so the two error families compose
    cleanly. Subclasses are semantic (AuthError, NotFoundError, ...) — they do
    not change behavior, only signal intent at call sites.
    """

    def __init__(
        self,
        *,
        message: str,
        code: str,
        status_hint: int = 400,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_hint = status_hint
        self.details = details or {}

    def __str__(self) -> str:
        return f"[{self.code}] {self.message}"


class AuthError(AppError):
    """Authentication or authorization failed."""


class NotFoundError(AppError):
    """Requested resource doesn't exist."""


class ConflictError(AppError):
    """State conflict (duplicate, invalid transition)."""


class ValidationError(AppError):
    """Input failed semantic validation beyond schema check."""


class RateLimitError(AppError):
    """Rate limit exceeded."""
