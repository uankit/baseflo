# `CONN-CSV` — CSV / Excel Upload Connector

Status: M1. The "drop your spreadsheet" path. Read-only, file-driven, the lowest-friction onboarding for non-technical SMB users.

---

## 1. Overview

Customer uploads a CSV or Excel file. The connector parses, infers types, samples rows, and exposes the file as a single source table. No live sync — refreshing means uploading again. Multiple files = multiple "tables" in the same connector.

Excel handling supports `.xlsx` only (not legacy `.xls`); each sheet is treated as a separate table named after the sheet.

## 2. Module Layout

```
server/app/connectors/csv/
├── __init__.py
├── connector.py              # CSVUploadConnector implementing Connector Protocol
├── upload.py                 # multipart upload handler; size limits; virus scan hook (M3+)
├── parser.py                 # csv reader with locale-aware delimiter detection (no regex; uses csv.Sniffer)
├── excel.py                  # openpyxl wrapper for .xlsx
├── type_inference.py         # observe sample values; produce SourceColumn with source_type
├── storage.py                # uploaded files in S3 / local FS; encrypted at rest
└── tests/
    ├── test_contract.py
    ├── test_parser.py
    ├── test_excel.py
    └── fixtures/
        ├── customers_clean.csv
        ├── orders_with_dates_and_money.csv
        ├── messy_quoting.csv
        └── multi_sheet.xlsx
```

## 3. Capabilities

```python
metadata = ConnectorMetadata(
    name="csv",
    display_name="CSV / Excel Upload",
    version="1.0.0",
    auth_kind=AuthKind.FILE_UPLOAD,
    capabilities=ConnectorCapabilities(
        can_introspect=True,
        can_read=True,
        can_write=False,                          # one-way: upload-only
        can_subscribe_webhooks=False,
        supports_pagination=True,
        supports_streaming=True,                  # row-by-row read
        requires_periodic_sync=False,             # refreshing = re-upload
        write_back_canonical_only=False,          # writes never go back to a CSV
    ),
)
```

## 4. Auth

`AuthCredentials.payload` carries the upload reference (`upload_id`) returned from a multipart upload endpoint. The actual file content is stored in S3 under a per-tenant prefix; the token references the S3 object.

File size limit: 100 MB hosted (configurable per plan); 1 GB self-host. Larger files: instruct user to use Postgres connector instead.

## 5. Introspection

CSV: `csv.Sniffer` detects delimiter and quoting (no regex; standard-library deterministic dialect detection). When detection fails, the parser raises `BF-CONN-CSV-006` rather than silently falling back to comma — per [`05-coding-rules.md`](../05-coding-rules.md) §5.3 we don't substitute defaults for unparseable inputs.

Header detection is a deterministic per-column **type-disagreement** algorithm: each cell is classified PRIMITIVE (int / float / bool / iso-date / iso-datetime) or LABEL; row 0 is a header iff at least one column has a label-shaped row 0 over a typed-data column 1+. Pure-text tables (e.g. names + free-text) and single-row inputs are structurally ambiguous and surface `BF-CONN-CSV-005`. Users can pin the answer by setting `has_header: bool` in the upload credentials payload.

Excel: `openpyxl` reads sheet names; each sheet becomes a `SourceTable`.

For each column, `type_inference.py` reads up to 1000 sample values and records:
- Observed pattern (numeric / boolean / temporal / string).
- Distinct count.
- Null-equivalent values (empty string, "N/A", "null"; treated as nullable).
- For numerics: integer vs float; observed range.
- For temporal: detected formats (ISO 8601 first; common locale formats fallback).

`source_type` strings are preserved (e.g., `"text"`, `"integer"`, `"datetime_iso8601"`); `ColumnClassifier` later assigns semantic types from these + sample values + reconciliation context.

## 6. Read

Streaming row read: yields one `Row` at a time. Pagination via `LIMIT`-style slicing of the iterator. No filter pushdown (CSV/Excel don't support it); filters are applied in-memory after read with a warning if the file is large.

## 7. Write

Not supported (`can_write=False`). Calling `write()` raises `BF-CONN-002`. Refreshing a CSV-backed entity means uploading a new file (which becomes a new version of the connector source).

## 8. Storage

Uploaded files stored in S3 under `s3://baseflo-uploads/<org_id>/<project_id>/<connector_id>/<upload_id>.<ext>`. Encrypted at rest (S3 server-side encryption + tenant DEK envelope). Retained for 1 year by default; configurable per plan. Hard-deleted along with project deletion.

## 9. Test Plan

- Contract suite — required.
- Parser tests:
  - Standard CSV with headers.
  - CSV with embedded commas in quoted fields.
  - CSV with trailing newlines.
  - CSV with mixed line endings.
  - Excel with multiple sheets.
  - Empty file → typed `BF-CONN-CSV-001`.
- Type inference: numeric / boolean / temporal / string detection.
- Streaming read with row limit.
- Coverage: 90%.

## 10. Error Codes

| Code | Condition |
|---|---|
| `BF-CONN-CSV-001` | File empty or unreadable |
| `BF-CONN-CSV-002` | File exceeds size limit |
| `BF-CONN-CSV-003` | Excel sheet count exceeds limit (50 sheets) |
| `BF-CONN-CSV-004` | Encoding could not be detected; user prompted to specify |
| `BF-CONN-CSV-005` | Header row could not be auto-detected and `has_header` not specified |
| `BF-CONN-CSV-006` | CSV dialect (delimiter / quoting) could not be determined |

## 11. Dependencies

[`CONN-FRAMEWORK`](CONN-FRAMEWORK.md), `csv` (stdlib), `openpyxl`, S3.

## 12. Milestone

- **M1**: full implementation; powers the "drop your spreadsheet" magic moment for SMB users.
- **M2**: virus scan integration (ClamAV); per-row error reporting on partial parse failures.
- **M3+**: large-file streaming via S3 select; column-rename UI before introspection commits.
