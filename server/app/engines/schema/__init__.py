"""Schema IR + DDL compiler.

Per docs/40-features/IR-CORE.md, the IR is the single contract between agents
and deterministic compilers. No path between them carries `dict[str, Any]`.

Sub-modules:
- `enums`         — SemanticType, PhysicalType, Cardinality, OnDelete, MergeStrategy
- `ir`            — Pydantic models: ColumnIR, TableIR, RelationshipIR, IndexIR, SchemaIR
- `compatibility` — cross-cutting deterministic validators (BF-SCHEMA-NNN)
- `transforms`    — pure functions: validate, normalize, hash, diff, apply_diff
- `ddl/`          — Postgres DDL emission via SQLGlot (M1.1 second half)
"""

from __future__ import annotations

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
from app.engines.schema.ir import (
    Assumption,
    ColumnIR,
    IndexIR,
    JoinKey,
    ReconciliationPolicy,
    RelationshipIR,
    SchemaIR,
    SourceContribution,
    SourceRef,
    TableIR,
)

__all__ = [
    "Assumption",
    "Cardinality",
    "ColumnIR",
    "IndexIR",
    "JoinKey",
    "JoinTransform",
    "MergeStrategy",
    "OnDelete",
    "PhysicalType",
    "PrimaryKeyStrategy",
    "ReconciliationPolicy",
    "RelationshipIR",
    "SchemaIR",
    "SemanticType",
    "SourceContribution",
    "SourceRef",
    "SourceRole",
    "TableIR",
]
