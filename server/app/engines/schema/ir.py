"""Schema IR — typed Pydantic models.

Per docs/40-features/IR-CORE.md §3.2. Every IR object is a strict Pydantic v2
model; equality is by value; hashes are stable across processes once the IR
is normalized via `transforms.normalize`.

Identifier names (table names, column names) are constrained at the model
level by regex — the only legitimate regex use here per docs/05-coding-rules
§1.2 (structural validation, not semantic decision).
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.engines.schema.enums import (
    Cardinality,
    JoinTransform,
    MergeStrategy,
    OnDelete,
    PhysicalType,
    PrimaryKeyStrategy,
    SemanticType,
    SourceRole,
)

# Identifier pattern: snake_case, must start with a letter, max 63 chars
# (Postgres' default identifier length limit). Used by `ColumnIR.name`,
# `TableIR.name`, etc.
IDENTIFIER_PATTERN = r"^[a-z][a-z0-9_]*$"

_FrozenConfig: ConfigDict = ConfigDict(frozen=True, extra="forbid")


class SourceRef(BaseModel):
    """A reference back to a particular column in a particular source table.

    Carried on `ColumnIR.sources` and `TableIR.sources` for traceability —
    enables the admin UI to show which source contributed each field.
    """

    model_config = _FrozenConfig
    connector_name: str = Field(min_length=2, max_length=64)
    source_table: str = Field(min_length=1, max_length=255)
    source_column: str | None = Field(default=None, max_length=255)


SourcePair = Annotated[list[SourceRef], Field(min_length=2, max_length=2)]


class ColumnIR(BaseModel):
    """A column in a unified table.

    Decision boundary recap (per docs/40-features/IR-CORE.md):
    - `semantic_type` is the agent's call (column meaning).
    - `physical_type` follows from semantic_type + observed values.
    - For MONEY columns, currency is expressed in ONE of three shapes
      (mutually exclusive, validated by `compatibility._check_money_columns`):
        * `currency`: ISO-4217 code, all rows share this currency.
        * `currency_column`: name of a sibling column on the same table that
          carries the per-row ISO code (multi-currency data).
        * neither set: currency unknown — surfaced as a workspace assumption,
          treated as "ask at query time" by downstream code.
    - `enum_values` is required when semantic_type == STATUS.
    - `pii_masked_by_default` is required-True when semantic_type starts with PII_.
    """

    model_config = _FrozenConfig

    name: str = Field(pattern=IDENTIFIER_PATTERN, min_length=1, max_length=63)
    label: str = Field(min_length=1, max_length=200)
    semantic_type: SemanticType
    physical_type: PhysicalType
    nullable: bool = True
    default: str | int | float | bool | None = None
    enum_values: list[str] | None = None
    currency: Annotated[str | None, Field(default=None, pattern=r"^[A-Z]{3}$|^$")] = None
    currency_column: str | None = Field(default=None, pattern=IDENTIFIER_PATTERN, max_length=63)
    """Name of a sibling column on the same table that holds the per-row ISO
    currency code. Mutually exclusive with `currency`."""
    is_minor_unit: bool = False
    sources: list[SourceRef] = Field(default_factory=list)
    pii_masked_by_default: bool = False
    description: str | None = Field(default=None, max_length=2000)


class JoinKey(BaseModel):
    """How rows from two source tables correspond for the purpose of merging
    them into one reconciled entity."""

    model_config = _FrozenConfig
    source_a: SourceRef
    source_b: SourceRef
    columns_a: list[str] = Field(min_length=1)
    columns_b: list[str] = Field(min_length=1)
    transformation: JoinTransform = JoinTransform.LOWERCASE_TRIM


class SourceContribution(BaseModel):
    """How a particular source contributes to a reconciled entity."""

    model_config = _FrozenConfig
    connector_name: str
    source_table: str
    role: SourceRole = SourceRole.AUGMENTING


class ReconciliationPolicy(BaseModel):
    """Set when a TableIR is fed by 2+ sources. Captures conflict resolution."""

    model_config = _FrozenConfig
    join_keys: list[JoinKey] = Field(min_length=1)
    authoritative_source: dict[str, str] = Field(default_factory=dict)
    """Map of canonical_column_name → connector_name that wins on conflict."""
    merge_strategy: MergeStrategy = MergeStrategy.PREFERRED_SOURCE
    primary_key_strategy: PrimaryKeyStrategy = PrimaryKeyStrategy.GENERATED_UUID


class TableIR(BaseModel):
    model_config = _FrozenConfig

    name: str = Field(pattern=IDENTIFIER_PATTERN, min_length=1, max_length=63)
    label: str = Field(min_length=1, max_length=200)
    purpose: str = Field(min_length=1, max_length=2000)
    grain: str = Field(min_length=1, max_length=200)
    """Plain English: 'one row per ___'."""
    primary_key: list[str] = Field(min_length=1)
    columns: list[ColumnIR] = Field(min_length=1)
    sources: list[SourceRef] = Field(default_factory=list)
    is_reconciled: bool = False
    reconciliation_policy: ReconciliationPolicy | None = None


class IndexIR(BaseModel):
    """Explicit index. The compiler auto-adds FK indexes; this is for any
    non-FK index the agent or compiler decides is worth declaring."""

    model_config = _FrozenConfig
    name: str = Field(pattern=IDENTIFIER_PATTERN)
    table: str = Field(pattern=IDENTIFIER_PATTERN)
    columns: list[str] = Field(min_length=1)
    unique: bool = False
    partial_predicate: str | None = None


class RelationshipIR(BaseModel):
    """A typed FK-style relationship between two tables.

    The compiler places the FK on the many-side per cardinality direction.
    """

    model_config = _FrozenConfig
    name: str = Field(pattern=IDENTIFIER_PATTERN)
    from_table: str = Field(pattern=IDENTIFIER_PATTERN)
    from_columns: list[str] = Field(min_length=1)
    to_table: str = Field(pattern=IDENTIFIER_PATTERN)
    to_columns: list[str] = Field(min_length=1)
    cardinality: Cardinality
    on_delete: OnDelete = OnDelete.RESTRICT
    optional_from: bool = False
    optional_to: bool = False
    source_pair: SourcePair | None = None


class Assumption(BaseModel):
    """Explicit assumption surfaced by an agent, displayed on the workspace.

    Lets users see *why* the unified model looks the way it does ('Stripe is
    authoritative for billing fields') without requiring them to read traces.
    """

    model_config = _FrozenConfig
    target: str = Field(min_length=1, max_length=200)
    """e.g. 'table:customers' or 'relationship:orders↔customers'."""
    text: str = Field(min_length=1, max_length=1000)
    source_agent: str = Field(min_length=2, max_length=80)


class SchemaIR(BaseModel):
    """The whole unified data model for one project version."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: int = Field(default=1, ge=1)
    tables: list[TableIR] = Field(min_length=1)
    relationships: list[RelationshipIR] = Field(default_factory=list)
    indexes: list[IndexIR] = Field(default_factory=list)
    assumptions: list[Assumption] = Field(default_factory=list)
    parent_version_id: UUID | None = None
    composed_at: datetime
    composed_by: str = Field(min_length=2, max_length=200)
    """Agent name + run id; for traceability when debugging."""

    def table_by_name(self, name: str) -> TableIR | None:
        for table in self.tables:
            if table.name == name:
                return table
        return None
