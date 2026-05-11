# `CONN-SHEETS` — Google Sheets Connector

Status: M1. Live read of Google Sheets with periodic poll-based sync. The other "drop your spreadsheet" path — same wedge as CSV upload but stays connected.

---

## 1. Overview

Customer connects via Google OAuth, picks one or more Google Sheets, and the connector treats each as a source table (one sheet per table). Sync is poll-based on a configurable cadence (default 15 minutes); when Google's Drive Activity API returns an "edited" event for a sheet, the next poll runs immediately rather than waiting for the cadence.

This is the connector that lets a yoga studio keep its existing Sheets-based bookings spreadsheet *and* see it reconciled into the Baseflo workspace, without migrating away.

## 2. Module Layout

```
server/app/connectors/sheets/
├── __init__.py
├── connector.py              # GoogleSheetsConnector
├── oauth.py                  # OAuth2 flow with Google
├── api.py                    # google-api-python-client wrapper (Sheets v4 + Drive v3)
├── introspection.py          # sheet metadata + cell range probing
├── reader.py                 # batch GET cell ranges; paginate large sheets
├── activity.py               # Drive Activity API for change detection
└── tests/
    ├── test_contract.py
    ├── test_oauth.py
    └── fixtures/
        ├── recorded_oauth_responses.json
        └── recorded_sheet_responses.json
```

## 3. Capabilities

```python
metadata = ConnectorMetadata(
    name="google_sheets",
    display_name="Google Sheets",
    version="1.0.0",
    auth_kind=AuthKind.OAUTH2,
    capabilities=ConnectorCapabilities(
        can_introspect=True,
        can_read=True,
        can_write=True,                           # appending and updating cells supported
        can_subscribe_webhooks=False,             # Sheets API has no push; polling only
        supports_pagination=True,
        supports_streaming=False,                 # batch-only read
        requires_periodic_sync=True,              # default 15 min
        write_back_canonical_only=True,
    ),
    required_scopes=[
        "https://www.googleapis.com/auth/spreadsheets.readonly",
        "https://www.googleapis.com/auth/drive.metadata.readonly",
    ],
    optional_scopes=[
        "https://www.googleapis.com/auth/spreadsheets",     # write access; prompted explicitly
    ],
)
```

## 4. Auth

OAuth2 with PKCE. Refresh token stored encrypted (tenant KMS). Token rotation on every API call where `expires_at < now() + 60s`. Revocation via Google's revoke endpoint when user disconnects.

Scopes:
- Default: read-only on Sheets + read on Drive metadata (to list available sheets).
- Optional: read/write on Sheets (prompted when user enables write-back).

## 5. Introspection

For each connected spreadsheet:
1. Fetch spreadsheet metadata (`spreadsheets.get`).
2. For each sheet (tab): treat as a `SourceTable`.
3. Probe row 1 for headers (column names); fall back to `column_A`, `column_B`, etc. if no headers.
4. Sample ~50 rows for `SourceColumn.sample_values` and source-type inference.
5. Estimated row count from sheet dimensions.

`source_type` is one of `"string" | "number" | "boolean" | "datetime"` based on sample value inspection (using Sheets' value type metadata, not regex).

## 6. Read

Batch `spreadsheets.values.batchGet` for ranges. Pagination via row-range chunking (default 1000 rows per call). Filters and sorts not pushed down to the API; applied in-memory after read.

## 7. Write

When the optional scope is granted:
- INSERT → append row via `spreadsheets.values.append`.
- UPDATE → identify row by primary-key cell match, update via `spreadsheets.values.update`.
- DELETE → not supported (Sheets API has no row-delete primitive that doesn't shift rows; we'd corrupt downstream references). Calling delete raises `BF-CONN-SHEETS-001`.

## 8. Sync Cadence + Change Detection

Periodic poll: every 15 min by default. On each poll:
1. Call Drive Activity API for the spreadsheet's most recent edits.
2. If `lastModifyTime > last_polled_at`, schedule an immediate re-introspect + re-read.
3. Otherwise skip until next interval.

Customers on Pro+ can lower the cadence to 5 min; Business+ to 1 min.

## 9. Test Plan

- Contract suite — required.
- OAuth tests with `vcr.py`-recorded responses (no live network in CI).
- Introspection: spreadsheets with multiple sheets, headerless sheets, empty sheets.
- Read: pagination across large sheets; filter/sort applied correctly.
- Write: append + update; delete raises typed error.
- Token refresh: expired token triggers refresh transparently.
- Coverage: 88%.

## 10. Error Codes

| Code | Condition |
|---|---|
| `BF-CONN-SHEETS-001` | DELETE not supported |
| `BF-CONN-SHEETS-002` | OAuth scope insufficient (write requested, only read granted) |
| `BF-CONN-SHEETS-003` | Spreadsheet not found / access revoked |
| `BF-CONN-SHEETS-004` | Rate limit hit (Google API quota) |
| `BF-CONN-SHEETS-005` | Header row not detected |

## 11. Dependencies

[`CONN-FRAMEWORK`](CONN-FRAMEWORK.md), `google-api-python-client`, `authlib`, [`SECURITY`](SECURITY.md) (token encryption).

## 12. Milestone

- **M1**: full implementation; OAuth flow integrated into onboarding; SMB users can connect a Sheets-based bookings/contacts spreadsheet.
- **M2**: write-back hardened (idempotent appends; primary-key-based updates).
- **M3+**: per-cell change tracking for finer-grained reconciliation history.
