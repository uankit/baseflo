"""DDL compiler — Schema IR → Postgres DDL via SQLGlot.

Per docs/40-features/IR-DDL.md. Deterministic; consumes the unified `SchemaIR`
from `PhysicalSchemaArchitect` and emits CREATE TABLE / FK / INDEX / CHECK
DDL plus an `EmissionResult` with structural counts and warnings.

The dialect adapter Protocol is defined here so MySQL/Snowflake adapters can
land later (M5+) without engine-code changes.
"""

from __future__ import annotations

from app.engines.schema.ddl.compiler import (  # noqa: F401
    EmissionResult,
    EmissionWarning,
    compile_ir,
)
from app.engines.schema.ddl.identifiers import (  # noqa: F401
    is_safe_identifier,
    quote_identifier,
)

__all__ = [
    "EmissionResult",
    "EmissionWarning",
    "compile_ir",
    "is_safe_identifier",
    "quote_identifier",
]
