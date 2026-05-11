"""Project data exports — the "no lock-in" brand promise.

Per docs/40-features/CONN-FRAMEWORK.md + docs/30-features.md SEC-EXPORT.
At any moment a user can request `/api/v1/projects/{id}/exports` and
receive a tarball with every reconciled table as CSV plus the IR JSON +
an `.env.example`. They can `pg_restore`/`psql -f` and have a working
copy without us — that's the "we're not lock-in" credibility play.
"""

from __future__ import annotations

from app.services.exports.composer import (
    ExportArchive,
    ExportComposer,
    compose_export_archive,
)

__all__ = [
    "ExportArchive",
    "ExportComposer",
    "compose_export_archive",
]
