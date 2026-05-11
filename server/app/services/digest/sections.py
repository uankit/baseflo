"""Section builders.

Per docs/40-features/DIGEST.md §3.3 the digest has four ordered sections:

1. AT_A_GLANCE          — top 3-5 COUNTER KPIs with deltas
2. WORTH_A_LOOK         — anomalies + lapsing list + payment failures + connector issues
3. WHAT_IS_SELLING      — top-N event counts (most-active products / services)
4. RECENT_REFINEMENTS   — project changes since the last digest

Each builder is a pure function: `(DigestInput) -> DigestSection`. Composer
assembles them in order, then trims to the 12-bullet hard cap.

Template Method spirit: each builder shares the same shape (read input,
emit bullets), so adding a new section kind is mechanical (per docs §4).
"""

from __future__ import annotations

from app.services.digest.types import (
    AnomalySeverity,
    BulletSentiment,
    DigestBullet,
    DigestInput,
    DigestSection,
    SectionKind,
)


__all__ = [
    "build_at_a_glance",
    "build_recent_refinements",
    "build_what_is_selling",
    "build_worth_a_look",
]


_AT_A_GLANCE_LIMIT = 5
_WHAT_IS_SELLING_LIMIT = 5
_RECENT_REFINEMENTS_LIMIT = 5


# ---------- Helpers ----------


def _format_value(value: float, unit: str | None) -> str:
    if unit == "$":
        if abs(value) >= 1_000:
            return f"${value:,.0f}"
        return f"${value:.2f}"
    if value == int(value):
        formatted = f"{int(value):,}"
    else:
        formatted = f"{value:,.2f}"
    if unit:
        return f"{formatted} {unit}"
    return formatted


def _format_delta(delta_pct: float | None) -> str | None:
    if delta_pct is None:
        return None
    sign = "+" if delta_pct >= 0 else ""
    return f"{sign}{delta_pct:.0f}% vs trailing 7-day avg"


def _delta_sentiment(delta_pct: float | None) -> BulletSentiment:
    if delta_pct is None:
        return BulletSentiment.INFO
    if delta_pct > 0:
        return BulletSentiment.POSITIVE
    if delta_pct < 0:
        return BulletSentiment.NEGATIVE
    return BulletSentiment.NEUTRAL


def _deep_link(input_: DigestInput, suffix: str) -> str:
    base = input_.deep_link_url_base.rstrip("/")
    if not suffix:
        return base
    return f"{base}/{suffix.lstrip('/')}"


# ---------- Section builders ----------


def build_at_a_glance(input_: DigestInput) -> DigestSection | None:
    """Top 3-5 counter KPIs with delta vs trailing-7-day avg.

    Returns None when no counter snapshots are available; the composer drops
    empty sections rather than emitting a heading with nothing under it.
    """
    if not input_.counter_kpis:
        return None

    # Stable order: largest value first, then name asc for tie-breaks.
    top = sorted(
        input_.counter_kpis,
        key=lambda s: (-s.value, s.kpi_name),
    )[:_AT_A_GLANCE_LIMIT]

    bullets = [
        DigestBullet(
            text=f"{snap.label}: {_format_value(snap.value, snap.unit)}",
            sentiment=_delta_sentiment(snap.delta_pct),
            delta=_format_delta(snap.delta_pct),
        )
        for snap in top
    ]
    return DigestSection(
        kind=SectionKind.AT_A_GLANCE,
        title="At a glance",
        bullets=bullets,
        deep_link_url=_deep_link(input_, "analytics"),
    )


def build_worth_a_look(input_: DigestInput) -> DigestSection:
    """Anomalies + lapsing customers + payment failures + connector issues.

    Always returns the section, even if empty — the doc says
    'Empty section = no problems detected', which is a positive signal worth
    surfacing explicitly rather than hiding.
    """
    bullets: list[DigestBullet] = []

    # Anomalies first; HIGH severity bumped above MEDIUM/LOW deterministically.
    severity_order: dict[AnomalySeverity, int] = {
        AnomalySeverity.HIGH: 0,
        AnomalySeverity.MEDIUM: 1,
        AnomalySeverity.LOW: 2,
    }
    for anomaly in sorted(
        input_.anomalies,
        key=lambda a: (severity_order[a.severity], a.kpi_name),
    ):
        bullets.append(
            DigestBullet(
                text=anomaly.description,
                sentiment=BulletSentiment.NEGATIVE,
            )
        )

    if input_.payment_failures > 0:
        plural = "" if input_.payment_failures == 1 else "s"
        bullets.append(
            DigestBullet(
                text=(
                    f"{input_.payment_failures} payment failure{plural} "
                    "since the last digest."
                ),
                sentiment=BulletSentiment.NEGATIVE,
            )
        )

    for customer in input_.lapsing_customers:
        bullets.append(
            DigestBullet(
                text=(
                    f"{customer.customer_name} hasn't done a "
                    f"{customer.last_activity_kind} in "
                    f"{customer.days_since_last_activity} days."
                ),
                sentiment=BulletSentiment.NEUTRAL,
            )
        )

    for issue in input_.connector_issues:
        bullets.append(
            DigestBullet(
                text=f"{issue.connector_name}: {issue.description}",
                sentiment=BulletSentiment.NEGATIVE,
            )
        )

    if not bullets:
        bullets.append(
            DigestBullet(
                text="Nothing flagged. Quiet day.",
                sentiment=BulletSentiment.POSITIVE,
            )
        )

    return DigestSection(
        kind=SectionKind.WORTH_A_LOOK,
        title="Worth a look",
        bullets=bullets,
        deep_link_url=_deep_link(input_, "analytics?tab=anomalies"),
    )


def build_what_is_selling(input_: DigestInput) -> DigestSection | None:
    """Top-N highest-volume events for the period."""
    if not input_.top_events:
        return None

    top = sorted(
        input_.top_events,
        key=lambda e: (-e.count, e.event_name),
    )[:_WHAT_IS_SELLING_LIMIT]

    bullets = [
        DigestBullet(
            text=f"{event.label}: {event.count:,}",
            sentiment=_delta_sentiment(event.delta_pct),
            delta=_format_delta(event.delta_pct),
        )
        for event in top
    ]
    return DigestSection(
        kind=SectionKind.WHAT_IS_SELLING,
        title="What's selling",
        bullets=bullets,
        deep_link_url=_deep_link(input_, "analytics?tab=events"),
    )


def build_recent_refinements(input_: DigestInput) -> DigestSection | None:
    """Project-schema changes since the last digest."""
    if not input_.recent_refinements:
        return None

    refinements = sorted(
        input_.recent_refinements, key=lambda r: r.completed_at, reverse=True,
    )[:_RECENT_REFINEMENTS_LIMIT]

    bullets = [
        DigestBullet(text=ref.summary, sentiment=BulletSentiment.INFO)
        for ref in refinements
    ]
    return DigestSection(
        kind=SectionKind.RECENT_REFINEMENTS,
        title="Recent refinements",
        bullets=bullets,
        deep_link_url=_deep_link(input_, "history"),
    )
