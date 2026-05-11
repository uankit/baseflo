# `IR-CORE` — Schema IR (Canonical Layer)

Status: M0–M1. The contract between agents and deterministic compilers. Every other engine feature depends on this one.

---

## 1. Overview

The Schema IR is the canonical, dialect-agnostic representation of a unified business data model. Agents produce strongly-typed IR objects. Deterministic compilers consume them and emit DDL, admin-UI specs, SDK types, KPI SQL, migrations, and more. **Nothing crosses the agent ↔ compiler boundary that isn't an IR object.** No `dict[str, Any]`, no untyped JSON, no string templates — only typed Pydantic models.

The IR is also **the stable contract** during refinement: a refinement is a typed diff against an IR, not a freeform schema rewrite.

## 2. High-Level Design

```
        ┌─────────────────┐         ┌──────────────────┐
        │ Agent outputs   │         │ Compilers        │
        │ (per specialist)│ ──IR──▶ │ (deterministic)  │
        └─────────────────┘         └──────────────────┘
                                              │
                          ┌───────────┬───────┴──────┬──────────────────┐
                          ▼           ▼              ▼                  ▼
                     Postgres DDL  Admin UI Spec  SDK TypeScript    KPI SQL +
                     (per dialect) (TanStack)     Methods           DuckDB exec
```

The IR encodes:
- **Tables** with grain, purpose, primary key, columns, source contributions.
- **Columns** with semantic type (PII / status / money / id / temporal / category / free-text), physical type, nullability, defaults, enum values, currency + minor unit.
- **Relationships** with cardinality, FK direction, on-delete behavior, source-pair contributions.
- **Indexes** — explicit, never auto-derived.
- **Reconciliation policy** — per reconciled entity, the conflict-resolution and merge strategy.
- **Assumptions** — explicit business decisions surfaced by agents (`"Stripe is authoritative for billing fields"`).
- **Versioning** — schema version, parent-version pointer, change provenance.

## 3. Low-Level Design

### 3.1 Module Layout

```
server/app/engines/schema/
├── ir.py                 # Pydantic models for the IR
├── enums.py              # SemanticType, PhysicalType, Cardinality, OnDelete, MergeStrategy, AuthKind
├── transforms.py         # Pure functions: composer, validator, normalizer, hash, diff
├── compatibility.py      # Compatibility matrices: SemanticType ↔ PhysicalType, etc.
└── tests/
    ├── test_ir_validation.py
    ├── test_ir_transforms.py
    └── fixtures/         # Canonical IR fixtures for downstream test reuse
```

### 3.2 Key Types

```python
# ir.py
from enum import StrEnum
from pydantic import BaseModel, Field
from typing import Annotated

class SemanticType(StrEnum):
    IDENTITY            = "identity"
    FOREIGN_KEY         = "foreign_key"
    MONEY               = "money"
    STATUS              = "status"
    TEMPORAL            = "temporal"
    PII_EMAIL           = "pii_email"
    PII_PHONE           = "pii_phone"
    PII_ADDRESS         = "pii_address"
    PII_NAME            = "pii_name"
    PII_ID_NUMBER       = "pii_id_number"
    CATEGORY            = "category"
    FREE_TEXT           = "free_text"
    BOOLEAN             = "boolean"
    COUNT               = "count"
    DERIVED             = "derived"

class PhysicalType(StrEnum):
    UUID  = "uuid"
    BIGINT = "bigint"
    INT   = "int"
    SMALLINT = "smallint"
    NUMERIC = "numeric"
    TEXT  = "text"
    VARCHAR = "varchar"
    BOOLEAN = "boolean"
    TIMESTAMPTZ = "timestamptz"
    DATE = "date"
    JSONB = "jsonb"
    BYTEA = "bytea"

class Cardinality(StrEnum):
    ONE_TO_ONE   = "1..1"
    ONE_TO_MANY  = "1..*"
    MANY_TO_ONE  = "*..1"
    MANY_TO_MANY = "*..*"

class SourceRef(BaseModel):
    connector_name: str             # "shopify", "postgres", "my_internal_crm"
    source_table: str               # original table/object name in the source
    source_column: str | None = None

class ColumnIR(BaseModel):
    name: str = Field(pattern=r"^[a-z][a-z0-9_]*$", min_length=1, max_length=63)
    label: str                      # user-facing display name
    semantic_type: SemanticType
    physical_type: PhysicalType
    nullable: bool
    default: str | int | float | bool | None = None
    enum_values: list[str] | None = None
    currency: str | None = None     # ISO 4217 when semantic_type == MONEY
    is_minor_unit: bool = False     # True when physical_type == BIGINT for money
    sources: list[SourceRef] = Field(default_factory=list)
    pii_masked_by_default: bool = False
    description: str | None = None

class TableIR(BaseModel):
    name: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    label: str
    purpose: str                    # one-paragraph rationale
    grain: str                      # "one row per ___"
    primary_key: list[str]
    columns: list[ColumnIR]
    sources: list[SourceRef]
    is_reconciled: bool = False     # True when contributed by 2+ sources
    reconciliation_policy: ReconciliationPolicy | None = None

class ReconciliationPolicy(BaseModel):
    join_keys: list[JoinKey]
    authoritative_source: dict[str, str]   # column_name -> connector_name
    merge_strategy: MergeStrategy

class RelationshipIR(BaseModel):
    name: str
    from_table: str
    from_columns: list[str]
    to_table: str
    to_columns: list[str]
    cardinality: Cardinality
    on_delete: OnDelete = OnDelete.RESTRICT
    optional_from: bool = False
    optional_to: bool = False
    source_pair: tuple[SourceRef, SourceRef] | None = None

class IndexIR(BaseModel):
    name: str
    table: str
    columns: list[str]
    unique: bool = False
    partial_predicate: str | None = None

class Assumption(BaseModel):
    target: str                     # "table:customers" | "relationship:orders↔customers"
    text: str                       # plain English
    source_agent: str               # which agent surfaced it

class SchemaIR(BaseModel):
    schema_version: int = 1
    tables: list[TableIR]
    relationships: list[RelationshipIR]
    indexes: list[IndexIR] = Field(default_factory=list)
    assumptions: list[Assumption] = Field(default_factory=list)
    parent_version_id: UUID | None = None
    composed_at: datetime
    composed_by: str                # agent name + run id
```

### 3.3 Core Logic — `transforms.py`

Pure functions, no I/O:

- `compose(*subgraphs) -> SchemaIR` — combine partial outputs from agents into a full IR.
- `validate(ir: SchemaIR) -> ValidationReport` — structural integrity (FK targets exist, primary keys are non-empty, no duplicate table names, every table has at least one column, etc.). Raises `BF-SCHEMA-001` on failure.
- `normalize(ir: SchemaIR) -> SchemaIR` — canonical ordering of tables/columns/relationships for deterministic hashing.
- `hash(ir: SchemaIR) -> str` — stable SHA-256 over normalized JSON. Used for cache keys, change detection, idempotency.
- `diff(parent: SchemaIR, child: SchemaIR) -> SchemaDiff` — typed delta for refinement.
- `apply_diff(parent: SchemaIR, diff: SchemaDiff) -> SchemaIR` — mechanical patch (deterministic merge for refinement).

### 3.4 Compatibility Matrix — `compatibility.py`

Cross-cutting deterministic checks the engine runs after agent composition:

| Check | Condition | Error |
|---|---|---|
| Money columns are minor-unit BIGINT | `semantic_type == MONEY` requires `physical_type == BIGINT` and `is_minor_unit == True` | `BF-SCHEMA-002` |
| Status columns have enum values | `semantic_type == STATUS` requires `enum_values` non-empty | `BF-SCHEMA-003` |
| FK relationship endpoints exist | every `from_table`/`to_table` exists in `tables` | `BF-SCHEMA-004` |
| FK columns exist on referenced tables | every column referenced in a relationship exists | `BF-SCHEMA-005` |
| Primary key columns exist | every column in `primary_key` exists in the table | `BF-SCHEMA-006` |
| No duplicate identifiers | table names unique; column names unique within a table | `BF-SCHEMA-007` |
| Reconciled tables have policy | `is_reconciled == True` requires `reconciliation_policy` | `BF-SCHEMA-008` |
| PII columns mask by default | `semantic_type ∈ PII_*` requires `pii_masked_by_default == True` | `BF-SCHEMA-009` |

These are validators, not heuristics — they verify *structure*, not *meaning*. Meaning is the agent's job.

## 4. Design Patterns Applied

| Pattern | Where | Why |
|---|---|---|
| **Specification** | Validators in `compatibility.py` | Each validator is a typed predicate; composes into `validate(ir)`; new validators added without changing call sites. |
| **Pipe / Functional Composition** | `transforms.py` | All transforms are pure functions; composable; test-friendly. |
| **Value Object** | All IR types are immutable Pydantic v2 models with `frozen=True` | Equality by value enables hash-based caching. |

The IR module is intentionally pattern-light. It's a contract, not a behavior layer.

## 5. Test Plan

- **Unit tests** (`test_ir_validation.py`):
  - Valid IR fixtures pass `validate()`.
  - Each compatibility violation produces the correct `BF-SCHEMA-NNN`.
  - Empty IR fails with `BF-SCHEMA-010`.
- **Property tests** (`test_ir_transforms.py`):
  - `apply_diff(parent, diff(parent, child)) == child` for any pair.
  - `hash(normalize(ir)) == hash(normalize(ir.copy()))` (determinism).
  - `compose(*decompose(ir)) == ir` for the round-trip composition.
- **Fixtures** (`fixtures/`):
  - `single_source_ecommerce.json` — typed ceramics-shop schema (used by 11 downstream tests).
  - `multi_source_yoga_studio.json` — Sheets + Stripe + Mailchimp + Notion reconciled.
  - `pathological_*.json` — invalid IRs covering each `BF-SCHEMA-NNN`.
- **Coverage threshold**: 95%. The IR is foundational; bugs here ripple everywhere.

## 6. Error Codes

| Code | Condition | Recovery |
|---|---|---|
| `BF-SCHEMA-001` | Validation failed (umbrella) | Manager routes repair to source agent. |
| `BF-SCHEMA-002` | Money column is not minor-unit BIGINT | `ConstraintProposer` re-runs with corrected context. |
| `BF-SCHEMA-003` | Status column missing `enum_values` | `ColumnClassifier` re-runs with status-discovery hint. |
| `BF-SCHEMA-004` | FK endpoint references non-existent table | `PhysicalSchemaArchitect` re-runs with table set as additional context. |
| `BF-SCHEMA-005` | FK references non-existent column | Same as above. |
| `BF-SCHEMA-006` | Primary key column missing from table | `PhysicalSchemaArchitect` re-runs. |
| `BF-SCHEMA-007` | Duplicate identifier (table or column) | Manager calls `PhysicalSchemaArchitect` rename pass. |
| `BF-SCHEMA-008` | Reconciled table missing reconciliation policy | `EntityReconciler` re-runs. |
| `BF-SCHEMA-009` | PII column not masked by default | Auto-corrected by `normalize()`; warning logged. |
| `BF-SCHEMA-010` | Empty IR (no tables) | Terminal failure — surfaces as `BF-AGENT-005` upstream. |

Every error code has a test asserting it fires under the specific condition.

## 7. Dependencies

None. The IR is the bottom of the stack.

## 8. Milestone

- **M0:** types defined; validators implemented; fixtures committed; tests at 95% coverage.
- **M1:** referenced by `ColumnClassifier`, `EntityReconciler` (single-source), `PhysicalSchemaArchitect`, `KPIPlanner`, the DDL compiler, and the admin-UI generator.
- **M2:** extended with multi-source reconciliation policy on `TableIR`.
- **M3+:** stable contract; the protocol version (`schema_version`) bumps only with breaking changes and a 6-month deprecation window.
