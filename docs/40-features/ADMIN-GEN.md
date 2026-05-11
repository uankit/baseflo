# `ADMIN-GEN` — Admin UI Generator

Status: M1. Combines `ADMIN-GEN` + `ADMIN-LIST` + `ADMIN-DETAIL` + `ADMIN-MASK` from [`30-features.md`](../30-features.md). The hosted admin UI rendered entirely from the unified `SchemaIR`. No per-project hand coding.

---

## 1. Overview

`ADMIN-GEN` produces, at runtime, the entire admin UI for a project: which tabs exist, what each list view looks like, which fields are editable, which are masked, what relationships render as linked navigation, what bulk actions are allowed. The admin UI is generated from the schema IR + agent labels + reconciliation policy — there is no per-project hand-coded React component. Every customer's admin is a render of their unified IR.

The output is an `AdminUISpec` consumed by the React client. The client knows nothing about specific verticals; it renders whatever the spec describes. This is what makes "n different businesses, n different admin panels, no manual UI work" real.

## 2. High-Level Design

```
SchemaIR + ReconciliationPlan + KPIs (parent_version)
                    │
                    ▼
        ┌──────────────────────────┐
        │  AdminUISpecBuilder      │  (deterministic; no LLM)
        └────────────┬─────────────┘
                     │
                     ▼
              AdminUISpec (typed)
                     │
                     ▼
              GET /api/v1/projects/:id/admin-ui-spec
                     │
                     ▼
              React client renders:
              - sidebar tabs
              - list views (TanStack Table)
              - detail/edit forms (per ColumnIR type)
              - relationship navigation
              - PII mask + reveal
              - bulk action menus
              - export buttons
              - refinement panel
```

## 3. Low-Level Design

### 3.1 Module Layout

```
server/app/services/admin_ui/
├── __init__.py
├── builder.py              # AdminUISpecBuilder.build(ir, plan, kpis) -> AdminUISpec
├── tabs.py                 # tab generation: one per top-level table or reconciled entity
├── list_view.py            # column rendering rules (sort, filter, search, mask)
├── detail_view.py          # form generation per ColumnIR
├── form_widgets.py         # widget mapping: SemanticType → input widget
├── relationships.py        # linked-entity navigation
├── bulk_actions.py         # which actions appear (export-rows, delete-selected with two-person approval, etc.)
└── tests/
    ├── test_spec_round_trip.py    # IR fixture → expected AdminUISpec
    └── fixtures/

client/apps/web/src/features/admin/
├── components/
│   ├── ListView.tsx        # generic; consumes AdminUISpec.tabs[i].listView
│   ├── DetailView.tsx
│   ├── EditForm.tsx
│   ├── PIIMaskedField.tsx
│   ├── MoneyField.tsx
│   ├── StatusChip.tsx
│   └── RelationshipNav.tsx
├── hooks/
│   ├── useAdminUISpec.ts
│   └── useEntityCRUD.ts
└── pages/
    └── WorkspacePage.tsx   # routes to tabs from spec
```

### 3.2 Key Types

```python
class AdminUISpec(BaseModel):
    project_id: UUID
    version_id: UUID
    tabs: list[AdminTab]
    refinement_enabled: bool
    export_enabled: bool
    custom_branding: BrandingConfig | None = None    # Pro+: logo, colors, custom domain

class AdminTab(BaseModel):
    id: str                                          # url-safe slug
    label: str                                       # plural ("Customers")
    icon: IconKind                                   # subset of allowed icons
    table_name: str                                  # entity table in IR
    list_view: ListViewSpec
    detail_view: DetailViewSpec
    bulk_actions: list[BulkActionSpec]
    badge_count_query: str | None = None             # optional KPI to display as badge

class ListViewSpec(BaseModel):
    columns: list[ListColumnSpec]                    # which columns to show by default
    default_sort: SortSpec
    filters: list[FilterSpec]                        # per-column filter widgets
    search_columns: list[str]                        # full-text search targets
    page_size: int = 50
    show_source_badge: bool                          # multi-source: which source contributed each row

class ListColumnSpec(BaseModel):
    name: str                                        # IR column name
    label: str
    widget: WidgetKind                               # TEXT | NUMBER | MONEY | DATE | STATUS_CHIP | PII_MASKED | LINK | BOOLEAN
    sortable: bool = True
    filterable: bool = True
    visible_by_default: bool = True

class DetailViewSpec(BaseModel):
    sections: list[DetailSection]                    # grouped fields
    relationships: list[RelationshipNavSpec]         # linked-entities panel
    activity_timeline: bool = True                   # show audit log + sources contributions
    edit_mode: EditModeSpec                          # which fields are editable; write-back rules

class WidgetKind(StrEnum):
    TEXT          = "text"
    LONG_TEXT     = "long_text"
    NUMBER        = "number"
    MONEY         = "money"                          # currency-aware; minor-unit input
    DATE          = "date"
    DATETIME      = "datetime"
    STATUS_CHIP   = "status_chip"                    # colored chip; enum from ColumnIR
    PII_MASKED    = "pii_masked"                     # masked by default; click-to-reveal
    LINK          = "link"
    BOOLEAN       = "boolean"
    FILE_UPLOAD   = "file_upload"
    SELECT        = "select"                         # CATEGORY type with low cardinality
```

### 3.3 Generation Rules

- **Tabs**: one per reconciled entity (or unreconciled top-level table). Hidden tabs for join tables and audit-only tables.
- **List columns**: defaults derived from `ColumnIR`:
  - `IDENTITY` columns visible only as small monospace cell (or hidden if UUID).
  - `MONEY` → `MONEY` widget with currency alignment.
  - `STATUS` → `STATUS_CHIP` with color per enum value (deterministic palette).
  - `PII_*` → `PII_MASKED` widget; reveal action audit-logged.
  - `TEMPORAL` → `DATETIME` with relative-time formatting + tooltip absolute.
  - `FREE_TEXT` → `TEXT` truncated; click-to-expand.
  - `BOOLEAN` → `BOOLEAN` widget.
  - `CATEGORY` low cardinality (≤8 distinct) → `SELECT`; else `TEXT`.
- **Detail sections**: grouped by semantic relatedness — Identity / Contact / Status / Financial / Activity / Relationships. Headers come from the agent's column descriptions where available.
- **Relationships panel**: every relationship endpoint becomes a navigable link to the related entity's detail view.
- **Bulk actions**: Export-Selected always; Delete-Selected only with two-person approval setting (M3+).
- **Multi-source badge**: when a row has contributions from >1 source, a small `S+M+N`-style badge shows; hover reveals per-field source attribution.

### 3.4 Edit Flow (Write-Back to Canonical Source)

When the user edits a field in the admin:
1. Client calls `PATCH /api/v1/projects/:id/entities/:table/:id` with the changed field.
2. Service reads `EntityReconciliationPlan.conflict_policy.authoritative_source` for that field.
3. Service routes the write to the appropriate connector via the data plane.
4. Audit log captures the edit with source target.
5. SSE event broadcasts so other connected clients refresh.

If write-back fails (connector down, token revoked), the edit is queued in `pending_writes` and retried; the user sees a "pending sync" badge on the row.

### 3.5 PII Mask + Reveal

PII columns are masked at render. Reveal action:
1. Client clicks unmask icon.
2. Service checks user's role (default: only Admin/Editor can reveal).
3. Audit log row written: `actor / action=pii.reveal / target=table.column.row_id`.
4. Server returns the unmasked value; client displays.
5. The reveal expires after 30 seconds; row auto-re-masks.

## 4. Design Patterns Applied

| Pattern | Where | Why |
|---|---|---|
| **Strategy** | `WidgetKind` per `SemanticType` | One widget per type; new types add a widget without touching list-view logic. |
| **Specification** | `FilterSpec` per `SemanticType` | Filter widgets composable; declarative. |
| **Schema-Driven UI** | The whole subsystem | The audit caught hand-coded admin tabs; this fixes it permanently. |
| **Command** | Edit + bulk actions | Audit-logged, idempotent, replayable. |

## 5. Test Plan

- Spec round-trip tests: every IR fixture produces an `AdminUISpec` matching golden expected.
- Widget mapping tests: every `SemanticType` maps to the right widget.
- PII reveal tests: role checks, audit log entries, time-expiry.
- Multi-source badge tests: row with 3 contributing sources renders correctly.
- Edit write-back tests: PATCH routes to authoritative source per `EntityReconciliationPlan`.
- Client component tests: each widget renders correctly given typed props.
- Coverage: 90% server-side, 85% client-side.

## 6. Error Codes

| Code | Condition | Recovery |
|---|---|---|
| `BF-ADMIN-001` | Spec generation failed (IR missing required field) | Surface as IR validation failure; don't render admin until IR is valid. |
| `BF-ADMIN-002` | Edit write-back failed; queued | UI surfaces pending sync badge; ops alert if backlog > N. |
| `BF-ADMIN-003` | PII reveal denied (insufficient role) | UI surfaces message + link to admin to request access. |
| `BF-ADMIN-004` | Bulk delete denied (two-person approval required) | UI prompts second approver. |

## 7. Dependencies

- [`IR-CORE`](IR-CORE.md), [`AGENT-ENT`](AGENT-ENT.md), [`AGENT-KPI`](AGENT-KPI.md).
- [`AUDIT-CORE`](AUDIT-CORE.md) — every PII reveal, edit, export, bulk action.
- [`CONN-FRAMEWORK`](CONN-FRAMEWORK.md) — write-back routes through connectors.

## 8. Milestone

- **M1**: full implementation; admin UI lives end-to-end for the friend's case.
- **M2**: multi-source badge + write-back to canonical source.
- **M3**: custom branding for Pro plans; SSO-aware role gating.
- **M4+**: bulk-edit; two-person approval; per-tenant custom widgets.
