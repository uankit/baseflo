"""Schema-aware event taxonomy generator.

Per docs/40-features/ANALYTICS.md §3.2. Walks the unified `SchemaIR` and
emits the typed event-name catalog the project supports. The SDK validates
every `events.track(...)` call against this list; the digest composer reads
it to know which events are worth surfacing.

Pure deterministic — no agents, no string heuristics. Event names are
derived MECHANICALLY from semantic types, not from column names.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from app.engines.schema.enums import (
    Cardinality,
    SemanticType,
)
from app.engines.schema.ir import RelationshipIR, SchemaIR, TableIR


__all__ = [
    "EventDefinition",
    "EventOrigin",
    "EventTaxonomy",
    "build_event_taxonomy",
]


class EventOrigin(StrEnum):
    ENTITY_CREATED = "entity_created"
    """Fires when a new row of a reconciled entity is created."""

    STATUS_TRANSITION = "status_transition"
    """Fires when a STATUS column transitions to a particular enum value."""

    RELATIONSHIP_ADDED = "relationship_added"
    """Fires when a row appears on the many-side of a relationship."""


class EventDefinition(BaseModel):
    """Typed entry in the project's event taxonomy.

    The SDK and ingestion endpoint use this to validate event names.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(min_length=2, max_length=120, pattern=r"^[a-z][a-z0-9_]*$")
    table_name: str = Field(min_length=1, max_length=63)
    origin: EventOrigin
    description: str = Field(min_length=1, max_length=500)
    status_value: str | None = None
    """Set when origin == STATUS_TRANSITION."""


class EventTaxonomy(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    events: list[EventDefinition] = Field(default_factory=list)

    def names(self) -> list[str]:
        return [e.name for e in self.events]

    def by_name(self, name: str) -> EventDefinition | None:
        for e in self.events:
            if e.name == name:
                return e
        return None


# ---------- Internal builders ----------


def _singular(table_name: str) -> str:
    """Best-effort singularisation for event names.

    M1 uses a tiny rule (drop trailing 's'); good enough for the deterministic
    cases the agent layer produces (`customers`, `orders`, `products`).
    Future enhancement: make this configurable per table via the IR's
    `label`/`grain` fields the agent already populates.
    """
    if table_name.endswith("ies") and len(table_name) > 3:
        return table_name[:-3] + "y"
    if table_name.endswith("s") and len(table_name) > 1:
        return table_name[:-1]
    return table_name


def _entity_created_event(table: TableIR) -> EventDefinition:
    singular = _singular(table.name)
    return EventDefinition(
        name=f"{singular}_created",
        table_name=table.name,
        origin=EventOrigin.ENTITY_CREATED,
        description=f"A row was inserted into {table.name}.",
    )


def _status_transition_events(table: TableIR) -> list[EventDefinition]:
    """One event per (status_column, observed enum_value)."""
    out: list[EventDefinition] = []
    singular = _singular(table.name)
    status_columns = [c for c in table.columns if c.semantic_type == SemanticType.STATUS]
    for col in status_columns:
        if not col.enum_values:
            continue
        for value in col.enum_values:
            # Sanitize the status value into the event-name token.
            value_token = value.lower().replace(" ", "_").replace("-", "_")
            # Drop any non-alphanumeric/underscore character.
            value_token = "".join(
                ch for ch in value_token if ch.isalnum() or ch == "_"
            )
            if not value_token:
                continue
            out.append(
                EventDefinition(
                    name=f"{singular}_{value_token}",
                    table_name=table.name,
                    origin=EventOrigin.STATUS_TRANSITION,
                    description=(
                        f"{table.name}.{col.name} transitioned to {value!r}."
                    ),
                    status_value=value,
                )
            )
    return out


def _relationship_added_events(
    table_index: dict[str, TableIR], relationships: list[RelationshipIR]
) -> list[EventDefinition]:
    """For each relationship that has a clear many-side, emit an event for
    the act of associating a row on that side."""
    out: list[EventDefinition] = []
    for rel in relationships:
        # The many-side is `from_table` for *..1 and `to_table` for 1..*.
        if rel.cardinality == Cardinality.MANY_TO_ONE:
            many_side = rel.from_table
            one_side = rel.to_table
        elif rel.cardinality == Cardinality.ONE_TO_MANY:
            many_side = rel.to_table
            one_side = rel.from_table
        else:
            # M2M and 1..1 don't yield a clear add-side event; skip in M1.
            continue

        many_table = table_index.get(many_side)
        if many_table is None:
            continue

        many_singular = _singular(many_side)
        one_singular = _singular(one_side)

        out.append(
            EventDefinition(
                name=f"{one_singular}_{many_singular}_added",
                table_name=many_side,
                origin=EventOrigin.RELATIONSHIP_ADDED,
                description=(
                    f"A {many_singular} was associated with a {one_singular}."
                ),
            )
        )
    return out


def build_event_taxonomy(ir: SchemaIR) -> EventTaxonomy:
    """Derive the typed event taxonomy from a unified SchemaIR.

    Names are deterministic; identical IRs produce byte-identical taxonomies
    (modulo `composed_at`-driven IR reordering, which `transforms.normalize`
    handles upstream).

    Duplicate names — possible when two tables singularise to the same token
    (`orders` + `order_items` both yielding `order_created`) — are de-duped
    in insertion order; the FIRST occurrence wins. This is intentional and deterministic.
    """
    table_index = {t.name: t for t in ir.tables}

    events: list[EventDefinition] = []
    seen_names: set[str] = set()

    def _push(event: EventDefinition) -> None:
        if event.name in seen_names:
            return
        events.append(event)
        seen_names.add(event.name)

    for table in ir.tables:
        _push(_entity_created_event(table))
        for status_event in _status_transition_events(table):
            _push(status_event)

    for rel_event in _relationship_added_events(table_index, ir.relationships):
        _push(rel_event)

    return EventTaxonomy(events=events)
