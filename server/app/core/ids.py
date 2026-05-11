"""UUIDv7 identifier generation.

Per docs/04-database-schema.md §2, all primary keys are UUIDv7 (time-sortable;
index-friendly). We use `uuid_utils` for fast, RFC-9562-compliant generation.

Test-time deterministic generation is supported via `set_id_factory` so unit tests
can assert against fixed ids without monkey-patching modules.
"""

from __future__ import annotations

from collections.abc import Callable
from uuid import UUID

import uuid_utils


def new_uuid7() -> UUID:
    """Generate a new UUIDv7.

    UUIDv7 encodes a millisecond Unix timestamp in the high bits, making rows
    naturally sortable by creation time and avoiding the index-fragmentation
    that plagues random UUIDv4 primary keys.
    """
    return _id_factory()


def _real_factory() -> UUID:
    return UUID(str(uuid_utils.uuid7()))


_id_factory: Callable[[], UUID] = _real_factory


def set_id_factory(factory: Callable[[], UUID]) -> None:
    """Override the id factory (test-only).

    Tests should restore the original factory in a fixture teardown.
    """
    global _id_factory
    _id_factory = factory


def reset_id_factory() -> None:
    """Restore the production UUIDv7 factory."""
    global _id_factory
    _id_factory = _real_factory
