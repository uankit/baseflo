# `CONN-EXCEL` — Excel `.xlsx` Upload Connector

Status: M2. Sibling of [`CONN-CSV`](CONN-CSV.md). The two share the file-upload UX (drop your spreadsheet, no API setup) but diverge in parsing: Excel files are binary, multi-sheet, and carry typed cells.

---

## 1. Overview

User uploads an `.xlsx` file. Each sheet becomes a `SourceTable`; row 0 of each sheet is treated as the header by default, overridable per-sheet via the upload UI. Type inference reads up to 1000 cells per column, falling back to the same primitive-detection helpers CSV uses (`_try_int / _try_float / _try_iso_date / …`) when openpyxl reports `cell.data_type == 's'` (string).

Legacy `.xls` is **not** supported — the user is asked to re-export as `.xlsx`. `.xlsm` (macro-enabled) loads but macros are ignored.

## 2. Module Layout

```
server/app/connectors/excel/
├── __init__.py            # registration with ConnectorRegistry
├── connector.py           # ExcelConnector implementing Connector Protocol
└── parser.py              # openpyxl-driven workbook → list[SourceTable]
```

The `infer_source_type` and primitive-parser helpers live in CSV's `parser.py` and are re-imported here — no duplication.

## 3. Capabilities

```python
metadata = ConnectorMetadata(
    name="excel",
    display_name="Excel Upload",
    version="1.0.0",
    auth_kind=AuthKind.FILE_UPLOAD,
    capabilities=ConnectorCapabilities(
        can_introspect=True,
        can_read=True,
        can_write=False,
        can_subscribe_webhooks=False,
        supports_pagination=True,
        supports_streaming=True,        # row-by-row read
        requires_periodic_sync=False,   # refresh = re-upload
        write_back_canonical_only=False,
    ),
)
```

## 4. Auth

`AuthCredentials.payload` carries `path` (a `SecretStr` pointing to the local upload, mirroring CSV's path-token). Optional `has_header` is a global override applied to every sheet — per-sheet header overrides land in M3 alongside the upload UI.

```python
AuthCredentials(payload={
    "path": SecretStr("/uploads/customers_orders.xlsx"),
    "has_header": SecretStr("true"),     # optional; defaults to true
})
```

`authenticate(...)` opens the workbook to validate the file, records sheet names + dimensions on the token's `metadata`, then closes the workbook. Subsequent reads re-open from `path`.

## 5. Introspection

`introspect_schema` returns one `SourceTable` per non-empty sheet. Sheet names are sanitized (`_sanitize_sheet_name`): lower-case, spaces → `_`, non-alphanumeric/underscore stripped. The first row's cells become column names; an empty / numeric-looking row 0 with `has_header=true` raises `BF-CONN-EXCEL-002` so the user can override.

`source_type` per column is determined by:
1. **openpyxl-typed cells** (`'n'` numeric → `integer` or `number`; `'d'` date → `datetime`; `'b'` bool → `boolean`).
2. **Fallback primitive inference** for `'s'` (string) cells, identical to CSV's `infer_source_type`.

Sample values: up to 30 non-null cells, taken from rows 1..N (0-indexed) skipping the header.

## 6. Read

Streaming: `ws.iter_rows(values_only=True)` per sheet, yielded as `Row(values=dict)`. Pagination via `query.limit`; `query.cursor` ignored for M2 since openpyxl doesn't expose row offsets cheaply (M3 lights up keyset reads when needed).

## 7. Write / Webhooks / Health

- `write` raises `BF-CONN-002` (uploads are read-only; refresh = re-upload).
- `webhook_subscribe` raises `BF-CONN-002` (file connector — no webhooks).
- `health_check` checks the file still exists and is readable.

## 8. Test Plan

- Workbook with 2 sheets → 2 `SourceTable`s, names sanitized.
- Sheet with typed cells (date, decimal, bool) → correct `source_type` per column.
- Sheet with all-string cells → falls back to CSV's primitive inference.
- Empty workbook → empty `SourceSchema`.
- `has_header=false` → columns synthesized as `column_1..N`.
- `read` streams rows with `query.limit` honoured.
- Coverage: 90%.

## 9. Error Codes

| Code | Condition |
|---|---|
| `BF-CONN-EXCEL-001` | Path missing or file unreadable |
| `BF-CONN-EXCEL-002` | Header row indeterminate and `has_header` not specified |
| `BF-CONN-EXCEL-003` | Sheet count exceeds limit (50 sheets) |
| `BF-CONN-EXCEL-004` | Unknown sheet requested via `sample_rows` / `read` |

## 10. Dependencies

[`CONN-FRAMEWORK`](CONN-FRAMEWORK.md), [`CONN-CSV`](CONN-CSV.md) (primitive parsers), `openpyxl` (>=3.1).

## 11. Milestone

- **M2**: full implementation; multi-sheet introspection.
- **M3**: per-sheet header override UI; column-rename UX before introspection commits; large-file streaming via `read_only=True` mode.
