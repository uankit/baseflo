"""Pure event-payload validator.

Per docs/40-features/ANALYTICS.md §4.2. Given an `EventTaxonomy` and an
incoming event descriptor, decide whether it's structurally valid:
  - Name must be in the taxonomy.
  - Status-transition events must carry a `properties.status_value` that
    matches the taxonomy entry's `status_value`.

Pure function: same inputs → same outcome. No DB, no side effects.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.engines.analytics.taxonomy import (
    EventDefinition,
    EventOrigin,
    EventTaxonomy,
)


__all__ = [
    "EventDescriptor",
    "ValidationOutcome",
    "validate_event",
]


@dataclass(frozen=True, slots=True)
class EventDescriptor:
    """The fields the validator inspects.

    `properties` is the user-supplied payload bag; the validator only reads
    the keys the taxonomy demands (e.g., `status_value`).
    """

    name: str
    properties: dict[str, Any]


@dataclass(frozen=True, slots=True)
class ValidationOutcome:
    """Result of validating a single event."""

    valid: bool
    matched: EventDefinition | None = None
    reason: str | None = None
    """User-safe reason on rejection. Always set when valid is False."""

    @classmethod
    def ok(cls, event: EventDefinition) -> "ValidationOutcome":
        return cls(valid=True, matched=event, reason=None)

    @classmethod
    def reject(cls, reason: str) -> "ValidationOutcome":
        return cls(valid=False, matched=None, reason=reason)


# ---------- Public ----------


def validate_event(
    *, descriptor: EventDescriptor, taxonomy: EventTaxonomy
) -> ValidationOutcome:
    """Validate one event descriptor against a taxonomy.

    The taxonomy is the authoritative event catalogue for a project version;
    callers obtain it via `build_event_taxonomy(project_version.schema_ir)`
    or by reading the version's pre-computed `intelligence_taxonomy` field.
    """
    matched = taxonomy.by_name(descriptor.name)
    if matched is None:
        return ValidationOutcome.reject(
            f"Event {descriptor.name!r} is not in the project's taxonomy."
        )

    if matched.origin == EventOrigin.STATUS_TRANSITION:
        supplied = descriptor.properties.get("status_value")
        if supplied != matched.status_value:
            return ValidationOutcome.reject(
                f"Event {descriptor.name!r} requires properties.status_value="
                f"{matched.status_value!r}; got {supplied!r}."
            )

    return ValidationOutcome.ok(matched)
