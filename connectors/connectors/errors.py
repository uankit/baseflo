from __future__ import annotations


class ConnectorError(Exception):
    """Base error raised by any connector. Carries a stable code for API mapping."""

    def __init__(self, *, message: str, code: str, status_hint: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_hint = status_hint


class AuthError(ConnectorError):
    """Authentication or authorization with the source failed."""


class IntrospectError(ConnectorError):
    """Schema discovery failed."""


class ReadError(ConnectorError):
    """Reading rows from the source failed."""


class WriteError(ConnectorError):
    """Writing back to the source failed."""


class ConfigError(ConnectorError):
    """Connector configuration is invalid or incomplete."""
