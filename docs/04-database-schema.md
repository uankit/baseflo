# Baseflo — Database Schema (Control Plane)

Status: locked for v1. Per-tenant generated data schemas live separately and are managed by the engine through the data-plane interface; this document covers the control plane only.

Defers to `01-architecture.md` for system context and `00-decisions.md` for the privacy model.

---

## 1. Two Databases, Two Lifecycles

Baseflo separates two concerns at the database boundary:

1. **Control plane** — our metadata. Organizations, users, projects, connectors, agent runs, audit log. Always lives in Baseflo's managed Postgres (or, for self-host, in the bundled Docker Postgres). Single owner: us.
2. **Tenant data plane** — the customer's actual business data. In Hosted-Cloud mode this lives in our Postgres in a tenant-scoped schema; in BYO-DB mode it lives in the customer's Postgres; in Self-Host mode it lives in the bundled Docker Postgres on customer infra. The data-plane interface abstracts which.

This document specifies the **control plane**. Tenant-data schemas are generated per-project from the unified `SchemaIR` (see `01-architecture.md` §3.3); each project's tables, columns, and constraints come from agent decisions, not from this document.

## 2. Conventions

- Engine: Postgres 16.
- All ids are `UUID v7` (time-sortable; index-friendly).
- All timestamps are `TIMESTAMPTZ`, UTC.
- All currency stored as minor units in `BIGINT` columns suffixed `_minor` plus a sibling `*_currency` `CHAR(3)` column.
- All soft deletes via `deleted_at TIMESTAMPTZ NULL`. Hard deletes only for tokens and ephemeral SSE events.
- All tables include `created_at` (NOT NULL DEFAULT now()), `updated_at` (NOT NULL DEFAULT now(), updated by trigger).
- All multi-tenant tables include `organization_id UUID NOT NULL` and a row-level security policy.
- Foreign keys cascade thoughtfully: ownership cascades on parent delete; reference relationships restrict.
- Check constraints favor enums (`CHECK (status IN (...))`) over free-text.
- Indexes are explicit; no `CREATE INDEX CONCURRENTLY` left out of migrations.

## 3. Entity Relationship (overview)

```
organizations
  ├── users (via memberships)
  ├── workspaces
  │     └── projects
  │           ├── project_versions  (immutable, parent-linked)
  │           ├── connectors
  │           │     └── connector_tokens (encrypted)
  │           ├── conversations
  │           │     ├── conversation_messages
  │           │     └── conversation_events  (sse, persisted, replayable)
  │           ├── generation_jobs
  │           │     └── generation_steps
  │           ├── agent_runs
  │           │     └── agent_run_attempts
  │           ├── refinements
  │           ├── exports
  │           ├── share_links
  │           └── feedback_events
  ├── audit_events  (org-scoped audit log)
  ├── api_keys      (per-org programmatic access)
  └── billing_subscriptions

users
  ├── sessions
  └── oauth_identities  (provider, subject)

system
  ├── system_health  (worker heartbeat, queue depth snapshots)
  └── failed_jobs    (DLQ)
```

## 4. Table Specifications

### 4.1 `organizations`

The billing entity. One organization owns workspaces, projects, billing, and roll-up audit logs.

| Column | Type | Notes |
|---|---|---|
| `id` | `UUID` | PK |
| `name` | `TEXT` | Display name |
| `slug` | `TEXT` UNIQUE | URL-safe identifier |
| `plan` | `TEXT` | enum: `hobby`, `pro`, `business`, `enterprise` |
| `status` | `TEXT` | enum: `active`, `paused`, `cancelled` |
| `kms_key_arn` | `TEXT` | per-tenant KMS key reference; NULL for self-host |
| `region` | `TEXT` | enum: `us-east-1`, `eu-west-1`, ... |
| `created_at`, `updated_at`, `deleted_at` | `TIMESTAMPTZ` | |

Indexes: `(slug)` unique; `(status, created_at)` for ops queries.

### 4.2 `users`

Auth identities. A user can belong to multiple organizations.

| Column | Type | Notes |
|---|---|---|
| `id` | `UUID` | PK |
| `email` | `CITEXT` UNIQUE | case-insensitive |
| `email_verified_at` | `TIMESTAMPTZ` NULL | |
| `display_name` | `TEXT` NULL | |
| `password_hash` | `TEXT` NULL | argon2id; NULL when only OAuth |
| `last_login_at` | `TIMESTAMPTZ` NULL | |
| `created_at`, `updated_at`, `deleted_at` | `TIMESTAMPTZ` | |

Indexes: `(email)` unique.

### 4.3 `memberships`

Bridges users ↔ organizations with role.

| Column | Type | Notes |
|---|---|---|
| `id` | `UUID` | PK |
| `organization_id` | `UUID` FK→organizations | RLS scope |
| `user_id` | `UUID` FK→users | |
| `role` | `TEXT` | enum: `owner`, `admin`, `editor`, `viewer` |
| `invited_by` | `UUID` FK→users NULL | |
| `accepted_at` | `TIMESTAMPTZ` NULL | NULL until accepted |
| `created_at`, `updated_at`, `deleted_at` | `TIMESTAMPTZ` | |

Indexes: `(organization_id, user_id)` unique.

### 4.4 `sessions`

Auth sessions (Lucia-style).

| Column | Type | Notes |
|---|---|---|
| `id` | `UUID` | PK; session token derived |
| `user_id` | `UUID` FK→users | |
| `expires_at` | `TIMESTAMPTZ` | |
| `revoked_at` | `TIMESTAMPTZ` NULL | |
| `user_agent`, `ip_address` | `TEXT` | for audit |
| `created_at` | `TIMESTAMPTZ` | |

Indexes: `(user_id, expires_at)`.

### 4.5 `oauth_identities`

OAuth provider linkage.

| Column | Type | Notes |
|---|---|---|
| `id` | `UUID` | PK |
| `user_id` | `UUID` FK→users | |
| `provider` | `TEXT` | enum: `google`, `github`, `microsoft` |
| `subject` | `TEXT` | provider's user id |
| `created_at`, `updated_at` | `TIMESTAMPTZ` | |

Indexes: `(provider, subject)` unique.

### 4.6 `workspaces`

A grouping inside an organization. Holds projects.

| Column | Type | Notes |
|---|---|---|
| `id` | `UUID` | PK |
| `organization_id` | `UUID` FK→organizations | RLS scope |
| `name`, `slug` | `TEXT` | |
| `created_by` | `UUID` FK→users | |
| `created_at`, `updated_at`, `deleted_at` | `TIMESTAMPTZ` | |

Indexes: `(organization_id, slug)` unique.

### 4.7 `projects`

A connected business — the unit a customer thinks of as "my CRM."

| Column | Type | Notes |
|---|---|---|
| `id` | `UUID` | PK |
| `organization_id` | `UUID` FK→organizations | RLS scope |
| `workspace_id` | `UUID` FK→workspaces | |
| `name`, `slug` | `TEXT` | |
| `description` | `TEXT` | the user's one-sentence business description |
| `current_version_id` | `UUID` FK→project_versions NULL | latest version |
| `deployment_mode` | `TEXT` | enum: `hosted`, `byo_db`, `self_host`, `local_dev` |
| `tenant_data_dsn_encrypted` | `BYTEA` NULL | for `byo_db`; encrypted with org KMS |
| `tenant_data_schema_name` | `TEXT` NULL | for `hosted`; per-tenant schema in our PG |
| `created_by` | `UUID` FK→users | |
| `created_at`, `updated_at`, `deleted_at` | `TIMESTAMPTZ` | |

Indexes: `(organization_id, workspace_id, slug)` unique; `(current_version_id)`.

### 4.8 `project_versions`

Every refinement creates a new immutable version. Parent lineage preserved.

| Column | Type | Notes |
|---|---|---|
| `id` | `UUID` | PK |
| `project_id` | `UUID` FK→projects | |
| `parent_version_id` | `UUID` FK→project_versions NULL | NULL for root |
| `version_number` | `INT` | monotonic per project |
| `schema_ir` | `JSONB` | the unified IR; typed contract on read |
| `kpi_definitions` | `JSONB` | typed list |
| `dashboard_spec` | `JSONB` | typed |
| `intelligence_taxonomy` | `JSONB` | event types and their semantics |
| `assumptions` | `JSONB` | explicit assumptions surfaced by agents |
| `validation_status` | `TEXT` | enum: `passed`, `warning`, `failed`, `pending` |
| `validation_report` | `JSONB` | findings |
| `created_by` | `UUID` FK→users NULL | NULL for system-initiated |
| `created_at` | `TIMESTAMPTZ` | |

Indexes: `(project_id, version_number)` unique; `(parent_version_id)`; GIN on `schema_ir` for ad-hoc queries during ops.

### 4.9 `connectors`

Per-project source connections.

| Column | Type | Notes |
|---|---|---|
| `id` | `UUID` | PK |
| `organization_id` | `UUID` FK→organizations | RLS scope |
| `project_id` | `UUID` FK→projects | |
| `kind` | `TEXT` | enum: `postgres`, `csv`, `excel`, `notion`, `shopify`, `stripe`, `mailchimp`, ... |
| `display_name` | `TEXT` | user-given |
| `status` | `TEXT` | enum: `connected`, `error`, `revoked`, `expired` |
| `config` | `JSONB` | non-secret connection config (e.g., shop domain, db host) |
| `last_sync_at` | `TIMESTAMPTZ` NULL | |
| `last_error` | `JSONB` NULL | error details if status=`error` |
| `created_at`, `updated_at`, `deleted_at` | `TIMESTAMPTZ` | |

Indexes: `(project_id, kind)`; `(status, last_sync_at)` for sync scheduler.

### 4.10 `connector_tokens`

Encrypted credentials. One row per token; rotated tokens create new rows; old rows are soft-deleted.

| Column | Type | Notes |
|---|---|---|
| `id` | `UUID` | PK |
| `connector_id` | `UUID` FK→connectors | |
| `token_type` | `TEXT` | enum: `oauth2`, `api_key`, `db_url`, `service_account` |
| `ciphertext` | `BYTEA` NOT NULL | envelope-encrypted with tenant DEK |
| `wrapped_dek` | `BYTEA` NOT NULL | DEK wrapped by tenant KEK in KMS |
| `expires_at` | `TIMESTAMPTZ` NULL | for OAuth refreshable |
| `scopes` | `TEXT[]` | granted scopes for audit |
| `revoked_at` | `TIMESTAMPTZ` NULL | |
| `created_at` | `TIMESTAMPTZ` | |

Indexes: `(connector_id, revoked_at)`.

### 4.11 `conversations`

Per-project user-system dialogue.

| Column | Type | Notes |
|---|---|---|
| `id` | `UUID` | PK |
| `organization_id`, `project_id` | `UUID` | RLS + scope |
| `started_by` | `UUID` FK→users | |
| `state` | `TEXT` | enum: `active`, `awaiting_clarification`, `closed` |
| `created_at`, `updated_at` | `TIMESTAMPTZ` | |

### 4.12 `conversation_messages`

| Column | Type | Notes |
|---|---|---|
| `id` | `UUID` | PK |
| `conversation_id` | `UUID` FK→conversations | |
| `author` | `TEXT` | enum: `user`, `system`, `agent` |
| `agent_name` | `TEXT` NULL | when author=`agent` |
| `content` | `TEXT` | |
| `metadata` | `JSONB` | structured data accompanying message |
| `created_at` | `TIMESTAMPTZ` | |

### 4.13 `conversation_events` (SSE persisted stream)

Persistent event log; client can replay from a sequence number.

| Column | Type | Notes |
|---|---|---|
| `id` | `UUID` | PK |
| `conversation_id` | `UUID` FK→conversations | |
| `sequence` | `BIGINT` | monotonic within conversation |
| `event_type` | `TEXT` | enum: `clarification.required`, `agent.start`, `agent.complete`, `validation.passed`, `validation.warning`, `validation.failed`, `artifact.ready`, `workspace.ready`, `error.recoverable`, `error.terminal` |
| `payload` | `JSONB` | typed per event_type |
| `created_at` | `TIMESTAMPTZ` | |

Indexes: `(conversation_id, sequence)` unique; `(created_at)` for retention sweeps.

Channel: a Postgres NOTIFY is fired on insert: `NOTIFY conversation_<id>, '<sequence>'`. Workers and SSE handlers `LISTEN` per conversation.

### 4.14 `generation_jobs`

A generation run (initial build or refinement).

| Column | Type | Notes |
|---|---|---|
| `id` | `UUID` | PK |
| `project_id` | `UUID` FK→projects | |
| `parent_version_id` | `UUID` FK→project_versions NULL | |
| `kind` | `TEXT` | enum: `initial`, `refinement`, `connector_added`, `re_introspect` |
| `status` | `TEXT` | enum: `queued`, `running`, `succeeded`, `failed`, `cancelled` |
| `idempotency_key` | `TEXT` UNIQUE | |
| `started_at`, `completed_at` | `TIMESTAMPTZ` NULL | |
| `error` | `JSONB` NULL | typed `BF-AREA-NNN` failure |
| `created_at`, `updated_at` | `TIMESTAMPTZ` | |

### 4.15 `generation_steps`

Per-stage status inside a job (e.g., `column_classification`, `entity_reconciliation`, `physical_schema`).

| Column | Type | Notes |
|---|---|---|
| `id` | `UUID` | PK |
| `job_id` | `UUID` FK→generation_jobs | |
| `step_name` | `TEXT` | |
| `step_index` | `INT` | order |
| `status` | `TEXT` | enum: `pending`, `running`, `passed`, `warning`, `failed`, `skipped` |
| `input_hash`, `output_hash` | `TEXT` NULL | |
| `validation_status` | `TEXT` NULL | |
| `started_at`, `completed_at` | `TIMESTAMPTZ` NULL | |
| `error` | `JSONB` NULL | |

Indexes: `(job_id, step_index)`.

### 4.16 `agent_runs`

Per-agent execution. One per `(generation_step, agent_name)`.

| Column | Type | Notes |
|---|---|---|
| `id` | `UUID` | PK |
| `step_id` | `UUID` FK→generation_steps | |
| `agent_name` | `TEXT` | |
| `model_tier` | `TEXT` | |
| `model_name` | `TEXT` | resolved at run time |
| `input_hash`, `output_hash` | `TEXT` | |
| `started_at`, `completed_at` | `TIMESTAMPTZ` | |
| `duration_ms` | `INT` | |
| `input_tokens`, `output_tokens`, `cache_read_tokens`, `cache_write_tokens` | `INT` | from provider; never zeroed |
| `repair_attempts` | `INT` DEFAULT 0 | |
| `escalated` | `BOOLEAN` DEFAULT false | tier was bumped |
| `final_status` | `TEXT` | enum: `passed`, `warning`, `failed`, `needs_clarification` |

Indexes: `(step_id)`; `(agent_name, started_at)` for ops.

### 4.17 `agent_run_attempts`

One row per attempt within a run.

| Column | Type | Notes |
|---|---|---|
| `id` | `UUID` | PK |
| `agent_run_id` | `UUID` FK→agent_runs | |
| `attempt_number` | `INT` | 1-based |
| `prompt_hash` | `TEXT` | for cache and dedup |
| `output_payload` | `JSONB` NULL | typed output |
| `validation_error` | `JSONB` NULL | when validator raised `ModelRetry` |
| `usage` | `JSONB` | `{input_tokens, output_tokens, ...}` |
| `started_at`, `completed_at` | `TIMESTAMPTZ` | |

### 4.18 `refinements`

Per-version evolution intent.

| Column | Type | Notes |
|---|---|---|
| `id` | `UUID` | PK |
| `project_id`, `parent_version_id` | `UUID` | |
| `child_version_id` | `UUID` FK→project_versions NULL | populated when child commits |
| `intent_text` | `TEXT` | user's English description |
| `interpreted_intent` | `JSONB` | typed output of `IntentInterpreter` |
| `change_plan` | `JSONB` | typed output of `ChangePlanner` |
| `impact_summary` | `JSONB` | what changes |
| `status` | `TEXT` | enum: `proposed`, `applied`, `discarded`, `failed` |
| `created_by` | `UUID` FK→users | |
| `created_at`, `updated_at` | `TIMESTAMPTZ` | |

### 4.19 `exports`

User-requested data exports.

| Column | Type | Notes |
|---|---|---|
| `id` | `UUID` | PK |
| `organization_id`, `project_id`, `project_version_id` | `UUID` | |
| `format` | `TEXT` | enum: `csv`, `sql`, `json`, `full` |
| `status` | `TEXT` | enum: `queued`, `running`, `ready`, `expired`, `failed` |
| `file_url_signed` | `TEXT` NULL | S3 signed URL; expires 24h |
| `expires_at` | `TIMESTAMPTZ` NULL | |
| `requested_by` | `UUID` FK→users | |
| `created_at`, `completed_at` | `TIMESTAMPTZ` NULL | |

### 4.20 `share_links`

Read-only shareable views.

| Column | Type | Notes |
|---|---|---|
| `id` | `UUID` | PK |
| `organization_id`, `project_id`, `project_version_id` | `UUID` | |
| `token` | `TEXT` UNIQUE | URL-safe slug |
| `permissions` | `TEXT[]` | enum values |
| `expires_at` | `TIMESTAMPTZ` NULL | |
| `created_by` | `UUID` FK→users | |
| `revoked_at` | `TIMESTAMPTZ` NULL | |
| `created_at` | `TIMESTAMPTZ` | |

### 4.21 `feedback_events`

User corrections / signal for the data flywheel.

| Column | Type | Notes |
|---|---|---|
| `id` | `UUID` | PK |
| `organization_id`, `project_id`, `project_version_id` | `UUID` | |
| `target_type` | `TEXT` | enum: `entity_reconciliation`, `column_classification`, `kpi_selection`, `cardinality`, `general` |
| `target_id` | `TEXT` | natural key into the artifact |
| `correction` | `JSONB` | typed correction payload |
| `note` | `TEXT` NULL | freeform |
| `created_by` | `UUID` FK→users | |
| `created_at` | `TIMESTAMPTZ` | |

Curated and aggregated by the learning subsystem (later, see `app/learning/`); this is the raw flywheel input.

### 4.22 `audit_events`

Security audit log. Append-only.

| Column | Type | Notes |
|---|---|---|
| `id` | `UUID` | PK |
| `organization_id` | `UUID` FK→organizations | RLS scope |
| `actor_type` | `TEXT` | enum: `user`, `agent`, `system`, `api_key` |
| `actor_id` | `TEXT` | user id, agent name, or service id |
| `action` | `TEXT` | enum: `read`, `write`, `delete`, `export`, `connector.connect`, `connector.revoke`, `auth.login`, `auth.logout`, `pii.reveal` |
| `target_kind` | `TEXT` | resource kind |
| `target_id` | `TEXT` | resource id |
| `metadata` | `JSONB` | request id, ip, user agent |
| `created_at` | `TIMESTAMPTZ` | |

Indexes: `(organization_id, created_at DESC)`; partial on `action='pii.reveal'` for compliance reports.

Retention: 1 year hosted-cloud default; configurable in BYO/self-host.

### 4.23 `digest_subscriptions`

Daily digest preferences.

| Column | Type | Notes |
|---|---|---|
| `id` | `UUID` | PK |
| `organization_id`, `project_id` | `UUID` | |
| `user_id` | `UUID` FK→users | |
| `cadence` | `TEXT` | enum: `daily`, `weekly`, `off` |
| `delivery_time_local` | `TIME` | user's timezone-local |
| `timezone` | `TEXT` | IANA |
| `channels` | `TEXT[]` | enum: `email`, `slack`, `webhook` |
| `last_sent_at` | `TIMESTAMPTZ` NULL | |
| `created_at`, `updated_at` | `TIMESTAMPTZ` | |

### 4.24 `api_keys`

Per-org programmatic access.

| Column | Type | Notes |
|---|---|---|
| `id` | `UUID` | PK |
| `organization_id` | `UUID` FK→organizations | |
| `name` | `TEXT` | label |
| `prefix` | `TEXT` | first 8 chars for display |
| `hash` | `TEXT` | argon2id(secret) |
| `scopes` | `TEXT[]` | |
| `last_used_at` | `TIMESTAMPTZ` NULL | |
| `revoked_at` | `TIMESTAMPTZ` NULL | |
| `created_by` | `UUID` FK→users | |
| `created_at` | `TIMESTAMPTZ` | |

### 4.25 `billing_subscriptions`

| Column | Type | Notes |
|---|---|---|
| `id` | `UUID` | PK |
| `organization_id` | `UUID` FK→organizations | |
| `provider` | `TEXT` | enum: `stripe` |
| `external_subscription_id` | `TEXT` | |
| `plan` | `TEXT` | mirror of organizations.plan |
| `status` | `TEXT` | |
| `current_period_end` | `TIMESTAMPTZ` | |
| `created_at`, `updated_at` | `TIMESTAMPTZ` | |

### 4.26 `system_health`

Worker heartbeats and queue depth snapshots for ops.

| Column | Type | Notes |
|---|---|---|
| `id` | `UUID` | PK |
| `worker_id` | `TEXT` | hostname/pid |
| `metric` | `TEXT` | enum: `heartbeat`, `queue_depth`, `provider_latency_ms` |
| `value` | `DOUBLE PRECISION` | |
| `metadata` | `JSONB` | |
| `recorded_at` | `TIMESTAMPTZ` | |

Indexes: `(worker_id, recorded_at DESC)`; partition by month after 90 days.

### 4.27 `failed_jobs`

DLQ for `arq` jobs that exhausted retries.

| Column | Type | Notes |
|---|---|---|
| `id` | `UUID` | PK |
| `organization_id` | `UUID` NULL | when scoped |
| `job_kind` | `TEXT` | |
| `job_payload` | `JSONB` | |
| `error` | `JSONB` | typed |
| `attempt_count` | `INT` | |
| `created_at` | `TIMESTAMPTZ` | |

## 5. Multi-Tenancy Enforcement

- Every multi-tenant table includes `organization_id`.
- A Postgres role (`baseflo_app`) is the only DB role used by application code; `SET app.organization_id = ...` is set at the start of each request.
- Row-level security policies on every multi-tenant table enforce `organization_id = current_setting('app.organization_id')::uuid`.
- The repository layer cannot construct a query that targets a different `organization_id` than the request context — enforced by a session-scoped guard.

## 6. Encryption at Rest

- DB-level: AES-256 disk encryption (RDS or equivalent).
- App-level: connector tokens, BYO-DB DSNs, OAuth refresh tokens, and any sensitive config are envelope-encrypted (per-tenant DEK wrapped by per-tenant KEK in KMS).
- Encryption helpers live in `app/core/crypto.py` with constant-time wrappers; no ad-hoc encryption in feature code.

## 7. Indexing Strategy

- Primary keys are UUIDv7; secondary indexes on `(organization_id, created_at DESC)` for activity feeds.
- Foreign-key columns indexed by default.
- Unique constraints on `(organization_id, slug)` patterns.
- GIN indexes on JSONB columns only where ad-hoc queries are documented; we don't speculatively index JSONB.
- All indexes ship with explicit migrations using `CREATE INDEX CONCURRENTLY` to avoid prod locks.

## 8. Migration Approach

- Tool: Alembic (existing).
- Naming: `<YYYYMMDD>_<NNNN>_<short_description>.py`.
- Every migration ships with a downgrade.
- Breaking column changes use the expand/contract pattern (add new column → backfill → flip reads → drop old column in a separate migration).
- Migrations are run in CI against an empty database and a representative seed before merge.

## 9. Tenant-Data-Plane Schemas (separate concern, summarized)

For Hosted-Cloud mode, each project has a tenant-scoped Postgres schema named `tenant_<organization_slug>_<project_slug>`. The engine emits DDL into this schema based on the unified `SchemaIR` of the current project version. Tables generated here are entirely customer-business-driven and are not specified in this document.

For BYO-DB and Self-Host, the same DDL emission targets the customer's Postgres connection string instead.

The data-plane interface is:

```python
class DataPlane(Protocol):
    async def emit_ddl(self, schema_ir: SchemaIR) -> EmissionResult: ...
    async def query(self, plan: QueryPlan, tenant: TenantCtx) -> AsyncIterator[Row]: ...
    async def write(self, mutation: Mutation, tenant: TenantCtx) -> WriteResult: ...
    async def execute_kpi(self, kpi: KPIDefinition, tenant: TenantCtx) -> KPIResult: ...
```

Four implementations: `HostedDataPlane`, `BYODataPlane`, `SelfHostDataPlane`, `LocalDevDataPlane`.

## 10. Migration Order for v1 (M0)

The v1 migration pack will be:

1. `20260507_0001_init_organizations_users_memberships.py`
2. `20260507_0002_workspaces_projects_versions.py`
3. `20260507_0003_connectors_tokens.py`
4. `20260507_0004_conversations_events.py`
5. `20260507_0005_generation_jobs_steps_agents.py`
6. `20260507_0006_refinements_exports_shares_feedback.py`
7. `20260507_0007_audit_digests_apikeys_billing.py`
8. `20260507_0008_system_health_failed_jobs.py`
9. `20260507_0009_rls_policies.py`
10. `20260507_0010_indexes.py`

Existing migrations under `server/migrations/versions/` are evaluated and either kept (if compatible) or replaced. The audit said the existing four are sane; this pack supersedes them with the broader scope.
