"""Admin UI spec generator.

Per docs/40-features/ADMIN-GEN.md. Schema-driven: the React client renders
whatever the generator describes — we never hand-code per-project admin UI.

Sub-modules:
- `types`     — typed AdminUISpec / AdminTab / ListViewSpec / DetailViewSpec / WidgetKind
- `generator` — `build_admin_ui_spec(schema_ir, kpis) -> AdminUISpec`
"""

from __future__ import annotations

from app.services.admin_ui.generator import build_admin_ui_spec  # noqa: F401
from app.services.admin_ui.types import (  # noqa: F401
    AdminTab,
    AdminUISpec,
    BulkActionSpec,
    DetailSection,
    DetailViewSpec,
    FilterOpKind,
    FilterSpec,
    IconKind,
    ListColumnSpec,
    ListViewSpec,
    SortDirection,
    SortSpec,
    WidgetKind,
)
