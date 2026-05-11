"""Structured error handling."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class BasefloError(Exception):
    """Domain error with structured metadata."""

    message: str
    error_code: str = "BF-UNKNOWN"
    status_code: int = 500
    details: dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        return f"[{self.error_code}] {self.message}"
