"""Typed events + provider enum for webhook ingestion."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


__all__ = [
    "IngestedEvent",
    "IngestedEventOp",
    "ProviderName",
]


class ProviderName(StrEnum):
    SHOPIFY = "shopify"
    STRIPE = "stripe"
    GOOGLE_SHEETS = "google_sheets"


class IngestedEventOp(StrEnum):
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    REFETCH = "refetch"
    """Source signaled "something changed" without telling us what (Sheets
    Drive Push). The reconciler re-fetches the resource."""


class IngestedEvent(BaseModel):
    """One normalized webhook event ready for the reconciler.

    `raw` carries the source payload for trace + replay; the reconciler
    re-fetches via the connector to defeat tampering / stale payloads.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")
    provider: ProviderName
    source_table: str = Field(min_length=1, max_length=120)
    """The connector's source-side table name (e.g., `customers`)."""
    op: IngestedEventOp
    source_id: str | None = Field(default=None, max_length=255)
    """The row's source-side id (Shopify GID, Stripe object id, Sheets row index).
    None for REFETCH events that don't point to a single row."""
    occurred_at: datetime
    raw: dict[str, Any] = Field(default_factory=dict)
    """Source payload for trace + the reconciler's re-fetch logic."""
