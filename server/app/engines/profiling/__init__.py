"""Deterministic source profiling.

This package turns connector schemas + bounded samples into typed evidence
bundles for agents. Agents reason over these facts instead of raw datasets.
"""

from app.engines.profiling.source_evidence import (
    ColumnEvidence,
    CurrencyEvidence,
    SourceEvidenceBundle,
    TableEvidence,
    profile_source,
)

__all__ = [
    "ColumnEvidence",
    "CurrencyEvidence",
    "SourceEvidenceBundle",
    "TableEvidence",
    "profile_source",
]
