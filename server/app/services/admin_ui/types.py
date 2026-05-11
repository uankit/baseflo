"""Typed AdminUISpec — what the React client renders.

Per docs/40-features/ADMIN-GEN.md §3.2. Strongly typed Pydantic v2 models,
`extra='forbid'` everywhere — no `dict[str, Any]` on the contract.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


__all__ = [
    "AdminTab",
    "AdminUISpec",
    "BulkActionSpec",
    "DetailSection",
    "DetailViewSpec",
    "EditModeSpec",
    "FilterOpKind",
    "FilterSpec",
    "IconKind",
    "ListColumnSpec",
    "ListViewSpec",
    "RelationshipNavSpec",
    "SortDirection",
    "SortSpec",
    "WidgetKind",
]


class WidgetKind(StrEnum):
    """How the client renders a column. Set deterministically from
    SemanticType + PhysicalType in `generator._widget_for_column`."""

    TEXT = "text"
    LONG_TEXT = "long_text"
    NUMBER = "number"
    MONEY = "money"
    DATE = "date"
    DATETIME = "datetime"
    STATUS_CHIP = "status_chip"
    PII_MASKED = "pii_masked"
    LINK = "link"
    BOOLEAN = "boolean"
    FILE_UPLOAD = "file_upload"
    SELECT = "select"


class IconKind(StrEnum):
    """Allowlist of icons the React client knows how to render."""

    USERS = "users"
    PACKAGE = "package"
    SHOPPING_CART = "shopping_cart"
    CREDIT_CARD = "credit_card"
    CALENDAR = "calendar"
    MESSAGE = "message"
    BAR_CHART = "bar_chart"
    DATABASE = "database"
    TAG = "tag"
    GENERIC = "generic"


class SortDirection(StrEnum):
    ASC = "asc"
    DESC = "desc"


class FilterOpKind(StrEnum):
    EQ = "eq"
    NE = "ne"
    IN = "in"
    GTE = "gte"
    LTE = "lte"
    BETWEEN = "between"
    CONTAINS = "contains"


class SortSpec(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    column: str
    direction: SortDirection = SortDirection.DESC


class FilterSpec(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    column: str
    label: str
    available_ops: list[FilterOpKind]


class ListColumnSpec(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    name: str
    label: str
    widget: WidgetKind
    sortable: bool = True
    filterable: bool = True
    visible_by_default: bool = True
    currency: str | None = None
    """ISO-4217 set when widget == MONEY."""
    enum_values: list[str] | None = None
    """Set when widget == STATUS_CHIP or SELECT."""


class ListViewSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    columns: list[ListColumnSpec] = Field(min_length=1)
    default_sort: SortSpec
    filters: list[FilterSpec] = Field(default_factory=list)
    search_columns: list[str] = Field(default_factory=list)
    page_size: int = Field(default=50, ge=10, le=500)
    show_source_badge: bool = False
    """When True, list rows show which source(s) contributed each row.
    Only meaningful for reconciled tables."""


class DetailSection(BaseModel):
    """Fields grouped on the detail view; e.g., 'Identity', 'Financial', 'Activity'."""

    model_config = ConfigDict(extra="forbid")
    title: str
    columns: list[str]


class RelationshipNavSpec(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    label: str
    target_table: str
    via_column: str


class EditModeSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    editable_columns: list[str] = Field(default_factory=list)
    write_back_canonical: bool = True
    """When True, edits route to the EntityReconciler-decided authoritative source."""


class DetailViewSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sections: list[DetailSection]
    relationships: list[RelationshipNavSpec] = Field(default_factory=list)
    activity_timeline: bool = True
    edit_mode: EditModeSpec


class BulkActionSpec(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    id: str
    label: str
    requires_two_person_approval: bool = False


class AdminTab(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(pattern=r"^[a-z][a-z0-9_-]*$")
    label: str
    icon: IconKind = IconKind.GENERIC
    table_name: str
    list_view: ListViewSpec
    detail_view: DetailViewSpec
    bulk_actions: list[BulkActionSpec] = Field(default_factory=list)
    badge_count_query: str | None = None
    """KPI name whose value renders as a small badge on the tab."""


class AdminUISpec(BaseModel):
    """Top-level admin UI definition the React client renders."""

    model_config = ConfigDict(extra="forbid")
    project_id: UUID
    project_version_id: UUID
    schema_version: int = 1
    tabs: list[AdminTab] = Field(default_factory=list)
    refinement_enabled: bool = True
    export_enabled: bool = True
    custom_branding: dict[str, Any] | None = None
    """Custom branding configuration."""
