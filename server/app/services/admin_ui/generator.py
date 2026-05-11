"""Deterministic AdminUISpec generator.

`build_admin_ui_spec(schema_ir, kpis, project_id, project_version_id)` walks
the unified `SchemaIR` and emits a typed `AdminUISpec`. Every per-column
widget choice and per-table tab definition is derived mechanically from
typed inputs — no LLM calls, no string heuristics.

Per docs/40-features/ADMIN-GEN.md §3.3 ("Generation Rules").
"""

from __future__ import annotations

from typing import Iterable
from uuid import UUID

from app.agents.specialists.kpi_planner.types import KPIDefinition
from app.engines.schema.enums import (
    PII_SEMANTIC_TYPES,
    PhysicalType,
    SemanticType,
)
from app.engines.schema.ir import ColumnIR, RelationshipIR, SchemaIR, TableIR
from app.services.admin_ui.types import (
    AdminTab,
    AdminUISpec,
    BulkActionSpec,
    DetailSection,
    DetailViewSpec,
    EditModeSpec,
    FilterOpKind,
    FilterSpec,
    IconKind,
    ListColumnSpec,
    ListViewSpec,
    RelationshipNavSpec,
    SortDirection,
    SortSpec,
    WidgetKind,
)


# ---------- Widget mapping ----------


_WIDGET_BY_SEMANTIC_TYPE: dict[SemanticType, WidgetKind] = {
    SemanticType.IDENTITY: WidgetKind.TEXT,
    SemanticType.FOREIGN_KEY: WidgetKind.LINK,
    SemanticType.MONEY: WidgetKind.MONEY,
    SemanticType.STATUS: WidgetKind.STATUS_CHIP,
    SemanticType.TEMPORAL: WidgetKind.DATETIME,
    SemanticType.PII_EMAIL: WidgetKind.PII_MASKED,
    SemanticType.PII_PHONE: WidgetKind.PII_MASKED,
    SemanticType.PII_ADDRESS: WidgetKind.PII_MASKED,
    SemanticType.PII_NAME: WidgetKind.PII_MASKED,
    SemanticType.PII_ID_NUMBER: WidgetKind.PII_MASKED,
    SemanticType.CATEGORY: WidgetKind.SELECT,
    SemanticType.FREE_TEXT: WidgetKind.LONG_TEXT,
    SemanticType.BOOLEAN: WidgetKind.BOOLEAN,
    SemanticType.COUNT: WidgetKind.NUMBER,
    SemanticType.DERIVED: WidgetKind.TEXT,
}


def _refine_widget_with_physical_type(
    widget: WidgetKind, physical_type: PhysicalType
) -> WidgetKind:
    """Light refinement: TEMPORAL columns with `date` physical type render as
    DATE (no time-of-day). CATEGORY at very low cardinality is SELECT;
    everything else CATEGORY-shaped becomes plain TEXT."""
    if widget == WidgetKind.DATETIME and physical_type == PhysicalType.DATE:
        return WidgetKind.DATE
    return widget


def _widget_for_column(col: ColumnIR) -> WidgetKind:
    raw = _WIDGET_BY_SEMANTIC_TYPE.get(col.semantic_type, WidgetKind.TEXT)
    return _refine_widget_with_physical_type(raw, col.physical_type)


# ---------- Filters: which ops are available per widget ----------


_FILTER_OPS_BY_WIDGET: dict[WidgetKind, list[FilterOpKind]] = {
    WidgetKind.TEXT: [FilterOpKind.EQ, FilterOpKind.NE, FilterOpKind.CONTAINS],
    WidgetKind.LONG_TEXT: [FilterOpKind.CONTAINS],
    WidgetKind.NUMBER: [FilterOpKind.EQ, FilterOpKind.GTE, FilterOpKind.LTE, FilterOpKind.BETWEEN],
    WidgetKind.MONEY: [FilterOpKind.GTE, FilterOpKind.LTE, FilterOpKind.BETWEEN],
    WidgetKind.DATE: [FilterOpKind.GTE, FilterOpKind.LTE, FilterOpKind.BETWEEN],
    WidgetKind.DATETIME: [FilterOpKind.GTE, FilterOpKind.LTE, FilterOpKind.BETWEEN],
    WidgetKind.STATUS_CHIP: [FilterOpKind.EQ, FilterOpKind.IN],
    WidgetKind.PII_MASKED: [FilterOpKind.EQ],
    WidgetKind.LINK: [FilterOpKind.EQ],
    WidgetKind.BOOLEAN: [FilterOpKind.EQ],
    WidgetKind.SELECT: [FilterOpKind.EQ, FilterOpKind.IN],
    WidgetKind.FILE_UPLOAD: [],
}


# ---------- Tab metadata ----------


# Curated icons mapped from canonical entity name keywords. This is
# deterministic LOOKUP, not semantic classification — it just picks a nicer
# default icon when the table name happens to match a known noun. Always
# falls back to GENERIC.
_ICON_BY_KEYWORD: dict[str, IconKind] = {
    "customer": IconKind.USERS,
    "user": IconKind.USERS,
    "member": IconKind.USERS,
    "patient": IconKind.USERS,
    "product": IconKind.PACKAGE,
    "item": IconKind.PACKAGE,
    "listing": IconKind.PACKAGE,
    "order": IconKind.SHOPPING_CART,
    "purchase": IconKind.SHOPPING_CART,
    "payment": IconKind.CREDIT_CARD,
    "charge": IconKind.CREDIT_CARD,
    "invoice": IconKind.CREDIT_CARD,
    "booking": IconKind.CALENDAR,
    "appointment": IconKind.CALENDAR,
    "session": IconKind.CALENDAR,
    "event": IconKind.CALENDAR,
    "message": IconKind.MESSAGE,
    "review": IconKind.MESSAGE,
    "comment": IconKind.MESSAGE,
}


def _icon_for_table(table: TableIR) -> IconKind:
    """Best-effort default; the user can override per-tab in admin settings."""
    name_lower = table.name.lower()
    for keyword, icon in _ICON_BY_KEYWORD.items():
        if keyword in name_lower:
            return icon
    return IconKind.GENERIC


# ---------- Section grouping ----------


_IDENTITY_SECTION = "Identity"
_FINANCIAL_SECTION = "Financial"
_STATUS_SECTION = "Status"
_CONTACT_SECTION = "Contact"
_ACTIVITY_SECTION = "Activity"
_OTHER_SECTION = "Other"


def _section_for_column(col: ColumnIR) -> str:
    if col.semantic_type == SemanticType.IDENTITY:
        return _IDENTITY_SECTION
    if col.semantic_type == SemanticType.FOREIGN_KEY:
        return _IDENTITY_SECTION
    if col.semantic_type == SemanticType.MONEY:
        return _FINANCIAL_SECTION
    if col.semantic_type == SemanticType.STATUS:
        return _STATUS_SECTION
    if col.semantic_type in PII_SEMANTIC_TYPES:
        return _CONTACT_SECTION
    if col.semantic_type == SemanticType.TEMPORAL:
        return _ACTIVITY_SECTION
    return _OTHER_SECTION


_SECTION_ORDER: tuple[str, ...] = (
    _IDENTITY_SECTION, _CONTACT_SECTION, _STATUS_SECTION,
    _FINANCIAL_SECTION, _OTHER_SECTION, _ACTIVITY_SECTION,
)


# ---------- Per-table builders ----------


def _build_list_column_spec(col: ColumnIR) -> ListColumnSpec:
    widget = _widget_for_column(col)
    visible = _is_visible_by_default(col, widget)
    sortable = widget not in {WidgetKind.LONG_TEXT, WidgetKind.PII_MASKED, WidgetKind.FILE_UPLOAD}
    filterable = widget != WidgetKind.FILE_UPLOAD
    return ListColumnSpec(
        name=col.name,
        label=col.label,
        widget=widget,
        sortable=sortable,
        filterable=filterable,
        visible_by_default=visible,
        currency=col.currency if widget == WidgetKind.MONEY else None,
        enum_values=col.enum_values if widget in {WidgetKind.STATUS_CHIP, WidgetKind.SELECT} else None,
    )


def _is_visible_by_default(col: ColumnIR, widget: WidgetKind) -> bool:
    """Hide noisy / heavy columns by default; user toggles in the UI."""
    if col.name in {"created_at", "updated_at", "deleted_at"}:
        return False
    if widget == WidgetKind.LONG_TEXT:
        return False
    return True


def _default_sort_for_table(table: TableIR) -> SortSpec:
    """Prefer `created_at` DESC when present; fall back to PK ASC."""
    column_names = {c.name for c in table.columns}
    if "created_at" in column_names:
        return SortSpec(column="created_at", direction=SortDirection.DESC)
    return SortSpec(column=table.primary_key[0], direction=SortDirection.ASC)


def _search_columns(table: TableIR) -> list[str]:
    """Server-side full-text search targets: STATUS, IDENTITY, and PII columns."""
    out: list[str] = []
    for col in table.columns:
        if col.semantic_type in PII_SEMANTIC_TYPES:
            out.append(col.name)
        elif col.semantic_type == SemanticType.IDENTITY and col.physical_type in {
            PhysicalType.TEXT, PhysicalType.VARCHAR
        }:
            out.append(col.name)
        elif col.semantic_type == SemanticType.STATUS:
            out.append(col.name)
    return out


def _build_filters(columns: Iterable[ColumnIR]) -> list[FilterSpec]:
    out: list[FilterSpec] = []
    for col in columns:
        widget = _widget_for_column(col)
        ops = _FILTER_OPS_BY_WIDGET.get(widget, [])
        if not ops:
            continue
        out.append(
            FilterSpec(column=col.name, label=col.label, available_ops=list(ops))
        )
    return out


def _build_detail_sections(columns: Iterable[ColumnIR]) -> list[DetailSection]:
    by_section: dict[str, list[str]] = {s: [] for s in _SECTION_ORDER}
    for col in columns:
        by_section[_section_for_column(col)].append(col.name)
    return [
        DetailSection(title=section, columns=cols)
        for section in _SECTION_ORDER
        if (cols := by_section.get(section))
    ]


def _build_relationships_for_table(
    table: TableIR, relationships: list[RelationshipIR]
) -> list[RelationshipNavSpec]:
    """Surface relationships where THIS table is involved.

    For each relationship the list view's row gets a navigable link to the
    related entity. Both directions of a relationship surface — incoming
    references (where this table is the to-side) become reverse-nav links.
    """
    out: list[RelationshipNavSpec] = []
    for rel in relationships:
        if rel.from_table == table.name:
            out.append(
                RelationshipNavSpec(
                    label=rel.to_table.replace("_", " ").title(),
                    target_table=rel.to_table,
                    via_column=rel.from_columns[0],
                )
            )
        elif rel.to_table == table.name:
            out.append(
                RelationshipNavSpec(
                    label=rel.from_table.replace("_", " ").title(),
                    target_table=rel.from_table,
                    via_column=rel.to_columns[0],
                )
            )
    return out


def _editable_columns(columns: Iterable[ColumnIR]) -> list[str]:
    """Identity columns and audit timestamps are read-only; everything else
    is editable by default. Refinement may further restrict."""
    out: list[str] = []
    for col in columns:
        if col.semantic_type == SemanticType.IDENTITY:
            continue
        if col.semantic_type == SemanticType.DERIVED:
            continue
        if col.name in {"created_at", "updated_at", "deleted_at"}:
            continue
        out.append(col.name)
    return out


def _kpi_for_tab_badge(table: TableIR, kpis: list[KPIDefinition]) -> str | None:
    """Pick a counter KPI scoped to this table for the tab's badge.

    Strict match: KPI's grain.table == table.name AND kind == COUNTER.
    """
    for kpi in kpis:
        if kpi.grain.table == table.name and kpi.kind.value == "counter":
            return kpi.name
    return None


def _is_join_table(table: TableIR) -> bool:
    """Heuristic-free: a join table is one whose primary_key has more than
    one column AND every primary-key column is a foreign-key-typed column.
    The agent layer's CardinalityResolver explicitly creates these for M2M.
    """
    if len(table.primary_key) <= 1:
        return False
    fk_column_names = {
        c.name for c in table.columns if c.semantic_type == SemanticType.FOREIGN_KEY
    }
    return all(pk in fk_column_names for pk in table.primary_key)


def _build_tab(table: TableIR, ir: SchemaIR, kpis: list[KPIDefinition]) -> AdminTab:
    list_columns = [_build_list_column_spec(c) for c in table.columns]

    list_view = ListViewSpec(
        columns=list_columns,
        default_sort=_default_sort_for_table(table),
        filters=_build_filters(table.columns),
        search_columns=_search_columns(table),
        page_size=50,
        show_source_badge=table.is_reconciled,
    )

    detail_view = DetailViewSpec(
        sections=_build_detail_sections(table.columns),
        relationships=_build_relationships_for_table(table, ir.relationships),
        activity_timeline=any(
            c.semantic_type == SemanticType.TEMPORAL for c in table.columns
        ),
        edit_mode=EditModeSpec(
            editable_columns=_editable_columns(table.columns),
            write_back_canonical=table.is_reconciled,
        ),
    )

    bulk_actions = [
        BulkActionSpec(id="export_selected", label="Export selected"),
        BulkActionSpec(
            id="delete_selected", label="Delete selected",
            requires_two_person_approval=True,
        ),
    ]

    return AdminTab(
        id=table.name.replace("_", "-"),
        label=table.label,
        icon=_icon_for_table(table),
        table_name=table.name,
        list_view=list_view,
        detail_view=detail_view,
        bulk_actions=bulk_actions,
        badge_count_query=_kpi_for_tab_badge(table, kpis),
    )


# ---------- Top-level entrypoint ----------


def build_admin_ui_spec(
    *,
    schema_ir: SchemaIR,
    kpis: list[KPIDefinition] | None = None,
    project_id: UUID,
    project_version_id: UUID,
) -> AdminUISpec:
    """Compose an AdminUISpec from a unified schema IR + KPI definitions.

    Per docs/40-features/ADMIN-GEN.md §3.3 — deterministic walk over the IR.
    Join tables (M2M bridge tables) are HIDDEN by default; the user can
    surface them later via project settings.
    """
    kpis = kpis or []
    visible_tables = [t for t in schema_ir.tables if not _is_join_table(t)]
    tabs = [_build_tab(table, schema_ir, kpis) for table in visible_tables]
    return AdminUISpec(
        project_id=project_id,
        project_version_id=project_version_id,
        schema_version=schema_ir.schema_version,
        tabs=tabs,
        refinement_enabled=True,
        export_enabled=True,
    )
