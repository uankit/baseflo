"""Typed I/O for IntentInterpreter.

Per docs/40-features/AGENT-INT.md §3.2. Parses a user's natural-language
refinement request ("add wishlists", "track returns separately", "rename
'plan' to 'tier'") into a typed `RefinementIntent` enum the downstream
analyzer can reason about without reading the raw text.

The agent is a SEMANTIC decision-maker — kind detection from a sentence is
exactly the kind of judgement the docs say belongs to an agent, not regex.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from app.engines.schema.ir import SchemaIR


class IntentKind(StrEnum):
    ADD_TABLE = "add_table"
    REMOVE_TABLE = "remove_table"
    ADD_COLUMN = "add_column"
    REMOVE_COLUMN = "remove_column"
    RENAME_COLUMN = "rename_column"
    ADD_RELATIONSHIP = "add_relationship"
    REMOVE_RELATIONSHIP = "remove_relationship"
    ADD_KPI = "add_kpi"
    REMOVE_KPI = "remove_kpi"
    SPLIT_TABLE = "split_table"
    MERGE_TABLES = "merge_tables"
    OTHER = "other"


class IntentInterpreterInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request: str = Field(min_length=2, max_length=2000)
    """The user's natural-language refinement request."""
    parent_ir: SchemaIR
    """The current schema; the agent grounds its interpretation against it."""


class RefinementIntent(BaseModel):
    """Typed interpretation of one refinement request.

    The agent's job is to map a sentence to ONE intent (the dominant one).
    Compound requests ("add wishlists AND remove orders.note") yield two
    separate refinements; the orchestrator runs them sequentially.
    """

    model_config = ConfigDict(extra="forbid")
    kind: IntentKind
    target: str = Field(min_length=1, max_length=200)
    """The thing being acted on. Format depends on kind:
       - ADD_TABLE / REMOVE_TABLE / SPLIT_TABLE: table name (snake_case).
       - ADD_COLUMN / REMOVE_COLUMN: 'table.column'.
       - RENAME_COLUMN: 'table.old_column'.
       - ADD_RELATIONSHIP: 'from_table↔to_table'.
       - ADD_KPI / REMOVE_KPI: KPI name."""
    payload: dict[str, str] = Field(default_factory=dict)
    """Extra typed details. Keys depend on kind. RENAME_COLUMN carries
    `new_name`; ADD_RELATIONSHIP carries `cardinality`; etc."""
    rationale: str = Field(min_length=1, max_length=500)
    """Why the agent classified the request this way. Trace-only."""


class IntentInterpreterOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    intents: list[RefinementIntent] = Field(min_length=1, max_length=5)
    """1..5 intents. The agent's prompt forbids more than 5 — refinements
    spanning many intents are pushed back to the user for splitting."""
    is_clarification_needed: bool = False
    """Set when the request is ambiguous and the agent can't classify
    confidently; the orchestrator surfaces a follow-up question."""
    clarification_question: str | None = Field(default=None, max_length=500)
