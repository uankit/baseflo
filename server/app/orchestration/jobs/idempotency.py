"""Idempotency-key resolution.

Per docs/40-features/JOBS-AND-SSE.md §3.2:
  - Same key + same payload → return existing job.
  - Same key + different payload → raise BF-JOB-001 (Conflict).

The implementation is content-addressed: we hash the typed payload and store
that fingerprint on the persisted `generation_jobs` row alongside the
idempotency key. On collision we compare fingerprints to decide between
return-existing and raise-conflict.
"""

from __future__ import annotations

import hashlib

from app.orchestration.jobs.types import JobPayload


def fingerprint(payload: JobPayload) -> str:
    """Deterministic hash of a typed payload for collision detection.

    Pydantic's `.model_dump_json(by_alias=True)` is canonical enough for our
    purposes; we tighten it with stable key order via `sort_keys=True` would
    be ideal, but Pydantic v2 does not expose sort. Instead we go through
    `json.dumps(model_dump(), sort_keys=True)` which is deterministic.
    """
    import json

    canonical = json.dumps(
        payload.model_dump(mode="json", by_alias=True, exclude_none=False),
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
