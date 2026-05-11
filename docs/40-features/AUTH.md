# `AUTH` — Sessions, OAuth, Roles

Status: M0–M3. Combines `AUTH-SESSION` + `AUTH-OAUTH` + `RBAC-ROLES` + (M3+) `AUTH-SSO` + `AUTH-SCIM`. Identity foundation for the entire system.

---

## 1. Overview

Authentication and authorization for human users + programmatic API keys. Lucia-style sessions for v1; OAuth (Google/GitHub/Microsoft); SSO (OIDC + SAML, M3+); SCIM provisioning (M3+); standard four-role RBAC + custom roles (M3+) + two-person approval (M4+).

Multi-tenancy is enforced through this layer: every request acquires a typed `TenantCtx` derived from the authenticated identity + organization membership; every downstream layer respects RLS scoped to that context.

## 2. High-Level Design

```
Browser / API client
        │
        ▼
┌──────────────────────┐
│ Auth Middleware      │  (FastAPI dependency)
│ - validates session  │
│ - resolves user      │
│ - resolves org via   │
│   membership         │
│ - sets RLS session   │
│   var                │
└──────────┬───────────┘
           │
           ▼
   TenantCtx propagated as
   FastAPI dependency through
   every endpoint
           │
           ▼
   Repositories enforce
   organization_id = current_setting('app.organization_id')
   via RLS policies
```

## 3. Low-Level Design

### 3.1 Module Layout

```
server/app/auth/
├── __init__.py
├── sessions.py             # Lucia-style session token issuance + validation
├── magic_link.py           # email-based passwordless flow
├── oauth/
│   ├── google.py
│   ├── github.py
│   └── microsoft.py
├── sso/                    # M3+
│   ├── oidc.py
│   ├── saml.py
│   └── scim.py
├── api_keys.py             # programmatic-access keys
├── rbac.py                 # roles + permission resolution
├── tenant_ctx.py           # TenantCtx dataclass + FastAPI dependency
├── middleware.py           # request middleware: session → TenantCtx → RLS session var
└── tests/
    ├── test_sessions.py
    ├── test_oauth.py
    ├── test_rbac.py
    └── test_tenant_isolation.py
```

### 3.2 Key Types

```python
class Role(StrEnum):
    OWNER     = "owner"      # billing, delete project, change deployment mode
    ADMIN     = "admin"      # connector mgmt, refinement, exports, team mgmt
    EDITOR    = "editor"     # read/write all data, refinement, exports
    VIEWER    = "viewer"     # read-only; can comment

class TenantCtx(BaseModel, frozen=True):
    user_id: UUID
    organization_id: UUID
    role: Role
    session_id: UUID
    request_id: str
    is_api_key: bool = False
    api_key_id: UUID | None = None

class SessionToken(BaseModel):
    id: UUID
    user_id: UUID
    expires_at: datetime
    revoked_at: datetime | None = None
```

### 3.3 Session Lifecycle

1. User signs in via magic link or OAuth.
2. Server creates `sessions` row; sets a session cookie (httpOnly, secure, sameSite=lax).
3. Every request: middleware validates session token, loads user + memberships, picks active organization (from URL, header, or default), populates `TenantCtx`.
4. `SET app.organization_id = '<uuid>'` issued on the SQLAlchemy session for the request.
5. Repositories' RLS policies enforce isolation.
6. Sign-out: marks `revoked_at` on the session.

Sessions auto-expire after 30 days idle. Refresh on each request shifts expiry forward.

### 3.4 OAuth (v1)

Google / GitHub / Microsoft via `authlib`. Callbacks land at `/api/v1/auth/callback/<provider>`; on success a session is issued. Email-confirmed identities only — providers that don't return a verified email (e.g., GitHub without verified email) prompt the user to add and verify one.

### 3.5 API Keys

`api_keys` table: name, prefix (first 8 chars displayed), argon2id hash of full secret, scopes, last_used_at, revoked_at. Scopes are coarse-grained for v1: `read:all`, `write:all`, `events:write`, `refinements:propose`. Per-table scopes deferred (M4+).

Auth flow:
- Request includes `Authorization: Bearer baseflo_<prefix>_<secret>`.
- Middleware looks up by prefix, verifies hash with argon2, populates `TenantCtx` with `is_api_key=True`.
- Audit log records actor as `api_key:<id>`.

### 3.6 RBAC

Permissions resolved per (role, action, resource_kind). Examples:
- `Owner` can do everything in their org.
- `Admin` cannot delete the org or change billing.
- `Editor` cannot manage team or revoke API keys.
- `Viewer` is read-only and cannot reveal PII.

Permission checks happen at the service layer, not in agents. Each service method is decorated:

```python
@requires_permission(Permission.REFINE_PROJECT)
async def execute_refinement(self, command, ctx: TenantCtx): ...
```

### 3.7 SSO (M3+)

OIDC and SAML 2.0 configured per organization. Settings UI surfaces an IdP form (test mode → flip to required). SCIM endpoint provisions/deprovisions users from the IdP.

When SSO is enabled, password and OAuth sign-ins are disabled for that org.

## 4. Design Patterns Applied

| Pattern | Where | Why |
|---|---|---|
| **Middleware** | Auth middleware sets `TenantCtx` once per request | Cross-cutting; never leaks into business logic. |
| **Strategy** | OAuth providers; SSO protocols | Provider-agnostic abstraction. |
| **Decorator** | `@requires_permission(...)` | Cross-cutting RBAC enforcement. |
| **Singleton** | `KMS` client for password / token hashing | One shared instance per process. |

## 5. Test Plan

- Session lifecycle: issue → refresh → revoke → expired.
- Magic link: link issued, used, single-use.
- OAuth: full flow against provider sandbox.
- RBAC: each role × action matrix; unauthorized actions return 403.
- Tenant isolation: cross-tenant query returns nothing (RLS enforced); cross-tenant write attempts raise.
- API keys: hash verification; revoked keys denied; scopes enforced.
- SSO (M3+): OIDC + SAML round-trip against test IdP.
- Coverage: 92% (security-critical).

## 6. Error Codes

| Code | Condition | Recovery |
|---|---|---|
| `BF-AUTH-001` | Invalid session | 401; client redirects to sign-in. |
| `BF-AUTH-002` | Insufficient role | 403; client surfaces "ask your admin." |
| `BF-AUTH-003` | API key revoked or invalid | 401; client refreshes credentials. |
| `BF-AUTH-004` | OAuth callback failed | Redirect to sign-in with error message. |
| `BF-AUTH-005` | SSO required for this org but other method used | 403; redirect to SSO. |
| `BF-AUTH-006` | Magic link expired or used | 410; request new link. |

## 7. Dependencies

[`04-database-schema.md`](../04-database-schema.md) — `users`, `sessions`, `oauth_identities`, `memberships`, `api_keys` tables.

## 8. Milestone

- **M0**: sessions + magic link + Google OAuth; RBAC with 4 standard roles; tenant isolation via RLS.
- **M1**: GitHub + Microsoft OAuth; API keys.
- **M3**: OIDC SSO (Google Workspace, Microsoft Entra ID); SCIM provisioning.
- **M4**: SAML 2.0 (Okta, OneLogin); custom roles; two-person approval for destructive ops.
