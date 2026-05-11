"""Pure functions over SchemaIR — validate, normalize, hash.

`diff` and `apply_diff` are not available in v1.
"""

from __future__ import annotations

import hashlib
import json

from app.core.errors import BasefloError
from app.engines.schema.compatibility import ValidationReport, validate as _validate
from app.engines.schema.ir import SchemaIR


def validate(ir: SchemaIR) -> ValidationReport:
    """Re-export for ergonomic `from app.engines.schema.transforms import validate`."""
    return _validate(ir)


def assert_valid(ir: SchemaIR) -> None:
    """Run validators; raise BF-SCHEMA-001 on any finding."""
    report = _validate(ir)
    if not report.passed:
        raise BasefloError(
            error_code="BF-SCHEMA-001",
            message=f"Schema IR failed validation: {report.summary()}",
            status_code=500,
            details={
                "findings": [
                    {"code": f.error_code, "target": f.target, "message": f.message}
                    for f in report.findings
                ]
            },
        )


def normalize(ir: SchemaIR) -> SchemaIR:
    """Return an IR with deterministic ordering of tables, columns, relationships,
    indexes, and assumptions for stable hashing.

    The IR is `frozen=True`, so we rebuild via `model_copy(update=...)`.
    """
    sorted_tables = sorted(
        (
            t.model_copy(
                update={
                    "columns": sorted(t.columns, key=lambda c: c.name),
                    "primary_key": sorted(t.primary_key),
                    "sources": sorted(
                        t.sources, key=lambda s: (s.connector_name, s.source_table, s.source_column or "")
                    ),
                }
            )
            for t in ir.tables
        ),
        key=lambda t: t.name,
    )
    sorted_relationships = sorted(ir.relationships, key=lambda r: r.name)
    sorted_indexes = sorted(ir.indexes, key=lambda i: i.name)
    sorted_assumptions = sorted(ir.assumptions, key=lambda a: (a.target, a.text))
    return ir.model_copy(
        update={
            "tables": sorted_tables,
            "relationships": sorted_relationships,
            "indexes": sorted_indexes,
            "assumptions": sorted_assumptions,
        }
    )


def hash_ir(ir: SchemaIR) -> str:
    """Stable SHA-256 over the normalized JSON representation.

    Used for cache keys, change detection, and idempotency.
    """
    payload = normalize(ir).model_dump(mode="json")
    canonical = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
