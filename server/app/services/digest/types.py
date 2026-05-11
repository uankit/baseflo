"""Typed I/O for the daily-digest composer.

Per docs/40-features/DIGEST.md §3.2. Every type is Pydantic v2; the composer
takes a `DigestInput` and produces a `DigestEmail`, which the delivery layer
sends.

Keeping this in its own module so the renderer + headline + composer + tests
all consume the same shapes without circular imports.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


__all__ = [
    "Anomaly",
    "AnomalySeverity",
    "BulletSentiment",
    "ConnectorIssue",
    "CounterSnapshot",
    "DigestBullet",
    "DigestEmail",
    "DigestInput",
    "DigestPeriod",
    "DigestSection",
    "LapsingCustomer",
    "RefinementSummary",
    "SectionKind",
    "TopEvent",
]


_FrozenConfig: ConfigDict = ConfigDict(frozen=True, extra="forbid")


# ---------- Enums ----------


class DigestPeriod(StrEnum):
    YESTERDAY = "yesterday"
    LAST_WEEK = "last_week"


class SectionKind(StrEnum):
    AT_A_GLANCE = "at_a_glance"
    WORTH_A_LOOK = "worth_a_look"
    WHAT_IS_SELLING = "what_is_selling"
    RECENT_REFINEMENTS = "recent_refinements"


class BulletSentiment(StrEnum):
    INFO = "info"
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"


class AnomalySeverity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


# ---------- Composer-input building blocks ----------


class CounterSnapshot(BaseModel):
    """One pre-aggregated COUNTER KPI snapshot the composer renders.

    `delta_pct` is current vs the comparable prior period (trailing-7-day
    average for daily digests). None means "no prior data; suppress delta".
    """

    model_config = _FrozenConfig
    kpi_name: str = Field(min_length=1, max_length=120)
    label: str = Field(min_length=1, max_length=200)
    value: float
    prior_value: float | None = None
    delta_pct: float | None = None
    unit: str | None = Field(default=None, max_length=40)
    """Plain unit string ('orders', '$', 'signups')."""


class Anomaly(BaseModel):
    """An anomaly the analytics layer flagged."""

    model_config = _FrozenConfig
    kpi_name: str
    description: str = Field(min_length=1, max_length=500)
    severity: AnomalySeverity = AnomalySeverity.MEDIUM


class LapsingCustomer(BaseModel):
    """A customer who looks at risk of churning. Ranked by composite score."""

    model_config = _FrozenConfig
    customer_name: str = Field(min_length=1, max_length=200)
    days_since_last_activity: int = Field(ge=0)
    last_activity_kind: str = Field(min_length=1, max_length=80)


class ConnectorIssue(BaseModel):
    """Connector health issue worth notifying."""

    model_config = _FrozenConfig
    connector_name: str
    description: str = Field(min_length=1, max_length=500)


class TopEvent(BaseModel):
    """Aggregated event count for one event name in the digest window."""

    model_config = _FrozenConfig
    event_name: str = Field(min_length=2, max_length=120)
    label: str = Field(min_length=1, max_length=200)
    count: int = Field(ge=0)
    delta_pct: float | None = None


class RefinementSummary(BaseModel):
    model_config = _FrozenConfig
    summary: str = Field(min_length=1, max_length=300)
    completed_at: datetime


class DigestInput(BaseModel):
    """All facts the composer needs. Pre-aggregated by the runner."""

    model_config = ConfigDict(extra="forbid")

    project_id: UUID
    project_name: str = Field(min_length=1, max_length=200)
    user_id: UUID
    period: DigestPeriod
    period_start: datetime
    period_end: datetime
    deep_link_url_base: str = Field(min_length=1, max_length=500)
    """Project workspace URL stub; section deep links are appended."""

    counter_kpis: list[CounterSnapshot] = Field(default_factory=list)
    anomalies: list[Anomaly] = Field(default_factory=list)
    lapsing_customers: list[LapsingCustomer] = Field(default_factory=list)
    payment_failures: int = Field(default=0, ge=0)
    connector_issues: list[ConnectorIssue] = Field(default_factory=list)
    top_events: list[TopEvent] = Field(default_factory=list)
    recent_refinements: list[RefinementSummary] = Field(default_factory=list)


# ---------- Composer-output building blocks ----------


class DigestBullet(BaseModel):
    model_config = _FrozenConfig
    text: str = Field(min_length=1, max_length=300)
    sentiment: BulletSentiment = BulletSentiment.INFO
    delta: str | None = Field(default=None, max_length=80)


class DigestSection(BaseModel):
    model_config = _FrozenConfig
    kind: SectionKind
    title: str = Field(min_length=1, max_length=120)
    bullets: list[DigestBullet] = Field(default_factory=list)
    deep_link_url: str | None = Field(default=None, max_length=500)


class DigestEmail(BaseModel):
    model_config = _FrozenConfig
    subject: str = Field(min_length=1, max_length=200)
    sections: list[DigestSection] = Field(default_factory=list)
    project_id: UUID
    user_id: UUID
    period: DigestPeriod
    composed_at: datetime
