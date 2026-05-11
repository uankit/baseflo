"""Daily-digest composer + delivery.

Per docs/40-features/DIGEST.md. The composer is pure (DigestInput → DigestEmail);
the delivery layer is a tiny Strategy abstraction.
"""

from __future__ import annotations

from app.services.digest.composer import DigestComposer
from app.services.digest.delivery import (
    DeliveryResult,
    DigestDeliveryAdapter,
    LogDelivery,
)
from app.services.digest.headline import build_subject_line
from app.services.digest.render import render_html, render_text
from app.services.digest.types import (
    Anomaly,
    AnomalySeverity,
    BulletSentiment,
    ConnectorIssue,
    CounterSnapshot,
    DigestBullet,
    DigestEmail,
    DigestInput,
    DigestPeriod,
    DigestSection,
    LapsingCustomer,
    RefinementSummary,
    SectionKind,
    TopEvent,
)

__all__ = [
    "Anomaly",
    "AnomalySeverity",
    "BulletSentiment",
    "ConnectorIssue",
    "CounterSnapshot",
    "DeliveryResult",
    "DigestBullet",
    "DigestComposer",
    "DigestDeliveryAdapter",
    "DigestEmail",
    "DigestInput",
    "DigestPeriod",
    "DigestSection",
    "LapsingCustomer",
    "LogDelivery",
    "RefinementSummary",
    "SectionKind",
    "TopEvent",
    "build_subject_line",
    "render_html",
    "render_text",
]
