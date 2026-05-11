"""Subject line generator.

Per docs/40-features/DIGEST.md §3.3 the subject line follows:

    "<Day>: <top_metric_1>, <top_metric_2>, <top_metric_3>, <count> thing(s) to look at"

Anomaly count drives whether opening is worthwhile; metric tally compresses
the most-recent-period activity into a single scannable line.

Pure function: same `DigestInput` → same subject. Easy to test.
"""

from __future__ import annotations

from app.services.digest.types import (
    CounterSnapshot,
    DigestInput,
)


__all__ = ["build_subject_line"]


# Numbers ≥1000 are abbreviated to "1.2k" / "23k" / "1.4m" so the subject line
# fits in mobile previews. Pure deterministic; no locale-sensitivity.
def _humanize_count(value: float, unit: str | None) -> str:
    abs_value = abs(value)
    if unit == "$":
        if abs_value >= 1_000_000:
            return f"${value / 1_000_000:.1f}m"
        if abs_value >= 1_000:
            return f"${value / 1_000:.1f}k"
        if abs_value >= 100:
            return f"${value:.0f}"
        return f"${value:.2f}"
    # Non-money: drop decimals when value is integer-like.
    if abs_value >= 1_000_000:
        formatted = f"{value / 1_000_000:.1f}m"
    elif abs_value >= 1_000:
        formatted = f"{value / 1_000:.1f}k"
    elif value == int(value):
        formatted = f"{int(value)}"
    else:
        formatted = f"{value:.1f}"
    if unit:
        return f"{formatted} {unit}"
    return formatted


def _day_label(input_: DigestInput) -> str:
    """The weekday of `period_end` minus one day (the "yesterday" the digest covers).

    Per the doc's example: "Tuesday: 12 bookings, …" — the weekday refers to the
    *day the digest covers*, which is the day before send time.
    """
    # period_end is the exclusive end of the window. The day covered is end-1d.
    from datetime import timedelta  # noqa: PLC0415 — local to keep top deps tight

    covered_day = input_.period_end - timedelta(days=1)
    return covered_day.strftime("%A")


def _format_metric(snapshot: CounterSnapshot) -> str:
    return _humanize_count(snapshot.value, snapshot.unit)


def build_subject_line(input_: DigestInput) -> str:
    """Compose the subject line. Always non-empty; falls back to a benign
    default when the project has zero data."""
    day = _day_label(input_)

    # Top 3 counters by value. Stable tie-break by name so determinism holds.
    top = sorted(
        input_.counter_kpis,
        key=lambda s: (-s.value, s.kpi_name),
    )[:3]

    metric_parts = [_format_metric(s) for s in top]
    anomaly_count = len(input_.anomalies)
    issues_part = (
        f"{anomaly_count} thing to look at" if anomaly_count == 1
        else f"{anomaly_count} things to look at"
    )

    if not metric_parts:
        if anomaly_count == 0:
            return f"{day}: nothing to flag"
        return f"{day}: {issues_part}"

    if anomaly_count > 0:
        return f"{day}: " + ", ".join(metric_parts) + f", {issues_part}"
    return f"{day}: " + ", ".join(metric_parts)
