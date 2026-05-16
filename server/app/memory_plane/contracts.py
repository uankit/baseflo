"""Contracts for Baseflo business memory.

This is domain memory, not chat history. It stores stable business meaning that
should shape future scans: glossary entries, semantic roles, relationships,
preferences, dismissed rules, and validated patterns.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class MemoryModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


MemoryScope = Literal["org", "source", "asset", "field", "relationship", "pattern", "user"]
MemoryKind = Literal[
    "business_summary",
    "business_entity",
    "business_kpi",
    "asset_role",
    "field_role",
    "relationship",
    "preference",
    "dismissal",
    "validated_pattern",
    "glossary",
]
MemoryStatus = Literal["active", "dismissed", "expired"]
MemorySource = Literal["memory_plane:auto", "user", "system"]


class MemoryCandidate(MemoryModel):
    key: str = Field(min_length=1, max_length=255)
    kind: MemoryKind
    scope: MemoryScope
    subject_ref: dict[str, Any] = Field(default_factory=dict)
    statement: str = Field(min_length=1)
    evidence_refs: list[dict[str, Any]] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    source: MemorySource = "memory_plane:auto"
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("key")
    @classmethod
    def _key_is_stable(cls, value: str) -> str:
        if value.strip() != value or " " in value:
            raise ValueError("memory key must be stable and space-free")
        return value


class BusinessMemoryRecord(MemoryModel):
    id: str | None = None
    key: str
    kind: MemoryKind | str
    scope: MemoryScope | str
    subject_ref: dict[str, Any] = Field(default_factory=dict)
    statement: str
    evidence_refs: list[dict[str, Any]] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    source: str
    status: MemoryStatus | str
    metadata: dict[str, Any] = Field(default_factory=dict)
    last_confirmed_at: datetime | None = None


class MemoryWriteResult(MemoryModel):
    key: str
    action: Literal["created", "updated", "unchanged", "skipped"]
    reason: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)


class MemoryPlaneRunResult(MemoryModel):
    candidates: list[MemoryCandidate]
    writes: list[MemoryWriteResult]
