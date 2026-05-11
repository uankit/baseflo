# Baseflo Alpha — Manual Test Plan

**Audience:** a developer-tester running through the alpha to confirm
nothing's broken before the team builds the web UI.

**Time budget:** ~3 hours for a full pass (1h setup + 2h test journeys).
~30 min if you only want to confirm the code-health checks pass.

**What you're testing:** see [§1](#1-what-the-alpha-is). What's intentionally
NOT in scope: see [§7 Known limitations](#7-known-limitations--dont-file-as-bugs).

---

## Table of contents

1. [What the alpha is](#1-what-the-alpha-is)
2. [Setup](#2-setup)
3. [Code-health gates (run first)](#3-code-health-gates-run-first)
4. [Test journeys](#4-test-journeys)
5. [Code review checklist](#5-code-review-checklist)
6. [Database verification queries](#6-database-verification-queries)
7. [Known limitations — don't file as bugs](#7-known-limitations--dont-file-as-bugs)
8. [How to report findings](#8-how-to-report-findings)

---

## 1. What the alpha is

Baseflo connects to the tools a business already uses (Shopify, Stripe,
Google Sheets, custom Postgres, plus CSV/Excel files), unifies the data
into a canonical model the AI architect agents propose, and exposes:

- A typed `@baseflo/sdk` (TypeScript).
- A `baseflo` CLI for devs (13 commands).
- A REST API at `/api/v1/...` with cookie-session auth.
- A web UI at `app.baseflo.com` — **in active build** per [`40-features/WEB-APP.md`](40-features/WEB-APP.md). The CLI/SDK journeys in this plan remain the authoritative server-test surface. Web-UI test journeys ship in a separate plan once `WEB-APP` reaches its milestone gates (M0/M1 per `WEB-APP.md` §20). Until then, web QA happens against the same backend exercised here.

**Two ICPs the alpha targets, both via CLI/SDK in this milestone:**

- **Indie devs** building on top of Baseflo (use the SDK + CLI).
- **SMB design partners** onboarded by the founder driving the CLI on a
  screen-share (no self-serve UI yet).

**Six connectors fully wired:** CSV, Excel, Postgres (read-only), Shopify
(read + write + webhooks), Stripe (read + write + webhooks), Google Sheets
(read + write + Drive push notifications).

**One agent pipeline** — eight stages from clarification through
schema/KPI design — actually runs against a real LLM (`gpt-4.1-mini` /
`gpt-4.1` / `o3-mini` per the model-routing tier table).

**One canonical data plane** — a per-tenant Postgres schema gets DDL
applied and rows backfilled from connectors after each agent run, then
stays current via webhook reconciliation.

**One refinement loop** — natural-language requests re-run agents and
emit a new project version with a diff.

---

## 2. Setup

### 2.1 Prerequisites

| Requirement | Min version | Notes |
|---|---|---|
| Docker Desktop | 25+ | For Postgres + Redis containers |
| Python | 3.12 | The server is async/await throughout |
| `uv` | 0.4+ | Python package manager (`pip install uv` if you don't have it) |
| Node.js | 18+ | For the SDK + CLI |
| `psql` | 15+ | For DB verification queries |
| (optional) Stripe test account | — | For Stripe install test |
| (optional) Shopify partner account + dev store | — | For Shopify OAuth |
| (optional) Google account + a spreadsheet | — | For Sheets OAuth |
| (optional) `ngrok` or similar | — | For webhook delivery in tests 9–10 |

### 2.2 Boot the stack

```bash
# 1. Clone
git clone <repo-url> Baseflo && cd Baseflo

# 2. Start Postgres + Redis
docker compose -f docker-compose.dev.yml up -d
docker compose -f docker-compose.dev.yml ps   # confirm both "healthy"

# 3. Server: install deps, run migrations, start API
cd server
uv sync                                       # installs all Python deps
cp .env.example .env                          # then edit (see 2.3)
uv run alembic upgrade head                   # applies all 19 migrations
uv run uvicorn app.main:app --reload --port 8000

# In a SECOND terminal — leave the server running:

# 4. SDK build (CLI links to it)
cd Baseflo/sdk/ts
npm install && npm run build

# 5. CLI
cd ../../cli
npm install && npm run build
npm link                                      # makes `baseflo` global
```

### 2.3 Required env vars (in `server/.env`)

```bash
BASEFLO_ENV=local
BASEFLO_DATABASE_URL=postgresql+asyncpg://baseflo:baseflo@localhost:5432/baseflo
BASEFLO_REDIS_URL=redis://localhost:6379/0
BASEFLO_API_BASE_URL=http://localhost:8000
BASEFLO_WEB_BASE_URL=http://localhost:5173
BASEFLO_SECRET_KEY=$(python -c "import secrets, base64; print(base64.b64encode(secrets.token_bytes(32)).decode())")
BASEFLO_LOCAL_KEK_BASE64=$(python -c "import secrets, base64; print(base64.b64encode(secrets.token_bytes(32)).decode())")
BASEFLO_KMS_PROVIDER=local

# Required for the LLM-backed agent saga (Test 6)
OPENAI_API_KEY=sk-...

# Optional — only if running the matching connector tests
BASEFLO_SHOPIFY_CLIENT_ID=...
BASEFLO_SHOPIFY_CLIENT_SECRET=...
BASEFLO_GOOGLE_CLIENT_ID=...
BASEFLO_GOOGLE_CLIENT_SECRET=...
BASEFLO_STRIPE_WEBHOOK_SECRET=whsec_...
```

### 2.4 Smoke-verify the boot

```bash
# Server alive
curl http://localhost:8000/api/v1/health
# expect: {"healthy": true, ...}

# CLI alive
baseflo --help
# expect: 13 commands listed (login, whoami, logout, orgs:create,
#         projects:create, projects:get, connect, connectors:list,
#         ask, refine, export, dev, logout)
```

If either fails — stop, check setup, **don't proceed**.

---

## 3. Code-health gates (run first)

Before any manual testing, confirm the codebase passes its own gates.
**Any red here is a bug — don't continue until they're green.**

```bash
# --- Server ---
cd server

# 3.1 Type check (strict)
uv run mypy --strict app/
# Expected: "Success: no issues found in 237 source files"

# 3.2 Unit tests (no DB required, ~3s)
uv run pytest tests/unit/ -q
# Expected: "766 passed"

# 3.3 Integration tests (require Postgres at baseflo:baseflo@localhost:5432)
uv run pytest tests/integration/ -m integration -q
# Expected: 29 passed (or some skipped if Postgres role missing — investigate)

# --- SDK ---
cd ../sdk/ts
npx tsc --noEmit
# Expected: clean

npx vitest run
# Expected: "12 passed (12)"

# --- CLI ---
cd ../../cli
npx tsc --noEmit
# Expected: clean
```

**File counts to expect** (so you can spot suspicious deletions):

- 237 Python source files in `server/app/`.
- 18 alembic migrations in `server/migrations/versions/`.
- 6 connectors in `server/app/connectors/{csv,excel,postgres,shopify,stripe,google_sheets}/`.

---

## 4. Test journeys

Each journey is a self-contained scenario. **Run them in order** — later
journeys assume earlier setup (org, project, connectors).

### Test 1 — Auth: magic-link sign-in

```bash
baseflo login --email tester@example.com
```

**Steps:**
1. Watch the **server's stdout**. Look for a log line like:

   ```
   [info] email_sent_via_log to=tester@example.com text_body="… token=ABCXYZ123… …"
   ```

2. Copy the token (everything after `?token=` and before `&` if there
   is one — typically ~43 url-safe chars).
3. Paste it at the CLI's `Token:` prompt.

**Expected:**

- ✅ "✓ Signed in as tester@example.com." printed.
- ✅ `~/.baseflo/credentials.json` created (mode 0600). Should contain
  `baseUrl`, `sessionToken`, `email` keys.
- ⚠️ `baseflo whoami` will fail because we have no organization yet —
  this is correct behavior. Don't file as a bug.

**Edge cases to verify:**

| Action | Expected |
|---|---|
| Paste a garbage token | Error: `BF-AUTH-006: Magic link is invalid, expired, or has already been used.` |
| Wait > 15 min, paste a real token | Same `BF-AUTH-006`. |
| Use a valid token twice | Second use → `BF-AUTH-006`. |
| `baseflo logout` then `baseflo whoami` | "Not signed in." |

### Test 2 — Org + project bootstrap

```bash
baseflo orgs:create acme --name "Acme Crochet"
```

**Expected:**

- ✅ "✓ Organization 'acme' created." with `organization_id`, `workspace_id`,
  `membership_id` printed.
- ✅ `~/.baseflo/credentials.json` now has `activeOrg=acme`.

```bash
baseflo projects:create growth --name "Growth dashboard"
```

**Expected:**

- ✅ "✓ Project 'growth' created." with `project_id`, `workspace_id` printed.
- ✅ Active project saved to credentials.

```bash
baseflo projects:get <project_id>
```

**Expected:**

- ✅ Prints project details with non-null `tenant_data_schema_name`
  (format: `tenant_<24 hex chars>`).
- ✅ `current_version_id` is `None` (no agent run yet).

**Edge cases:**

| Action | Expected |
|---|---|
| `baseflo orgs:create acme` again | `BF-VALID-009`: slug already taken (409). |
| `baseflo orgs:create "BAD SLUG"` | 400 (Pydantic pattern fail). |
| `baseflo projects:get <random uuid>` | 404. |

### Test 3 — Connector install (Stripe — easiest, no OAuth)

Skip if you don't have a Stripe test account. **This makes a real HTTP
call to api.stripe.com.**

```bash
baseflo connect stripe --api-key sk_test_<your real test key>
```

**Expected:**

- ✅ "✓ Stripe connector installed." with `connector_id` and `account_id`
  (real Stripe account id, e.g. `acct_1Pq...`).
- ⚠️ Server log: `webhook_subscribe_failed` warning is normal for local
  dev — Stripe can't deliver to `http://localhost:8000`. Use ngrok if you
  want to test webhook delivery in Test 9.

```bash
baseflo connectors:list
```

**Expected:**

- ✅ Stripe connector shown with `status=connected`.

**Edge cases:**

| Action | Expected |
|---|---|
| `--api-key sk_test_invalid` | `BF-CONN-STRIPE-002`: Stripe rejected the API key. |
| `--api-key short` | 400 (Pydantic min_length). |

### Test 4 — Connector install (Shopify — OAuth)

Skip if you don't have a Shopify partner account + dev store + the
`BASEFLO_SHOPIFY_CLIENT_ID/SECRET` set.

```bash
baseflo connect shopify --shop-domain your-test-store.myshopify.com
```

**Expected:**

- ✅ Prints a URL.
- ✅ Open in browser → Shopify "Authorize Baseflo" page.
- ✅ Click Install → redirects to your local `/api/v1/oauth/shopify/callback`.
- ✅ Browser shows JSON response (no UI yet); the connector is now installed.

**Verify in DB** (see [§6](#6-database-verification-queries) for psql commands):

- ✅ `connectors` row for kind=`shopify`, config has `shop_domain`.
- ✅ `connector_tokens` row with non-empty `ciphertext` (encrypted) and
  `wrapped_dek`.

**Verify webhook auto-subscribe:**

- Shopify admin → **Settings → Notifications → Webhooks** — should show
  ~9 new subscriptions pointing at your callback URL. (If you didn't run
  with ngrok, Shopify creates them but can't deliver — check the URL
  format only.)

### Test 5 — Connector install (Google Sheets — OAuth + Drive Push)

Skip if you don't have Google OAuth credentials configured.

```bash
baseflo connect sheets --spreadsheet-id <your spreadsheet id>
```

**Expected:**

- ✅ Prints URL with `prompt=consent` (forces refresh_token issue).
- ✅ Browser flow → grant `spreadsheets` + `drive.metadata.readonly` scopes.
- ✅ Callback completes.

**Verify:**

- ✅ DB: `connectors` row, `connector_tokens` row with refresh token in
  encrypted ciphertext.
- ✅ DB: `connector.config` includes a `webhook_subscription_id` (if
  ngrok is configured) — the Drive Push channel id. If you're on
  localhost, expect a logged `webhook_subscribe_failed` (Google requires
  HTTPS public URLs).

### Test 6 — The agent saga

This is the headline demo. Requires at least one connector installed.
**Costs OpenAI API tokens (~$0.10 per run).**

```bash
baseflo ask "Build me a customer 360 with churn risk and lifetime value"
```

**Expected output:** real-time SSE stream printing each agent stage:

```
19:32:41 agent.start          ClarificationAgent
19:32:43 agent.complete       ClarificationAgent 412t 1834ms
... (8 stages total) ...
19:33:09 validation.passed    workspace
19:33:09 workspace.ready      project=… version=…
```

**Verify in DB:**

- ✅ `project_versions` row created with non-empty JSONB `schema_ir`,
  `kpi_definitions`, `dashboard_spec`.
- ✅ `tenant_data_applications` row with `status=succeeded`,
  non-zero `statements_count`.
- ✅ The per-tenant Postgres schema (named `tenant_<hex>`) exists. List
  its tables: `\dn` then `\dt tenant_<hex>.*` in psql.
- ✅ Tables match what the IR proposed (e.g., `customers`, `orders`).
- ✅ Rows backfilled — `SELECT count(*) FROM tenant_<hex>.customers`
  should be > 0 if you connected a connector with data.
- ✅ `entity_id_map` rows mapping source IDs to canonical IDs.

**Edge cases:**

| Action | Expected |
|---|---|
| `baseflo ask "..."` with no connectors installed | Saga still runs (description-only); IR is empty; `workspace.ready` still fires. No DDL applied (correctly skipped). |
| Hit Ctrl-C mid-stream | CLI exits; saga continues server-side until natural end (or arq job timeout). |

### Test 7 — Refinement

Requires Test 6 completed.

```bash
baseflo refine "Add a churn metric per product type and track repeat purchases"
```

**Expected:**

- ✅ "✓ Refinement applied." with `new_version_id` printed.
- ✅ A diff summary lists added/modified KPIs and tables.

**Verify in DB:**

- ✅ New `project_versions` row with `parent_version_id` pointing at the
  previous version.
- ✅ `projects.current_version_id` updated to the new version.

**Edge case:** ambiguous request:

```bash
baseflo refine "do the thing"
```

→ should return clarification_needed=True with the agent's question.

### Test 8 — Export

```bash
baseflo export                    # uses active project; writes to cwd
# or
baseflo export <project-id> --out ./out/
```

**Expected:**

- ✅ "✓ Exported to …" with file path + size in KB.

**Verify the tarball:**

```bash
tar -tzf baseflo-export-*.tar.gz
```

Should list:
- `README.md`
- `ir.json`
- `kpi_definitions.json`
- `ddl.sql`
- `tables/<each_ir_table>.csv` (one per IR table)
- `.env.example`

**Verify content:**

```bash
mkdir -p /tmp/extract && tar -xzf baseflo-export-*.tar.gz -C /tmp/extract
cat /tmp/extract/ddl.sql              # should be valid Postgres DDL
head /tmp/extract/tables/customers.csv  # should have header + rows (if Test 6 backfilled rows)
jq '.tables | length' /tmp/extract/ir.json  # number of tables in the IR
```

**Try re-importing the DDL** to confirm it's runnable:

```bash
createdb baseflo_reimport_test
psql baseflo_reimport_test -f /tmp/extract/ddl.sql
# expect: CREATE TABLE messages, no errors
```

### Test 9 — Webhook reception (requires ngrok)

Webhooks need a public URL. In dev, point providers at `https://<your>.ngrok.io`
and set `BASEFLO_API_BASE_URL` accordingly.

**Setup once:**

```bash
ngrok http 8000
# note the https://abc123.ngrok.io URL
```

Edit `server/.env`:

```
BASEFLO_API_BASE_URL=https://abc123.ngrok.io
```

Restart the server. Re-run `baseflo connect shopify ...` so auto-subscribe
uses the public URL.

**Test the round-trip:**

1. In Shopify admin, edit a customer's email.
2. Watch server logs — should show:

   ```
   shopify_webhook_accepted topic=customers/update ...
   webhook_dispatch_completed status=applied ...
   ```

3. Run `baseflo export` again — verify the customer's email is updated
   in the CSV.

**Without ngrok:** test only that the receive endpoint correctly
processes a synthetic webhook. The unit tests
(`tests/unit/test_connector_webhook_routes.py`) already cover this.

### Test 10 — Tenant isolation (RLS)

Critical security check.

```bash
cd server
uv run pytest tests/integration/test_auth_isolation.py -m integration -v
```

**Expected:** 6 tests pass.

The most important assertion: with `app.organization_id = A`, queries
against any tenant-scoped table return only A's rows. **If any of these
fail, security is broken — escalate immediately.**

### Test 11 — SDK integration

Make a tiny Node script `test-sdk.mjs`:

```javascript
import { BaseflowClient } from "@baseflo/sdk";
import { readFileSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";

const creds = JSON.parse(
  readFileSync(join(homedir(), ".baseflo/credentials.json"), "utf-8"),
);

const client = new BaseflowClient({
  baseUrl: creds.baseUrl,
  token: creds.sessionToken,
  activeOrg: creds.activeOrg,
});

console.log("me:", await client.auth.me());
console.log("connectors:", await client.connectors.list());
```

```bash
cd /tmp && npm init -y && npm install ../path/to/Baseflo/sdk/ts
node test-sdk.mjs
```

**Expected:**

- ✅ Both calls return typed responses, no runtime errors.
- ✅ `me` shows your `user_id` + `organization_id` + `role=owner`.
- ✅ `connectors.connectors` is an array of installed connectors.

---

## 5. Code review checklist

If you also want to read the code (vs. just black-box test), focus here:

| Path | What to look for |
|---|---|
| `server/app/auth/` | Session-cookie validation, magic-link, RBAC matrix. Does any code path bypass the resolver? |
| `server/app/services/data_plane/` | The 7 data-plane services. Each has unit tests in `tests/unit/test_*.py`. |
| `server/app/services/connector_oauth/` | Registrar persists encrypted tokens; subscriber auto-subscribes webhooks. |
| `server/app/services/connector_tokens/vault.py` | `EnvelopeCrypto` round-trips. Confirm no plaintext tokens in DB. |
| `server/app/orchestration/sagas/architect.py` | The 8-stage saga + `_finalize_data_plane` hook. |
| `server/app/connectors/` | Each connector implements `Connector` Protocol. Confirm tests exist for each. |
| `server/migrations/versions/` | 19 migrations, sequential. No hand-edits should be visible. |
| `server/app/api/v1/routes/` | Every route has typed request/response models. No raw `dict[str, Any]` in signatures. |
| `sdk/ts/src/client.ts` | Mirrors the route surface. Adding a new endpoint = update both. |
| `cli/src/commands/` | One file per command. Commander wires in `cli/src/index.ts`. |

**Things that should NOT exist** (file as bugs if you find them):

- `time.sleep(...)` in async code paths (use `await asyncio.sleep`).
- `print(...)` statements (use the structlog logger).
- `from typing import Any` *without a `# type: ignore[misc]` justification* in Pydantic schemas.
- Hardcoded model strings like `"gpt-4"` outside `app/core/config.py`.
- Plaintext API keys / secrets anywhere outside `.env`.
- SQL strings built with `f"... {user_input} ..."` (we use `quote_identifier` + bound params).

---

## 6. Database verification queries

Connect with: `psql postgresql://baseflo:baseflo@localhost:5432/baseflo`

**Auth state:**

```sql
SELECT id, email, last_login_at FROM users ORDER BY created_at DESC LIMIT 5;
SELECT id, expires_at, revoked_at FROM sessions ORDER BY created_at DESC LIMIT 5;
SELECT id, slug, plan, status FROM organizations ORDER BY created_at DESC LIMIT 5;
SELECT id, role, accepted_at FROM memberships WHERE user_id=(SELECT id FROM users WHERE email='tester@example.com');
```

**Project state:**

```sql
SELECT id, slug, deployment_mode, tenant_data_schema_name, current_version_id FROM projects;
SELECT id, version_number, jsonb_array_length(jsonb_path_query_array(schema_ir, '$.tables[*]')) AS table_count
  FROM project_versions ORDER BY created_at DESC LIMIT 5;
```

**Connector state:**

```sql
SELECT id, kind, display_name, status, config FROM connectors;
SELECT id, connector_id, octet_length(ciphertext) AS cipher_bytes, octet_length(wrapped_dek) AS dek_bytes,
       expires_at, scopes, revoked_at FROM connector_tokens;
-- ciphertext + wrapped_dek MUST be non-zero bytes (means: encrypted, not stored as plaintext)
```

**Data plane:**

```sql
SELECT id, project_id, schema_name, kind, statements_count, status, applied_at
  FROM tenant_data_applications ORDER BY applied_at DESC LIMIT 5;
SELECT entity_kind, source, source_id, canonical_id FROM entity_id_map LIMIT 20;
\dn   -- list schemas; expect a `tenant_<hex>` per project
\dt tenant_xxxxx.*   -- list tables in that schema
SELECT count(*) FROM tenant_xxxxx.customers;
```

**Webhook ingestion (after Test 9):**

```sql
SELECT actor_type, action, target_kind, created_at FROM audit_events ORDER BY created_at DESC LIMIT 10;
```

---

## 7. Known limitations — don't file as bugs

These are **deliberate alpha-scope cuts**, documented in
[`docs/31-todolist.md`](31-todolist.md) "Post-Alpha Backlog":

| Limitation | Workaround | Slated for |
|---|---|---|
| No CSV/Excel upload endpoint | Place file at server-accessible path; the connector reads from `metadata["file_path"]` | UI workstream |
| No KPI execution endpoint | Run `kpi_definitions.json` SQL yourself against the tenant schema | UI workstream |
| Web UI under construction | Use CLI/SDK for all journeys in this plan; web journeys live in a separate plan once `WEB-APP` M0/M1 lands | See [`40-features/WEB-APP.md`](40-features/WEB-APP.md) §20 |
| No auto-digest scheduler | Compose & deliver works on manual trigger only | Post-alpha |
| Refinement is destructive | Refining drops + recreates affected tables. Existing canonical rows are wiped. M2 ships non-destructive ALTER plans | M2 |
| GitHub / Microsoft sign-in | Only Google + magic link | M1 |
| AWS KMS not implemented | `AwsKmsClient` is a stub. `LocalKMSClient` works for self-host + dev | M1+ |
| API key issuance routes | Resolver validates Bearer keys but no route to mint them | When SDK/CLI need server-side issuance |
| CSRF tokens | SameSite=Lax cookie blocks the worst CSRF surface | Pre-SOC2 |
| Audit chain hashing | Audit events written; `chain_hash` deferred | M3+ |
| EU region | US-East only | When first EU customer signs |
| Soft-then-hard project deletion | Hard DELETE works; 30-day soft-delete saga deferred | When deletion requests arrive |
| End-to-end integration test (Shopify webhook → reconciler → export → digest delta) | Each piece unit-tested in isolation; chain test deferred until UI exists | UI workstream |
| Webhook delivery from providers to localhost | Use ngrok | N/A — provider limitation |
| `baseflo dev` starts compose, not the API server | Documented in command output. Run `uv run uvicorn ...` separately | Could fold in post-alpha |

---

## 8. How to report findings

For each finding, capture in a single block:

```markdown
### [B|N|C] <short description>

**Severity:** Blocker / Non-blocker / Cosmetic
**Test:** Test N — name (or "code review")

**Steps:**
1. ...
2. ...

**Expected:** (what this doc says should happen)

**Actual:** (what you observed)

**DB state if relevant:**
```sql
-- query you ran
```
```
-- output

**Server log excerpt:**
```
relevant lines from uvicorn stdout
```

**Notes:** (any hypothesis on cause; commit hash if you bisected; etc.)
```

**Severity guide:**

- **Blocker** = a documented test journey doesn't work as described, or
  a code-health gate is red, or any RLS/security test fails.
- **Non-blocker** = behavior diverges from this doc but is recoverable
  (typo in error message, SSE event ordering quirk, etc.).
- **Cosmetic** = output formatting, log noise, etc.

**Pass criteria for the alpha:** zero Blockers. Non-blockers and cosmetics
go on the issue tracker for the next sprint.

---

## Appendix A — Reset between runs

If you want a clean slate between test passes:

```bash
# Wipe DB (Postgres)
docker compose -f docker-compose.dev.yml down -v
docker compose -f docker-compose.dev.yml up -d
cd server && uv run alembic upgrade head

# Clear local credentials
rm -rf ~/.baseflo/

# Optional: re-link CLI
cd ../cli && npm run build && npm link
```

## Appendix B — Component versions a passing alpha should report

| Component | Expected count |
|---|---|
| `mypy --strict` source files | **237**, 0 issues |
| Unit tests | **766** passed |
| Integration tests | **29** collected (run with `-m integration`) |
| SDK vitest tests | **12** passed |
| Alembic migrations | **19** total, head=`0019_membership_lookup_contract` |
| API routes (under `/api/v1/...`) | health, auth.\*, orgs, projects.\*, oauth.\*, connectors.\*, conversations.\*, refinements.\*, exports.\*, share_links.\*, events, connector_webhooks.\* |
| CLI commands | **13** at top level |
| Connectors registered | **6** (csv, excel, postgres, shopify, stripe, google_sheets) |
