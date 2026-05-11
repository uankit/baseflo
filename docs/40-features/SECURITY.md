# `SECURITY` — Privacy & Security Primitives

Status: M0–M3. Combines `SEC-KMS` + `SEC-TOKENS` + `SEC-PII-MASK` + `SEC-EXPORT` + `SEC-DELETE` + `AUDIT-CORE`. The technical expression of the brand promise: **"Your data stays yours."**

---

## 1. Overview

Five primitives that compose the privacy/security posture from day one:

1. **Per-tenant KMS envelope encryption** for at-rest customer data (Hosted Cloud).
2. **Encrypted connector tokens** with per-tenant DEK; revocation propagates to source providers when supported.
3. **PII field masking** by default in admin UI + log scrubber (PII fields per `ColumnClassifier`).
4. **One-click full data export** ("take everything and leave"; CSV + SQL + JSON).
5. **One-click data deletion** (30-day soft delete, then hard delete; audit-logged).
6. **Audit log** (`audit_events`) — tamper-evident chain (M3+).

Everything ties back to the per-tenant KEK in AWS KMS (or per-tenant local key in Self-Host).

## 2. High-Level Design

```
┌─────────────────────────────────────────────────────────────────┐
│              KMS (per-tenant KEK, root)                          │
└──────────────────────┬──────────────────────────────────────────┘
                       │ wraps
                       ▼
              ┌─────────────────────────┐
              │ Per-tenant DEK          │ (rotated monthly; lazy on first use)
              └──────────┬──────────────┘
                         │ encrypts
        ┌────────────────┼────────────────┬─────────────────┐
        ▼                ▼                ▼                 ▼
  Connector tokens  BYO-DB DSNs    OAuth refresh tokens   Sensitive config
  (connector_      (tenant_data    (oauth_identities       (encrypted
  tokens.cipher    _dsn_encrypted) .refresh_token_         columns where
  text)                            encrypted)              applicable)

  PII column masking (admin UI + log scrub) reads ColumnClassifier output;
  click-to-reveal logs to audit_events; auto-remasks after 30s.

  Export job: full project blob → SQL + CSV + JSON → S3 signed URL (24h).
  Delete: soft for 30 days → hard delete; audit-logged at both stages.
```

## 3. Low-Level Design

### 3.1 Module Layout

```
server/app/core/crypto/
├── __init__.py
├── kms.py                    # AWS KMS wrapper (or local-key for self-host)
├── envelope.py               # encrypt/decrypt with per-tenant DEK; rotation
├── hashing.py                # argon2id helpers (passwords, API keys)
├── secret_scanning.py        # log scrubber for ColumnClassifier-flagged PII
└── tests/

server/app/services/
├── data_export/
│   ├── service.py            # export job runner; produces SQL + CSV + JSON
│   ├── packagers/
│   │   ├── csv.py
│   │   ├── sql.py
│   │   └── json.py
│   └── tests/
├── data_deletion/
│   ├── service.py            # soft-delete now; hard-delete in 30 days
│   ├── scheduler.py          # nightly job
│   └── tests/
└── audit/
    ├── service.py            # AuditLogger.write(...) + queryers
    ├── chain.py              # M3+: cryptographic hash chaining
    └── siem_export.py        # M3+: Splunk / Datadog / syslog
```

### 3.2 Key Types

```python
class EncryptedBlob(BaseModel):
    ciphertext: bytes
    nonce: bytes
    wrapped_dek: bytes          # tenant DEK wrapped by tenant KEK
    kek_alias: str              # KMS alias / self-host key ref

class ExportFormat(StrEnum):
    CSV   = "csv"
    SQL   = "sql"
    JSON  = "json"
    FULL  = "full"              # all three in one tarball

class ExportRequest(BaseModel):
    project_id: UUID
    project_version_id: UUID
    formats: list[ExportFormat]
    requested_by: UUID

class ExportResult(BaseModel):
    export_id: UUID
    file_url_signed: str        # S3 signed URL, 24h expiry
    expires_at: datetime
    sha256: str

class DeletionRequest(BaseModel):
    project_id: UUID            # or organization_id for full org delete
    requested_by: UUID
    confirmation_text: str      # must equal project name; client enforces
    scheduled_hard_delete_at: datetime  # = now + 30 days

class AuditEvent(BaseModel):
    id: UUID
    organization_id: UUID
    actor_type: ActorType        # USER | AGENT | SYSTEM | API_KEY
    actor_id: str
    action: AuditAction          # READ | WRITE | DELETE | EXPORT | CONNECTOR_CONNECT | CONNECTOR_REVOKE | AUTH_LOGIN | AUTH_LOGOUT | PII_REVEAL
    target_kind: str
    target_id: str
    metadata: dict               # request_id, ip, user_agent
    created_at: datetime
    chain_hash: str | None       # M3+: hash of previous row + this row's content
```

### 3.3 Envelope Encryption

```python
class EnvelopeCrypto:
    def __init__(self, kms_client: KMSClient, tenant_kek_alias: str):
        self._kms = kms_client
        self._kek_alias = tenant_kek_alias

    async def encrypt(self, plaintext: bytes) -> EncryptedBlob:
        dek = self._kms.generate_data_key(self._kek_alias)         # returns plaintext + ciphertext (wrapped)
        ciphertext, nonce = aes_gcm_encrypt(dek.plaintext, plaintext)
        return EncryptedBlob(
            ciphertext=ciphertext, nonce=nonce,
            wrapped_dek=dek.ciphertext, kek_alias=self._kek_alias,
        )

    async def decrypt(self, blob: EncryptedBlob) -> bytes:
        dek = self._kms.decrypt(blob.wrapped_dek)                   # uses KEK
        return aes_gcm_decrypt(dek, blob.ciphertext, blob.nonce)
```

DEK rotation: monthly cron re-wraps DEKs with current KEK; old wrapped DEKs retained for 30 days for emergency decryption.

### 3.4 PII Masking

`ColumnClassifier` flags columns with `pii_*` semantic types and `pii_masked_by_default = True`. Two surfaces enforce:

- **Admin UI**: list and detail views show masked values (e.g., `j***n@example.com`); click-to-reveal action calls `POST /api/v1/projects/:id/pii/reveal` with field reference; server checks role, writes audit event, returns plaintext for 30s.
- **Log scrubber**: `structlog` processor inspects every log record; replaces values of any field matching a PII column path with `***REDACTED***`. The list of PII paths is computed once per project version and cached.

The scrubber does NOT use regex on free-text fields. Free-text PII (names embedded in notes, etc.) is NOT auto-detected in v1; flagged for v3 with Presidio integration.

### 3.5 Data Export

A user with Owner or Admin role clicks Settings → Export. Job enqueued; output written to S3 with a per-tenant prefix; signed URL emailed. SQL format includes DDL + INSERT statements per table (re-importable). CSV format includes one file per table. JSON format includes the full project artifact (IR + KPIs + dashboard spec + connector configs minus secrets) plus per-table row arrays.

Sensitive data export — when PII columns are included — requires an additional confirmation and is audit-logged.

### 3.6 Data Deletion

- Soft delete (immediate): `deleted_at` timestamp set on `projects` row; project disappears from UI; data retained.
- Hard delete (T+30 days): nightly scheduler hard-deletes the project's tenant schema (Hosted Cloud) or drops the per-project schema in customer's DB (BYO-DB) and removes control-plane rows.
- During the 30-day soft window, an Admin can restore.
- Audit events written at both soft and hard deletion.
- Org-level delete: same flow, but cascades to all projects.

### 3.7 Audit Chain (M3+)

Every `audit_events` row carries `chain_hash = sha256(previous_row.chain_hash || row_content)`. A daily transparency receipt publishes the latest chain head to a public log (or, for self-host, customer's chosen append-only store). Tamper detection: an attacker who modifies an audit row breaks the chain.

## 4. Design Patterns Applied

| Pattern | Where | Why |
|---|---|---|
| **Envelope Encryption** | `EnvelopeCrypto` | Industry standard for SaaS at-rest encryption with per-tenant key isolation. |
| **Decorator** | Log scrubber as a `structlog` processor | Cross-cutting; never leaks into business code. |
| **Strategy** | KMS provider (AWS KMS hosted; local file for self-host) | Same envelope semantics, different key store. |
| **Append-Only Log + Hash Chain** | Audit chain | Tamper evidence; standard in compliance-heavy contexts. |
| **Saga** | Soft → hard delete | 30-day compensation window; manual restore possible during window. |

## 5. Test Plan

- KMS tests: encrypt/decrypt round-trip; decryption fails with wrong KEK; rotation preserves access to old blobs.
- PII reveal: only authorized roles; audit row written; auto-remask after 30s.
- Log scrub: PII column values redacted from log records (positive and negative tests).
- Export: full project export round-trips (re-import yields same IR + same data).
- Soft/hard delete: scheduled job clears 30-day-old soft-deleted projects; restore during window works.
- Audit chain: tampering with an audit row breaks chain validation.
- Coverage: 95% (security-critical).

## 6. Error Codes

| Code | Condition | Recovery |
|---|---|---|
| `BF-SEC-001` | Decryption failed (key mismatch / corruption) | Surface to operator; refuse to display data. |
| `BF-SEC-002` | PII reveal denied (role) | UI message; ask admin. |
| `BF-SEC-003` | Export job failed | Retry; surface failure if persistent. |
| `BF-SEC-004` | Deletion confirmation text mismatch | UI feedback; user retries. |
| `BF-SEC-005` | Audit chain broken | Operator alert; surface to compliance team. |
| `BF-SEC-006` | KMS unreachable | Retry with backoff; surface as terminal if persistent. |

## 7. Dependencies

[`AGENT-COL`](AGENT-COL.md) (PII column flags), [`04-database-schema.md`](../04-database-schema.md) (`audit_events`, `connector_tokens`, etc.), [`AUTH`](AUTH.md), AWS KMS, S3.

## 8. Milestone

- **M0**: KMS envelope encryption; encrypted connector tokens; PII masking + reveal; one-click export + delete; basic audit log.
- **M1**: log scrubber processor live; nightly hard-delete scheduler; export-import round trip tested.
- **M3**: SIEM export; tamper-evident audit chain; daily transparency receipt; data residency (EU region).
- **M5+**: Presidio integration for free-text PII detection.
