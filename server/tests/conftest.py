"""Test process configuration.

Production still requires explicit environment. Tests get deterministic local
settings before application modules import Settings.
"""

from __future__ import annotations

import os

os.environ.setdefault(
    "BASEFLO_DATABASE_URL",
    "postgresql+asyncpg://baseflo:baseflo@localhost/baseflo_test",
)
os.environ.setdefault("BASEFLO_SECRET_KEY", "test-secret-for-server-tests")
