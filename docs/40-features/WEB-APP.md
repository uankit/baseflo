# `WEB-APP` — Hosted Web Application (Meta-App Shell)

Status: M0–M3, locked **2026-05-07** by `00-decisions.md` §10. Production grade. Combines `WEB-SHELL` + `WEB-AUTH` + `WEB-ONBOARD` + `WEB-PROJECT` + `WEB-CONNECT` + `WEB-SAGA` + `WEB-WORKSPACE` + `WEB-REFINE` + `WEB-EXPORT` + `WEB-SHARE` + `WEB-SETTINGS` + `WEB-DESIGN-SYSTEM` + `WEB-ERROR-SYSTEM` + `WEB-A11Y`. The single source of truth for the hosted web client at `app.baseflo.com`.

This document defers to `00-decisions.md` for the locked decisions, `01-architecture.md` §3.7 for the admin-generation contract, `02-tech-stack.md` for the frontend stack, `04-database-schema.md` for entity shape, `05-coding-rules.md` for coding rules, `40-features/ADMIN-GEN.md` for the schema-driven admin tabs nested inside the workspace, `40-features/AUTH.md` for backend session contract, and `20-gtm.md` for ICP and demo framing.

---

## 1. Overview

The hosted web app is the surface where a user goes from *"I have a business / I have a frontend"* to *"my workspace is live and I can see + act on my data."* It is the meta-app shell that:

- Authenticates and routes the user.
- Onboards them into an organization, workspace, and first project.
- Connects their data sources.
- Streams the live agent saga that builds their unified schema.
- Renders the resulting workspace — schema-driven admin tabs (delegated to `ADMIN-GEN`), behavioral analytics (`ANA-*`), refinement panel (`REF-PANEL`), exports (`SEC-EXPORT`), share links (`ADMIN-SHARE`).
- Manages settings — team, billing, audit, API keys, custom domain, deployment mode, SSO.

It is **not**:

- The auto-generated per-tenant admin pane. That's `ADMIN-GEN`, *contained inside* this shell.
- A code generator. Per `00-decisions.md` §2.
- A chat-only agent UI. Per [`06-design.md`](../06-design.md) §4.8 visual non-goals: avoid generic AI chat aesthetic, blob/orb decoration, glassmorphism, AI gradients.
- A marketing site. `baseflo.com` is a separate static deployment (`WEB-MARKETING`, M2).

**Who calls it:** end-users (ICP-A indie devs, ICP-B SMB owners) via browser; the founder during screen-shared onboarding; ICP-D customers reviewing BYO-DB / Self-Host options. **Who does NOT call it:** AI agents (use `MCP-SERVER`); programmatic integrations (use `SDK-TS` + `API-REST`); the CLI (uses the same REST API directly).

**Why this is industry-grade-or-it-doesn't-ship:** Per `00-decisions.md` §9, the alpha cut to CLI/SDK was reversed because the canonical 90-second demo (`20-gtm.md` §5) and the SMB drop-spreadsheet wedge cannot be sold without a real workspace. ICP-A devs also expect a hosted dashboard. So this app is on the demo path *and* the activation path *and* the retention path — every screen is on a critical journey.

---

## 2. High-Level Design

### 2.1 Where the web app sits

```
   ┌────────────────────────────────────────────────────────────────────┐
   │                 USER (browser, signed in to app.baseflo.com)        │
   └────────────────────────────┬───────────────────────────────────────┘
                                │ HTTPS + WSS
                                ▼
   ┌────────────────────────────────────────────────────────────────────┐
   │              CLOUDFLARE / VERCEL EDGE  (`app.baseflo.com`)          │
   │  - serves Vite-built static bundle                                  │
   │  - proxies `/api/v1/*` and `/sse/*` to FastAPI                      │
   └────────────────────────────┬───────────────────────────────────────┘
                                │
                                ▼
   ┌────────────────────────────────────────────────────────────────────┐
   │                       FASTAPI SERVER                                │
   │  /api/v1/auth        /api/v1/orgs        /api/v1/projects           │
   │  /api/v1/connectors  /api/v1/sagas       /api/v1/refinements        │
   │  /api/v1/exports     /api/v1/share       /api/v1/admin-ui-spec      │
   │  /api/v1/data        /api/v1/kpis        /api/v1/audit              │
   │  /sse/conversations/{id}    (Server-Sent Events for saga + refine)  │
   └────────────────────────────┬───────────────────────────────────────┘
                                │
                                ▼
                   Postgres (control plane)
                   Redis (arq jobs)
                   KMS (per-tenant keys)
                   Tenant data plane (4 runners)
```

The frontend is a single-page application (SPA). Vite-built static assets, served from CDN, talk to the same-origin REST API and SSE stream. No SSR; no Next.js. Per `02-tech-stack.md` row "Frontend framework", the rationale is: app-first, not SEO-first; SSE-heavy; vite is faster + desktop-wrapper friendly (Tauri v2 in M5+).

### 2.2 Top-level package layout

```
client/                                        ← currently empty; this scaffold ships in M0
├── apps/
│   └── web/
│       ├── public/
│       ├── src/
│       │   ├── main.tsx
│       │   ├── providers.tsx                   ← TanStack Query, Router, theme, error boundary
│       │   ├── router.tsx                      ← TanStack Router root
│       │   ├── routes/                         ← file-based routes (see §4)
│       │   ├── layouts/                        ← AppShell, AuthShell, WorkspaceShell, ShareShell, SettingsShell
│       │   ├── features/                       ← one folder per feature (see §3.2)
│       │   ├── shared/                         ← cross-feature hooks, utils, constants
│       │   └── styles/                         ← tokens.css, base.css, print.css
│       ├── tests/
│       │   ├── unit/
│       │   ├── component/
│       │   └── e2e/                            ← Playwright
│       ├── index.html
│       ├── vite.config.ts
│       ├── tsconfig.json
│       └── package.json
├── packages/
│   ├── ui/                                     ← @baseflo/ui (Radix wraps, primitives, charts, tables)
│   ├── api-client/                             ← @baseflo/api-client (gateway + transports)
│   ├── error-system/                           ← @baseflo/error-system (BF-WEB-NNN registry, normalizer)
│   ├── contracts/                              ← @baseflo/contracts (types generated from SchemaIR + REST)
│   ├── sdk/                                    ← @baseflo/sdk (public dev SDK; reused inside web app)
│   └── config/                                 ← shared eslint, tsconfig, prettier, tailwind preset
├── package.json
├── pnpm-workspace.yaml
└── turbo.json
```

The dependency-direction boundary (UI → feature hook → feature service → client gateway → transport adapter) is locked in [`06-design.md`](../06-design.md) §6 and made enforceable by ESLint import-restriction rules: route files cannot import transport modules; UI components cannot import gateways.

### 2.3 Feature folder shape (canonical)

```
features/<feature-name>/
├── services/                                   ← business / workflow logic (no React)
│   ├── <feature>Service.ts
│   └── <feature>Service.test.ts
├── hooks/                                      ← React state composers
│   ├── use<Feature>.ts
│   └── use<Feature>.test.ts
├── components/                                 ← screens + sub-components
│   ├── <Feature>View.tsx
│   ├── <Feature>View.test.tsx
│   └── <SubComponent>.tsx
├── fixtures/                                   ← typed mock data for tests + Storybook
│   └── <feature>.fixtures.ts
└── index.ts                                    ← public exports
```

TDD-first means the test file is committed *before* the implementation file in every feature folder. Code review enforces this via commit-time hook (CI) and human gate. See `05-coding-rules.md` §1.1.

---

## 3. Low-Level Design

### 3.1 Stack confirmation (no additions to `02-tech-stack.md`)

| Concern | Choice | Rationale (defers to `02-tech-stack.md`) |
|---|---|---|
| Framework | React 18 + Vite | Locked. |
| Types | TypeScript strict | Locked. |
| Routing | TanStack Router (file-based) | Typed routes; replaces hand-maintained route registry. |
| Server state | TanStack Query | Locked. SSE complementary. |
| Local state | Zustand | Locked. Per-feature stores; no global app store for server data. |
| Forms | react-hook-form + Zod resolver | react-hook-form is lightweight; Zod is already locked for validation. |
| UI primitives | Radix UI | Locked; accessible by default. |
| Styling | Tailwind + CSS variables (`@baseflo/ui` preset) | Locked. Tokens drive theme; classes drive layout. |
| Tables | TanStack Table + TanStack Virtual | Locked. |
| Charts | Recharts | Locked. Vega-Lite re-evaluated M2. |
| Code display | Shiki (read-only); Monaco only when editing | Locked. |
| Icons | lucide-react | Locked. |
| Validation | Zod | Locked. SSE payload + REST response validation. |
| Tests (unit/component) | Vitest + Testing Library | Locked. |
| Tests (e2e) | Playwright | Locked. |
| Tests (load) | k6 | Locked; runs against API not UI. |

If a feature wants something not in this list, the answer is no until `02-tech-stack.md` updates with `00-decisions.md` Changelog backing.

### 3.2 Module / feature inventory

Each row = one folder under `apps/web/src/features/` and one sub-section in this document.

| Feature folder | Sub-feature ID | Purpose |
|---|---|---|
| `auth/` | `WEB-AUTH` | Sign-in, sign-up, magic-link, OAuth, password reset, session refresh, sign-out. |
| `onboarding/` | `WEB-ONBOARD` | First-run wizard: org create / join, deployment-mode pick, first project. |
| `org-dashboard/` | `WEB-PROJECT` | Recent projects, daily digest preview, quick-start, onboarding checklist. |
| `project-create/` | `WEB-PROJECT` | "Describe your business" prompt + ICP-B `/start` lane. |
| `connectors/` | `WEB-CONNECT` | Connector hub: install, OAuth dance, API-key entry, file upload, status, reconnect, revoke. |
| `saga-viewer/` | `WEB-SAGA` | Live SSE stream of generation sagas; replay; clarification gate; workspace.ready CTA. |
| `workspace/` | `WEB-WORKSPACE` | Top bar, sidebar (ADMIN-GEN-driven), main pane router, right refine rail, version selector. |
| `admin-tabs/` | embedded `ADMIN-GEN` | Schema-driven list/detail/edit tabs; this folder is a thin host that renders `AdminUISpec`. |
| `analytics/` | embedded `ANA-*` | Behavioral analytics tab: funnels, cohorts, geo, top-N, lapsing, anomaly. |
| `digest-preview/` | embedded `DIG-COMPOSE` | Today's digest preview at top of overview tab. |
| `refine-panel/` | `WEB-REFINE` | Right-rail composer; plan preview; apply; version-switch. |
| `versions/` | embedded `ADMIN-VERSIONS` | History list, side-by-side compare, rollback. |
| `exports/` | `WEB-EXPORT` | Format picker, job progress, download history. |
| `share-links/` | `WEB-SHARE` | Create/manage links from inside workspace. |
| `share-page/` | `WEB-SHARE` | Public read-only view at `/s/<token>`. |
| `settings/` | `WEB-SETTINGS` | Org, team, billing, audit, API keys, custom domain, deployment mode, SSO. |
| `system/` | `WEB-SHELL` + `WEB-ERROR-SYSTEM` | App shell, error boundary, status bar, global toasts, command palette. |

### 3.3 URL contract

```
PUBLIC
  /                                     → if signed-in, redirect to last org dashboard; else /sign-in
  /sign-in                              → email/password + magic-link + OAuth buttons
  /sign-up                              → same form, "create account" CTA
  /auth/magic-link                      → ?token=… consumes; on success → /welcome or last-visited
  /auth/callback/{provider}             → OAuth callback handler
  /auth/forgot                          → email entry
  /auth/reset                           → ?token=… new password form
  /s/{share-token}                      → public read-only share page
  /not-found                            → 404
  /unsupported                          → "optimized for desktop" gate

AUTHENTICATED
  /welcome                              → first-run org create / join wizard
  /o/{org-slug}                         → org dashboard (project list)
  /o/{org-slug}/start                   → ICP-B lane: "Tell us about your business" → connect → saga
  /o/{org-slug}/projects/new            → ICP-A lane: prompt + advanced controls
  /o/{org-slug}/p/{project-slug}        → redirect to current_version_id
  /o/{org-slug}/p/{project-slug}/v/{version-id}                  → workspace overview
  /o/{org-slug}/p/{project-slug}/v/{version-id}/{tab-id}         → workspace tab (ADMIN-GEN-driven)
  /o/{org-slug}/p/{project-slug}/v/{version-id}/connectors       → connector hub for this project
  /o/{org-slug}/p/{project-slug}/v/{version-id}/analytics         → analytics
  /o/{org-slug}/p/{project-slug}/v/{version-id}/versions          → version history
  /o/{org-slug}/p/{project-slug}/v/{version-id}/exports           → export center
  /o/{org-slug}/p/{project-slug}/v/{version-id}/share             → manage share links
  /o/{org-slug}/p/{project-slug}/v/{version-id}/audit             → audit log filtered to project
  /o/{org-slug}/p/{project-slug}/saga/{conversation-id}           → live or replayed saga viewer
  /o/{org-slug}/settings/{org|team|billing|api-keys|domain|deployment|sso|audit}
                                        → settings tabs

CALLBACKS / WEBHOOK FRONTENDS
  /oauth/{connector}/callback           → connector OAuth completion (server returns; client polls/refreshes)
```

URL design rules:

- Slug owns identity (`{org-slug}`, `{project-slug}`); UUIDs only where slugs are user-hostile (`{version-id}`, `{conversation-id}`).
- Tab IDs in workspace come from `AdminUISpec.tabs[i].id` (`ADMIN-GEN`-derived); the URL route segment is the tab slug. Unknown tab → 404, never silent fallback.
- Query strings own ephemeral UI state only (`?refine=open`, `?compare=v3`); never own primary navigation.
- Trailing slashes: never. Redirected to non-slash.
- Query params used by the saga viewer: `?seq=<int>` to resume from a specific SSE sequence number.

### 3.4 URL state, route loaders, and data dependencies

TanStack Router supports typed loaders. Every route defines its `loader` (data fetched before render) and its `params` schema. Loaders return promises that TanStack Query keys can subscribe to.

Example, schematic:

```ts
// routes/o/$orgSlug/p/$projectSlug/v/$versionId/index.tsx
export const Route = createFileRoute('/o/$orgSlug/p/$projectSlug/v/$versionId/')({
  parseParams: (raw) => ({
    orgSlug: z.string().parse(raw.orgSlug),
    projectSlug: z.string().parse(raw.projectSlug),
    versionId: z.string().uuid().parse(raw.versionId),
  }),
  loader: async ({ params, context }) => {
    return Promise.all([
      context.gateway.projects.getBySlug(params.orgSlug, params.projectSlug),
      context.gateway.workspace.getAdminUISpec(params.versionId),
      context.gateway.workspace.getOverviewSummary(params.versionId),
    ]);
  },
  component: WorkspaceOverview,
  errorComponent: WorkspaceLoadError,
  pendingComponent: WorkspaceLoadingSkeleton,
});
```

Three benefits: predictable loading skeletons, typed error boundaries, no waterfall fetches inside components.

### 3.5 Key types (frontend contracts)

These types live in `@baseflo/contracts` and are generated from the FastAPI OpenAPI schema where possible. Hand-written only for client-only concerns (`UIState`, `LayoutKind`).

```ts
// @baseflo/contracts/auth.ts
export interface SessionDTO {
  user: { id: UUID; email: string; displayName: string | null; emailVerifiedAt: string | null };
  organizations: OrgMembershipDTO[];
  activeOrgId: UUID | null;
  expiresAt: string;
}

export interface OrgMembershipDTO {
  organizationId: UUID;
  organizationSlug: string;
  organizationName: string;
  role: "owner" | "admin" | "editor" | "viewer";
  plan: "free" | "hobby" | "pro" | "business" | "enterprise";
  region: "us-east-1" | "eu-west-1";
}

// @baseflo/contracts/project.ts
export interface ProjectSummaryDTO {
  id: UUID;
  slug: string;
  name: string;
  description: string | null;
  deploymentMode: "hosted" | "byo_db" | "self_host" | "local_dev";
  currentVersionId: UUID | null;
  createdAt: string;
  updatedAt: string;
  status: "ready" | "generating" | "needs_clarification" | "failed" | "no_connectors";
}

// @baseflo/contracts/saga.ts
export type SagaEventKind =
  | "conversation.message"
  | "clarification.required"
  | "clarification.answered"
  | "agent.start"
  | "agent.complete"
  | "validation.passed"
  | "validation.warning"
  | "validation.failed"
  | "artifact.ready"
  | "workspace.ready"
  | "error.recoverable"
  | "error.terminal"
  | "refinement.start"
  | "refinement.complete"
  | "heartbeat";

export interface SagaEvent {
  conversationId: UUID;
  sequence: number;
  kind: SagaEventKind;
  createdAt: string;
  payload: SagaEventPayload;        // discriminated union by kind
}

// @baseflo/contracts/admin.ts is generated from server `AdminUISpec` (see ADMIN-GEN.md §3.2)
export type { AdminUISpec, AdminTab, ListViewSpec, DetailViewSpec, WidgetKind } from "./generated/admin";
```

The `SagaEventPayload` union is exhaustive; adding a kind in `04-database-schema.md` §4.13 is a contract break that bumps `@baseflo/contracts` major version, regenerates types, and forces every consumer to handle the new case.

### 3.6 Gateway and transport boundary

The boundary from [`06-design.md`](../06-design.md) §6 holds:

```
React component
   └─ feature hook (TanStack Query / Zustand)
       └─ feature service (workflow logic)
           └─ client gateway (@baseflo/api-client)
               └─ transport adapter (REST | SSE | placeholder for tests)
```

`@baseflo/api-client/src/gateway.ts` defines named domain operations. Implementations dispatch to `restTransport.ts`, `sseTransport.ts`, or `placeholderTransport.ts` (used in tests). UI never imports a transport module directly; `eslint.config.js` forbids it.

Minimum gateway surface (locked in M0):

```ts
gateway.auth.signIn(email, password): Promise<SessionDTO>
gateway.auth.signInMagicLink(email): Promise<{ ok: true }>
gateway.auth.consumeMagicLink(token): Promise<SessionDTO>
gateway.auth.signInOAuth(provider): Promise<{ redirectUrl: string; state: string }>
gateway.auth.signOut(): Promise<void>
gateway.auth.session(): Promise<SessionDTO>
gateway.auth.refreshSession(): Promise<SessionDTO>

gateway.orgs.create(req): Promise<OrgDTO>
gateway.orgs.list(): Promise<OrgDTO[]>
gateway.orgs.get(slug): Promise<OrgDTO>
gateway.orgs.update(slug, patch): Promise<OrgDTO>
gateway.orgs.invite(slug, email, role): Promise<MembershipDTO>

gateway.projects.create(orgSlug, req): Promise<ProjectSummaryDTO>
gateway.projects.list(orgSlug): Promise<ProjectSummaryDTO[]>
gateway.projects.getBySlug(orgSlug, projectSlug): Promise<ProjectDetailDTO>
gateway.projects.archive(projectId): Promise<void>

gateway.connectors.list(projectId): Promise<ConnectorDTO[]>
gateway.connectors.startInstall(projectId, kind): Promise<{ flowId: UUID; redirectUrl?: string; nextStep: ConnectorInstallStep }>
gateway.connectors.completeInstall(flowId, payload): Promise<ConnectorDTO>
gateway.connectors.revoke(connectorId): Promise<void>
gateway.connectors.reconnect(connectorId): Promise<{ redirectUrl?: string }>
gateway.connectors.health(connectorId): Promise<HealthDTO>

gateway.sagas.start(projectId, prompt): Promise<{ conversationId: UUID; jobId: UUID }>
gateway.sagas.subscribe(conversationId, fromSeq?): EventSource
gateway.sagas.replay(conversationId, fromSeq, toSeq?): Promise<SagaEvent[]>
gateway.sagas.answerClarification(conversationId, answer): Promise<void>

gateway.workspace.getAdminUISpec(versionId): Promise<AdminUISpec>
gateway.workspace.getOverviewSummary(versionId): Promise<OverviewDTO>
gateway.workspace.listEntities(versionId, table, query): Promise<EntityListDTO>
gateway.workspace.getEntity(versionId, table, id): Promise<EntityDTO>
gateway.workspace.updateEntity(versionId, table, id, patch): Promise<EntityDTO>
gateway.workspace.revealPII(versionId, table, id, column): Promise<{ value: string; expiresAt: string }>

gateway.refinements.propose(projectId, intentText): Promise<RefinementProposalDTO>
gateway.refinements.apply(refinementId): Promise<{ newVersionId: UUID }>
gateway.refinements.discard(refinementId): Promise<void>
gateway.refinements.list(projectId): Promise<RefinementDTO[]>

gateway.exports.request(versionId, format): Promise<ExportDTO>
gateway.exports.poll(exportId): Promise<ExportDTO>

gateway.shareLinks.create(versionId, opts): Promise<ShareLinkDTO>
gateway.shareLinks.list(projectId): Promise<ShareLinkDTO[]>
gateway.shareLinks.revoke(shareLinkId): Promise<void>
gateway.shareLinks.publicGet(token): Promise<PublicShareDTO>

gateway.audit.list(orgSlug, query): Promise<AuditPage>
gateway.apiKeys.list(orgSlug): Promise<ApiKeyDTO[]>
gateway.apiKeys.create(orgSlug, req): Promise<{ key: ApiKeyDTO; secret: string }>
gateway.apiKeys.revoke(orgSlug, id): Promise<void>

gateway.billing.subscription(orgSlug): Promise<BillingDTO>
gateway.billing.portalLink(orgSlug): Promise<{ url: string }>
```

Adding methods is one-line plus type generation; adding a transport (e.g., WebSocket) is one new file under `transports/` plus dispatching in `gateway.ts`.

---

## 4. Information Architecture

### 4.1 Sitemap (top-level mental model)

```
app.baseflo.com
├── (Public)
│   ├── /sign-in, /sign-up, /auth/*            → identity
│   ├── /s/{share-token}                       → public share page
│   └── /unsupported, /not-found               → fallbacks
│
├── (Authenticated, no org context)
│   └── /welcome                               → first-run wizard
│
├── /o/{org-slug}                              → ORG SHELL
│   ├── /                                       → org dashboard (project list, digest, onboarding ✓)
│   ├── /start                                  → ICP-B onboarding lane
│   ├── /projects/new                           → ICP-A onboarding lane
│   ├── /p/{project-slug}/v/{version-id}        → WORKSPACE SHELL
│   │   ├── (overview)                          → KPI strip, digest, recent activity
│   │   ├── /{adminTab}                         → ADMIN-GEN-driven tabs (Customers, Orders, …)
│   │   ├── /connectors                         → connector hub for this project
│   │   ├── /analytics                          → funnels, cohorts, geo, top-N, lapsing
│   │   ├── /versions                           → history, compare, rollback
│   │   ├── /exports                            → export center
│   │   ├── /share                              → manage share links
│   │   └── /audit                              → project-scoped audit log
│   ├── /p/{project-slug}/saga/{conversation-id}
│   │                                           → SAGA SHELL (full-bleed live build)
│   └── /settings/{org|team|billing|...}        → SETTINGS SHELL
│
└── (Embedded by ICP-B-onboarding lane only — not a separate route)
    /o/{org-slug}/start emits a saga-shell experience inline.
```

Five shells exist: **AppShell** (top bar + content), **AuthShell** (centered card, no nav), **WorkspaceShell** (top bar + side nav + main + right rail), **SagaShell** (full-bleed stage rail), **ShareShell** (top bar minimal + content), **SettingsShell** (top bar + side nav + content). Six total counting the share-page minimal layout.

### 4.2 Navigation hierarchy

**Top bar** (always visible when authenticated):

```
[Baseflo wordmark]  [Org switcher ▾]  [Project switcher ▾ — only in workspace] · · ·  [Help] [User menu ▾]
```

- Org switcher pulls from `gateway.orgs.list()`. Viewer/Editor see only their org; multi-org users see all.
- Project switcher visible only inside a workspace. Recent + search.
- Help opens command palette (cmd-K) seeded with help search + actions.
- User menu: profile, sign-out, theme toggle.

**Workspace side nav** (left rail):

```
GENERATED FROM AdminUISpec  (delegated to ADMIN-GEN — see ADMIN-GEN.md §3.3)
  • Overview
  • <reconciled entity tab 1>           — e.g., "Customers"
  • <reconciled entity tab 2>           — e.g., "Orders"
  • …
  • <unreconciled top-level tab N>

STATIC (every workspace)
  • Connectors
  • Analytics
  • Versions
  • Exports
  • Share
  • Audit

FOOTER
  • Settings (link to org settings; not a workspace tab)
```

The static section never depends on the schema; the generated section is whatever `ADMIN-GEN` produces for the current `version-id`. Empty workspaces (no connectors, no version) show only static items + a "Get started" hero in the main pane.

**Workspace right rail** (refine panel, collapsible):

- Composer at bottom.
- Plan preview when a refinement proposal is pending.
- "What changed" mini-feed scrolls upward from the latest refinement.

### 4.3 IA principles

1. **One thing per screen.** No mega-pages. The workspace's overview is the only multi-purpose screen, and even it limits itself to KPI strip + digest + activity + onboarding checklist.
2. **No blank tabs.** A tab without content shows a typed empty state with the next action — never an empty grid.
3. **Stable nav order.** Tab order changes only on schema refinement; never on hover or filter.
4. **The user is always one click from their data.** No more than two clicks from any screen to a Customer detail or any other reconciled entity.
5. **Settings is its own shell.** Not nested in workspace; its own URL space; back button returns to workspace.

---

## 5. User Flows

Each flow names: trigger, success criteria, screens visited, gateways called, error paths. Order matches likely usage frequency for v1.

### 5.1 Sign-in (returning user)

Trigger: user visits `/` while logged out, or session expires.

```
[/sign-in]
  • Email
  • Password (optional — magic-link by default)
  • OR "Sign in with Google" / GitHub / Microsoft
  • Submit
       ↓
  gateway.auth.signIn(email, password) | gateway.auth.signInMagicLink(email)
       ↓
  Success: 200 + Set-Cookie session
       ↓
  Redirect to:
    - /welcome              if 0 organizations
    - /o/{lastVisited}      if remembered
    - /o/{firstOrg}         otherwise
       ↓
  TanStack Query cache hydrated with SessionDTO
```

Error paths:
- Invalid credentials → inline error using `BF-AUTH-001` copy.
- Magic-link sent but never clicked → expires after 15 min, `BF-AUTH-006`.
- OAuth provider rejection → return to `/sign-in?error=BF-AUTH-004` with banner.

### 5.2 First-run onboarding (`/welcome`)

Trigger: signed-in user with `organizations.length === 0`.

Three-step wizard, single-page progress:

```
Step 1 — Create your organization
  • Name (auto-derives slug; user can edit)
  • Region: us-east-1 (default), eu-west-1 (greyed if alpha=false)
  • Plan: Free Starter (default), see plans link
       ↓
  POST /api/v1/orgs

Step 2 — Choose deployment mode
  ╭────────── Hosted Cloud ──────────╮  ←  default; recommended
  │ "Your data lives in our managed   │
  │  Postgres, encrypted with your    │
  │  own KMS key."                    │
  ╰───────────────────────────────────╯
  ╭──────── Bring Your Own DB ────────╮  ←  Pro+ only (greyed otherwise with link to plans)
  │ "Connect your own Postgres        │
  │ (Neon, Supabase, RDS). Engine     │
  │ on us; data on you."              │
  ╰───────────────────────────────────╯
  ╭───────── Self-Host Docker ────────╮  ←  Business+ only; routes to download page
  │ "Download a Docker image. Engine  │
  │ + data on your infra."            │
  ╰───────────────────────────────────╯
       ↓
  Choice persisted on the org's first project (deployment_mode); future projects can override.

Step 3 — Pick your path
  ╭──── I'm building an app ────╮      ╭──── I run a business ────╮
  │ "I want a backend, APIs,    │      │ "Connect Stripe, Sheets,  │
  │  SDKs, CLI."                │      │  Excel and see one view." │
  ╰─────────────────────────────╯      ╰───────────────────────────╯
       ↓                                          ↓
  /o/{org}/projects/new                  /o/{org}/start
```

Success: org created, `activeOrgId` set, deployment mode noted, route handed off to ICP-A or ICP-B path. Persisted to `audit_events` (`auth.first_org_created`).

### 5.3 ICP-A flow — "I'm building an app"

Trigger: `/o/{org}/projects/new`.

```
Screen: project create
  • Project name + slug
  • Description (single sentence — feeds the agent saga)
  • Advanced (collapsed): row-count budget, dialect (Postgres alpha), include-dashboard, include-simulation defaults
  • CTA: Build my workspace
       ↓
  gateway.projects.create(...) returns ProjectSummaryDTO
       ↓
  Redirect to /o/{org}/p/{slug}/connectors
       ↓
  Screen: connector hub (empty state)
    "Add your first source"
    Cards: Postgres, CSV upload, Google Sheets, Shopify, Stripe, Mailchimp
      ↓ user picks Postgres
    Modal: paste connection string, test, save
      → POST /api/v1/connectors/install
      → ConnectorDTO returned with status=connected
      ↓
    User can repeat or click "I'm done — build my workspace"
       ↓
  gateway.sagas.start(projectId, prompt=description)
       ↓
  Redirect to /o/{org}/p/{slug}/saga/{conversationId}
       ↓
  Saga Shell streams events; on workspace.ready → CTA "Open workspace" → /o/{org}/p/{slug}/v/{versionId}
```

Default copy on the saga shell explicitly references the SDK + CLI in a side note: *"Already have a frontend? Once your workspace is ready, paste two lines into Cursor — see `Help → CLI quickstart`."*

### 5.4 ICP-B flow — "I run a business" (`/o/{org}/start`)

Trigger: `/o/{org}/start` selected from welcome, or sidebar in empty org.

```
Screen: business intake (single page; mirrors gtm.md §5 demo)
  Field 1: "What kind of business is this?"
    Free text + examples chips (yoga studio, coffee shop, agency, online store, salon, …)
  Field 2: "What do you want to see in one place?"
    Default examples: customers, bookings, payments, classes, products, orders
  Field 3: "Drop or connect your sources"
    Drag-drop zone for CSV/Excel
    Connector buttons row: Stripe, Mailchimp, Sheets, Shopify, Notion, Postgres
    Each shows live row counts after connect ("Found 247 bookings, 1,243 contacts, 89 charges")
  CTA: Build my workspace (greyed until at least one source connected)
       ↓
  Internally: creates project (auto slug from business name), runs same connector install flow as ICP-A
       ↓
  gateway.sagas.start(...) and route to saga shell
       ↓
  Saga shell shows business-friendly stage labels:
    "Reading your sources..."   (introspection)
    "Understanding customers..."  (column classification + entity reconciliation)
    "Resolving relationships..." (cardinality + constraints)
    "Designing your workspace..." (physical schema)
    "Setting up analytics..."    (KPI planner)
    "Ready"                       (workspace.ready)
       ↓
  Workspace Shell loads, lands on Overview tab; first highlight is "1,247 unique customers (resolved 488 duplicates)" — the magic-moment metric from `20-gtm.md` §5 beat 4.
```

Error path: if introspection fails (e.g., Stripe key invalid), inline reconnect — no full-page error.

### 5.5 Connector install (deep dive)

Triggered from connector hub or from intake screens. Three sub-flows:

**5.5.1 OAuth (Google Sheets, Shopify, Stripe-OAuth, Notion):**

```
[Connectors] → click [Add Sheets] →
  POST /api/v1/connectors/install/start { kind: "sheets" }
    → 200 { redirectUrl, flowId, state }
  Browser navigates to redirectUrl (Google consent)
  User grants → Google → /api/v1/oauth/callback/sheets?code=…&state=…
  Server exchanges, persists encrypted token, returns ConnectorDTO
  Server redirects to /o/{org}/p/{slug}/connectors?installed=<id>
  Client highlights the new card with toast "Sheets connected. Found 12 sheets, 4,872 rows."
```

**5.5.2 API key (Stripe-via-key, Mailchimp):**

```
[Add Stripe] → modal:
  • Test mode toggle (default: off)
  • API key input (masked)
  • Test connection button
       ↓
  POST /api/v1/connectors/install/start { kind: "stripe", credentials: { api_key: "...", test_mode: false } }
       → ConnectorDTO with status=connected
  Card slides in.
```

**5.5.3 File upload (CSV, Excel):**

```
[Add CSV] → drag-drop or file picker
  Multi-file accepted
  Per-file progress + introspect summary (table name suggestion, row count, column types)
  User can rename table or set row sampling
       ↓
  POST /api/v1/connectors/install (multipart)
       → ConnectorDTO + sample preview rendered immediately in modal
```

**Common after install:** the connectors hub re-renders with the new card. Status badge: connected / error / revoked / expired. Last sync timestamp. Reconnect button when expired.

**Failure paths use connector-specific codes:** `BF-CONN-001` (unknown connector), `BF-CONN-STRIPE-002` (key rejected), `BF-CONN-OAUTH-003` (callback state mismatch). Frontend shows the registered copy (see §16).

### 5.6 Saga viewer (`/o/{org}/p/{slug}/saga/{conversationId}`)

Full-bleed shell. Three regions:

```
┌─────────────────────────────────────────────────────────────────────────┐
│ Top bar: project title · saga status pill · cancel button              │
├─────────────────────┬──────────────────────────┬────────────────────────┤
│ STAGE RAIL          │ CURRENT STAGE DETAIL     │ EMERGING ARTIFACTS     │
│ (left)              │ (center)                 │ (right)                │
│                     │                          │                        │
│ ● Reading sources   │ ColumnClassifier         │ ┌─ Customer ─┐         │
│ ● Understanding…    │   3 columns/sec, 47 done │ │ id (UUID)  │         │
│ ◐ Resolving rels    │   token usage: 12.4k in  │ │ email (PII)│         │
│ ○ Designing schema  │   Output: SemanticType   │ │ name       │         │
│ ○ Setting up KPIs   │   per column             │ └────────────┘         │
│                     │                          │ Orders preview…        │
└─────────────────────┴──────────────────────────┴────────────────────────┘
```

Event handling (see `04-database-schema.md` §4.13 + §3.5 above):

| Event | UI effect |
|---|---|
| `agent.start` | Stage rail row pulses; stage detail shows agent name + tier + start time. |
| `agent.complete` | Stage rail row marked done; detail updates with tokens + duration; stage advances. |
| `validation.passed` | Validation chip on the artifact preview turns green. |
| `validation.warning` | Yellow chip, expandable details panel ("we assumed X — refine if wrong"). |
| `validation.failed` | Red chip + "Repairing" inline message; manager re-runs the indicated specialist (one repair attempt visible to user; deeper repair internalized). |
| `clarification.required` | Modal interrupts: at most three plain-language questions with chips + free-text. User answer routes to `gateway.sagas.answerClarification`. |
| `artifact.ready` | New emerging-artifact card slides in on the right. |
| `workspace.ready` | Full-screen success card: "Your workspace is ready" + primary CTA "Open workspace" → `/o/{org}/p/{slug}/v/{newVersionId}`. |
| `error.recoverable` | Toast with retry. |
| `error.terminal` | Replace center pane with terminal-error template (BF-WEB-021); offer "Start over with same prompt" or "Adjust + retry." |
| `heartbeat` | Connection indicator stays green; if absent for >30s → reconnect attempt; UI shows "Reconnecting…" pill. |

The saga viewer uses `gateway.sagas.subscribe` with `EventSource` (auto-reconnect). On reconnect, the client passes `?seq=<lastSeen>` and the server replays from `conversation_events` (`SSE-REPLAY` per `04-database-schema.md` §4.13).

**Cancel:** sends `POST /api/v1/sagas/{id}/cancel`. Saga marks job cancelled; does not undo committed artifacts (per saga compensator design in `50-design-patterns.md` §9).

### 5.7 Workspace shell — Overview tab

Default landing tab when entering a workspace.

```
┌──────────────────────────────────────────────────────────────────────────┐
│ Top bar (org · project · version selector · share · refine toggle)       │
├───────────┬──────────────────────────────────────────┬───────────────────┤
│ SIDE NAV  │ MAIN PANE: Overview                       │ REFINE RAIL       │
│           │                                           │ (collapsed by     │
│ Overview  │  Today's digest      ← DIG-COMPOSE preview│  default; cmd-/   │
│ Customers │  ┌─────────────────────────────────┐      │  toggles)         │
│ Orders    │  │ "1,247 unique customers (488    │      │                   │
│ Products  │  │ resolved). 12 lapsing this week"│      │                   │
│ ──────── │  └─────────────────────────────────┘      │                   │
│ Connectors│                                           │                   │
│ Analytics │  KPI strip   ← top 3 KPIs as widgets     │                   │
│ Versions  │  ┌─────┐ ┌─────┐ ┌─────┐                 │                   │
│ Exports   │  │ MRR │ │ AOV │ │ CR  │                 │                   │
│ Share     │  └─────┘ └─────┘ └─────┘                 │                   │
│ Audit     │                                           │                   │
│ ──────── │  Recent activity   ← audit feed           │                   │
│ Settings  │  • Sarah K added 2 bookings (Sheets)     │                   │
│           │  • Order #1247 refunded (Stripe)         │                   │
│           │                                           │                   │
│           │  Onboarding checklist (if incomplete)    │                   │
│           │  ☑ Connect first source                   │                   │
│           │  ☑ Build workspace                        │                   │
│           │  ☐ Invite a teammate                      │                   │
│           │  ☐ Set daily digest                       │                   │
└───────────┴──────────────────────────────────────────┴───────────────────┘
```

Empty-state variant (no connectors, no version): replace main pane with a hero card + connect-first CTA — never a blank surface.

### 5.8 Workspace shell — Entity tabs (delegated to `ADMIN-GEN`)

Each schema-driven tab renders an `AdminUISpec.tabs[i]`. Components live in `features/admin-tabs/` and are documented in `ADMIN-GEN.md` §3.2. The web app's responsibility:

- Fetch `AdminUISpec` once per version; cache in TanStack Query keyed by `versionId`.
- Hydrate the tab's `ListView` and `DetailView` per spec.
- Surface PII reveal via `gateway.workspace.revealPII` with a 30-second auto-remask timer (see `ADMIN-GEN.md` §3.5).
- Route relationship clicks: clicking a relationship cell goes to the related entity tab + record. URL transition uses `View Transition API` for spatial continuity.
- Render the multi-source attribution badge (S+M+N) when a row has contributions from >1 source.

The web app **does not hand-code** any tab. Adding a new connector and re-running the saga changes the tabs without front-end changes — that's the schema-driven UI promise from `01-architecture.md` §3.7.

### 5.9 Refinement (`WEB-REFINE`)

Triggered from any workspace screen via cmd-/ or refine rail toggle.

```
Right rail open:
  Composer at bottom
  History above (from refinements service)

User types: "Add a churn metric per product type and track repeat purchases"
       ↓
  gateway.refinements.propose(projectId, intentText)
       ↓
  Plan preview card slides in:
    "Will add 1 KPI: churn_rate_by_product_type
     Will modify 2 tables: orders (+ is_repeat column), customers (+ first_order_at)
     Will create new version v3 from v2."
  Buttons: [Apply]  [Discard]  [Edit prompt]
       ↓ Apply
  gateway.refinements.apply(refinementId)
       ↓
  Toast "Applying refinement…" + saga subset (refinement.start → refinement.complete)
       ↓
  On complete: workspace switches to new version; URL updates with new version-id; toast "Now on v3 — old version still available in Versions."
```

Destructive notes (refinement is destructive in M1, non-destructive M2 per `ALPHA-TEST-PLAN.md` §7): the plan preview names which tables get dropped + recreated; user must check a confirmation checkbox before Apply when destructive operations are present.

### 5.10 Export (`WEB-EXPORT`)

```
Workspace → Exports tab
  Format picker: [CSV per table] [Postgres SQL] [JSON full] [Full archive (everything)]
  PII handling toggle: "Include PII columns" (default off; reveals warn dialog "PII export is audit-logged + emailed to admin")
  Request export
       ↓
  gateway.exports.request(versionId, format)
       ↓
  Job row: queued → running → ready
  Polling via TanStack Query (interval=2s while not ready, capped at 60s)
       ↓
  Ready: signed-URL download; expires_at shown; auto-delete in 24h
  History list: previous exports + their status
```

Success: file downloaded; `audit_events` row written by server (action=`export`).

### 5.11 Share link (`WEB-SHARE`)

Two surfaces: create + manage from inside workspace, view from public `/s/{token}`.

Create:

```
Share tab → Create share link
  Permissions: [Overview only] [Overview + KPIs] [Full read-only (default)]
  Expires: [24 hours] [7 days] [Never] [Custom]
  Password protect: optional
  Notes: optional ("for the investor deck")
       ↓
  gateway.shareLinks.create(versionId, opts) → ShareLinkDTO
  Modal shows the URL with copy button + caution: "Anyone with this link can view this workspace. Revoke from this list."
```

Public view at `/s/{token}` (`ShareShell`):

```
- Top bar: minimal (Baseflo wordmark · "Shared workspace" pill · Generated-by footer link)
- Hero: business summary (1 paragraph from project description)
- KPI highlights (max 6)
- Dashboard preview (the most-impactful chart from KPI planner)
- Top assumptions (the explicit Assumption[] from project_versions.assumptions, max 5)
- Top risks (from CoherenceGate's surfaced warnings, max 3)
- Hidden: raw traces, audit log, PII columns, internal validation reports, refinement history.
- Password gate if configured.
- "Powered by Baseflo" footer with sign-up CTA — visible only if owner has the "show CTA" toggle on.
```

If revoked: 410 Gone with branded "This share link has been revoked." page.

### 5.12 Settings (`WEB-SETTINGS`)

`SettingsShell` with side nav. Tabs map 1:1 to control-plane subsystems.

| Tab | Surfaces | Backed by |
|---|---|---|
| Org | name, slug, region, logo, plan badge, danger zone (delete org) | `organizations` |
| Team | members + roles + invites + pending; SCIM info (M3+) | `memberships` |
| Billing | plan + usage meters + payment method; portal link to Stripe | `billing_subscriptions` + Stripe portal |
| API Keys | list, create, revoke, last-used; copy-once secret display | `api_keys` |
| Custom Domain | configure CNAME, verification, certificate status (Pro+) | `organizations.custom_domain` (added in M2) |
| Deployment | per-project mode editor (Hosted ↔ BYO ↔ Self-Host); BYO connection-string flow | `projects.deployment_mode` |
| SSO (M3+) | OIDC/SAML config, test mode, force-on switch (Business+) | `organizations.sso_config` |
| Audit | log table with filter by action, actor, target, time range; CSV export | `audit_events` |

Role gating per `AUTH.md` §3.6 — viewer sees read-only views; editor cannot revoke API keys; admin cannot change billing or delete org.

Destructive operations always behind a typed confirmation modal (see `BulkDelete` pattern in `ADMIN-GEN.md` §3.4 and §11 confirmation pattern below).

---

## 6. Trust Patterns (the "high-trust niche UX" anchor)

The user requested a "high-trustworthy" experience. Trust in B2B SaaS is built by these specific UI behaviors. Each is a load-bearing component, not a polish item.

### 6.1 PII mask + reveal

Per `ADMIN-GEN.md` §3.5: every column tagged `pii_*` by `ColumnClassifier` is masked at render. A click on the mask icon:

1. Calls `gateway.workspace.revealPII(...)`.
2. Server checks role; writes `audit_events` row (action=`pii.reveal`).
3. Returns the unmasked value with a 30-second TTL.
4. Frontend shows the value with a countdown ring; auto-remasks after 30 seconds.
5. Reveal-disabled UI state for Viewer role; CTA "Ask your admin" + email-pre-fill button.

Component: `<PIIField column={col} value={maybeMasked} onReveal={...} />` from `@baseflo/ui`.

### 6.2 Source attribution

Every reconciled-entity row carries an attribution badge `[S+M+P]` (Stripe + Mailchimp + Postgres) when contributions span >1 source. Hover reveals per-field attribution: "email — from Sheets · last_charge_at — from Stripe · phone — from Excel."

This makes the reconciliation moat *visible*. Without this UI, users assume Baseflo "made up" data; with it, every value is traceable to its origin connector. Component: `<AttributionBadge contributions={...} />`.

### 6.3 Deployment-mode badge

Always-visible chip on the workspace top bar:

- **Hosted Cloud** — neutral gray; tooltip "Encrypted in our Postgres · `region` · KMS key `kek-…-abcd1234`."
- **BYO Database** — blue accent; tooltip "Your Postgres at `***.neon.tech`. We never store rows."
- **Self-Host Docker** — green; tooltip "Your infra. Our image."
- **Local Dev** — orange; tooltip "Local container. Not for production data."

Clicking opens `Settings → Deployment` with the current mode pre-selected. This is the one-glance answer to "where does my data live?"

### 6.4 Reversible-action pattern

Per `01-architecture.md` §3.8 every refinement is immutable + reversible. UI surfaces this:

- "Apply" buttons on refinements are paired with "Old version stays available."
- Workspace top-right always shows the version selector with quick rollback.
- Destructive confirmation modal (delete project, drop a connector) requires typing the org/project slug to confirm.

### 6.5 Audit transparency

Two surfaces:

1. Org-level: `Settings → Audit` — full filterable log.
2. Per-project: `Workspace → Audit` — same model scoped.

Filterable by actor, action, target, time. Exportable as CSV. Per `04-database-schema.md` §4.22 retention is 1 year; UI shows "Showing last 1 year" footer.

### 6.6 Honest copy (no overclaim)

Recast for the post-pivot product (no overclaim, honest copy at every surface):

- Never say "AI" in primary product copy. Per `20-gtm.md` §7 ("Is this AI?" objection): "Yes, but you don't see it.")
- Never claim certifications not held. Status page shows current SOC2 status: in-progress until certification.
- Never auto-grant share-link access without an explicit user action.
- Never silently retry destructive actions.

### 6.7 Status pill (top-bar, always)

- Green dot: all systems normal.
- Yellow: degraded service (with tooltip naming the degraded subsystem).
- Red: incident in progress (with tooltip linking to status.baseflo.com).
- Loaded from `gateway.system.health()` polled every 60s; piggy-backs on the existing `OPS-STATUS` page.

---

## 7. Design System (`WEB-DESIGN-SYSTEM` → `@baseflo/ui`)

### 7.1 Token taxonomy

CSS custom properties only. No hardcoded hex in component code. `tokens.css` defines them; `tailwind.config.ts` exposes them as Tailwind utilities; `@baseflo/ui` references them via the Tailwind preset.

```css
/* Surface */
--color-bg:           hsl(220 20% 98%);   /* off-white */
--color-surface:      hsl(0 0% 100%);     /* card */
--color-surface-2:    hsl(220 14% 96%);   /* subtle elevation */
--color-border:       hsl(220 13% 91%);
--color-border-focus: hsl(217 91% 60%);

/* Text */
--color-fg:           hsl(222 47% 11%);
--color-fg-muted:     hsl(215 16% 47%);
--color-fg-subtle:    hsl(217 13% 64%);
--color-fg-on-accent: hsl(0 0% 100%);

/* Accents */
--color-accent:       hsl(217 91% 60%);   /* deep blue; brand accent, see 06-design.md §4.1 */
--color-accent-hover: hsl(217 91% 54%);
--color-accent-soft:  hsl(217 100% 96%);

/* Semantic */
--color-success: hsl(142 71% 45%);
--color-warning: hsl(38 92% 50%);
--color-danger:  hsl(0 84% 60%);
--color-info:    hsl(199 89% 48%);
--color-private: hsl(280 30% 50%);   /* PII-related */

/* Typography */
--font-sans:   "Inter", ui-sans-serif, system-ui, sans-serif;
--font-mono:   "JetBrains Mono", ui-monospace, monospace;
--text-xs:     0.75rem;
--text-sm:     0.875rem;
--text-base:   1rem;
--text-lg:     1.125rem;
--text-xl:     1.25rem;
--text-2xl:    1.5rem;
--text-3xl:    1.875rem;
--leading-tight: 1.2;
--leading-normal: 1.5;
--font-weight-regular: 400;
--font-weight-medium:  500;
--font-weight-semibold: 600;

/* Spacing — 4px base */
--space-1: 0.25rem; --space-2: 0.5rem;  --space-3: 0.75rem;
--space-4: 1rem;    --space-5: 1.25rem; --space-6: 1.5rem;
--space-8: 2rem;    --space-10: 2.5rem; --space-12: 3rem;

/* Radius */
--radius-sm: 4px; --radius-md: 6px; --radius-lg: 8px; --radius-pill: 9999px;

/* Shadow */
--shadow-sm: 0 1px 2px hsl(220 13% 91% / 0.5);
--shadow-md: 0 4px 12px hsl(220 13% 91% / 0.6);
--shadow-lg: 0 8px 24px hsl(220 13% 87% / 0.7);

/* Motion */
--motion-fast:   120ms cubic-bezier(0.2, 0, 0, 1);
--motion-normal: 200ms cubic-bezier(0.2, 0, 0, 1);
--motion-slow:   320ms cubic-bezier(0.2, 0, 0, 1);

/* Z-index */
--z-base: 0; --z-sticky: 100; --z-overlay: 1000; --z-modal: 1100; --z-toast: 1200; --z-tooltip: 1300;
```

Dark mode: deferred to M3. The tokens are designed to swap via `[data-theme="dark"]` attribute switch; no component code changes needed.

### 7.2 Component inventory (`@baseflo/ui`)

Wraps Radix primitives with brand tokens; adds Baseflo-specific composite components.

**Primitives (Radix-wrapped):**
`Button`, `IconButton`, `Link`, `Input`, `Textarea`, `Select`, `Checkbox`, `Radio`, `Switch`, `Slider`, `Dialog`, `Popover`, `Tooltip`, `Menu`, `DropdownMenu`, `ContextMenu`, `Tabs`, `Accordion`, `Collapsible`, `Toggle`, `ToggleGroup`, `ToolbarRoot`, `Separator`, `ScrollArea`, `AlertDialog`, `HoverCard`, `Avatar`, `Progress`, `Toast`.

**Composites (Baseflo-specific):**
`StatusPill`, `ValidationBadge`, `RoleBadge`, `PlanBadge`, `DeploymentModeBadge`, `AttributionBadge`, `PIIField`, `MoneyCell`, `StatusChip`, `ConnectionDot`, `KPIWidget`, `MetricStrip`, `EmptyState`, `ErrorCallout`, `ErrorMessage`, `LoadingSkeleton`, `OnboardingStep`, `StageRailItem`, `AgentActivityRow`, `ArtifactPreviewCard`, `RefinePlanCard`, `ShareLinkCard`, `AuditRow`, `CommandPalette`, `ConfirmDestructive`, `CodePanel` (Shiki), `EditorPanel` (Monaco; lazy).

**Layouts:**
`AppShell`, `AuthShell`, `WorkspaceShell`, `SagaShell`, `ShareShell`, `SettingsShell`, `Sidebar`, `RightRail`, `TopBar`.

**Charts:**
`KPIChart` (sparkline + value), `LineChart`, `BarChart`, `AreaChart`, `Gauge`, `EmptyChart` — all wrapping Recharts with brand tokens.

**Tables:**
`DataTable` (TanStack Table + Virtual + a11y); `ListColumnRenderer` per `ADMIN-GEN.md` `WidgetKind`.

**Forms:**
`FormField`, `FormError`, `FormCaption`, `FormSection` — react-hook-form + Zod resolver out of the box.

### 7.3 Iconography

`lucide-react` only. A curated subset is exported by `@baseflo/ui/icons` with stable names: `IconCustomers`, `IconOrders`, `IconConnectors`, `IconAnalytics`, `IconRefine`, `IconExport`, `IconShare`, `IconAudit`, `IconSettings`, `IconSearch`, `IconCheck`, `IconWarning`, `IconError`, `IconInfo`, `IconLock`, `IconUnlock`, `IconArrowRight`, `IconExternalLink`, `IconCopy`. Adding an icon requires a registered name; ad-hoc imports of `lucide-react` outside `@baseflo/ui/icons` is forbidden by ESLint rule.

### 7.4 Voice & tone

Inherits `20-gtm.md` §8.1:

- Plain English. No jargon.
- Calm confidence. Specific over general.
- Builder energy. Not corporate.

UI copy rules:

- Empty states use direct verbs: "Add your first source" — never "It looks like you haven't added any sources yet."
- Errors name the action: "Couldn't connect to Stripe. Check the API key and try again." — never "An error occurred."
- CTAs use specific verbs: "Build my workspace", "Apply refinement", "Connect Stripe" — never "Continue", "Submit", "OK."
- Confirmations name the action and the outcome: "Delete project 'growth'? This cannot be undone." — never "Are you sure?"

### 7.5 Motion principles

- Default: `--motion-normal` 200ms easing `cubic-bezier(0.2, 0, 0, 1)`.
- Page transitions: View Transition API where supported; fallback to no transition (no janky CSS attempts).
- Skeletons: shimmer at `--motion-slow`.
- Toasts: enter 200ms, exit 120ms.
- No bounces, no springs, no overshoots. Every motion has a clear cause-and-effect.
- Respects `prefers-reduced-motion`: motion is replaced with instant transitions globally.

### 7.6 Visual non-goals (anti-pattern fence)

Per [`06-design.md`](../06-design.md) §4.8 + `20-gtm.md` §8.2 "Visual Direction":

- ❌ Purple-to-pink gradients ("AI gradients").
- ❌ Glassmorphism, blob/orb decoration.
- ❌ Glowing accents.
- ❌ Marketing-hero composition inside the app.
- ❌ Nested cards (one layer of elevation max per pane).
- ❌ Dark side-nav with light main (never inverse-themed regions).
- ❌ Iconography from multiple icon families.

---

## 8. States (loading, empty, ready, warning, error, disabled)

Every screen ships its five states explicitly. Storybook + Vitest cover all five for every meaningful component.

### 8.1 Loading

- **Skeleton** for known shapes (table → header skeleton + 6 row skeletons; KPI strip → 3 placeholder widgets).
- **Spinner** only for very short operations (<500ms expected).
- **Progress bar** when the operation has a percentage (file upload, export job).
- Never an empty white pane. Loading state is always present from frame 1.

### 8.2 Empty

- Shape: icon + headline + supporting paragraph + primary action.
- Examples:
  - No projects → "Create your first project" + "Build workspace" CTA.
  - No connectors → "Add your first source" + connector card grid.
  - No refinements → "Refine your workspace by describing what to change." + composer focus.

### 8.3 Ready

- Default state. Stable layout dimensions; no shifts as data lands.

### 8.4 Warning

- Soft yellow chip + supporting copy. Inline within ready state, not blocking.
- Example: "Stripe data hasn't synced in 4 hours. [Reconnect]"

### 8.5 Error

- Red callout + cause + recovery action. Use `ErrorCallout` from `@baseflo/ui`.
- For full-screen errors (terminal saga failure, 500, network down): full `ErrorView` with a "Try again" CTA + a "Contact support" secondary.
- Never raw stack traces, provider names, or internal exception classes.

### 8.6 Disabled

- Grey-out + tooltip explaining *why*. Never a silent disabled.
- Example: "Reveal PII (Viewer role can't reveal PII; ask your admin)."

---

## 9. Accessibility (`WEB-A11Y` → WCAG 2.1 AA)

The bar is non-negotiable: industry-grade means usable by people relying on assistive tech.

### 9.1 Required behaviors

- Every interactive element keyboard-reachable, with visible focus ring (`--color-border-focus`).
- Tab order matches visual order. Arrow-key navigation inside lists/grids.
- ARIA landmarks: `<header>`, `<nav>`, `<main>`, `<aside>`, `<footer>`. One `<main>` per shell.
- Headings form a tree: one `<h1>` per page (the page title); `<h2>` for major sections; never skip levels.
- Focus management on route change: focus moves to `<h1>`; on modal open: focus moves to first focusable element; on modal close: focus returns to invoker.
- Live regions: SSE saga events announce in `aria-live="polite"`; errors in `aria-live="assertive"`.
- Status conveyed by color **and** icon **and** label. Never color alone.
- Forms: every `<input>` has a `<label>`; errors associated via `aria-describedby`; required fields announced.
- Color contrast: 4.5:1 minimum body text; 3:1 minimum large text and UI graphics; tested in `tokens.test.ts` against measured contrast at design time.
- Touch targets: minimum 44x44 CSS px.
- Tables: `<th scope="col">`, sort buttons announce direction.
- Charts: include accessible name + accessible description summarizing the data; "View as table" toggle.

### 9.2 Tooling

- `@axe-core/playwright` runs on every Playwright test; CI fails on any violation of impact ≥ "serious."
- `eslint-plugin-jsx-a11y` lint rules enforced; no exceptions without comment justification.
- Manual screen-reader passes (NVDA + VoiceOver) on every milestone-shipping flow.

### 9.3 Reduced motion / reduced data

- `prefers-reduced-motion: reduce` removes non-essential motion.
- `prefers-reduced-data: reduce` opts out of large auto-loaded charts; a "Load chart" button replaces them.

---

## 10. Responsive Behavior

The app is **desktop-first** — workspace tasks need horizontal real estate. Phone is an explicit non-goal for v1; the share page (`/s/{token}`) and auth pages remain fully responsive.

### 10.1 Breakpoints

```
sm:  640px      auth screens, share page (read-only) — fully functional
md:  768px      auth + share + a graceful "settings" minimum
lg:  1024px     full app shell available; org dashboard fully usable
xl:  1280px     workspace shell fully comfortable (default target)
2xl: 1536px     workspace shell with refine rail open
```

### 10.2 Per-shell behavior

| Shell | Below 640px | 640–1024px | 1024–1280px | ≥1280px |
|---|---|---|---|---|
| AuthShell | Native | Native | Native | Native |
| ShareShell | Reflowed single-column | Single-column | Two-column | Polished |
| AppShell | "Optimized for desktop" gate (`/unsupported`) | Reduced top-bar; primary actions only | Native | Native |
| WorkspaceShell | Gate | Gate | Side nav collapsed by default; refine rail closed | Native (refine rail toggleable) |
| SagaShell | Gate | Gate | Stage rail above; detail below; artifacts hidden | Three-column |
| SettingsShell | Gate | Stacked single-column | Two-column | Native |

### 10.3 The `/unsupported` page

Small viewports on workspace-class routes show a polished "Optimized for desktop" page with a single CTA: "Email me a desktop link." Not a 404. The user understands this is intentional, not broken. Auth pages and the share page remain fully responsive at all viewports.

### 10.4 Print

- Share page has a `print.css` that strips chrome, expands all collapsibles, ensures charts render as static images.
- Workspace prints: limited support; the most useful print artifact is `Export → PDF` (M3+) using server-side rendering, not browser print.

---

## 11. Performance Budgets

Set during design; CI enforces on every PR.

| Metric | Budget | How measured |
|---|---|---|
| First contentful paint | < 1.5s on Fast 3G | Lighthouse CI |
| Largest contentful paint | < 2.5s on Fast 3G | Lighthouse CI |
| Time to interactive | < 3.0s on Fast 3G | Lighthouse CI |
| Total bundle (initial route) | < 250 KB gzipped | `vite-bundle-analyzer` + CI gate |
| Per-route additional chunk | < 80 KB gzipped | CI gate |
| SSE message-to-paint latency | < 100ms p95 | Custom telemetry |
| Workspace `AdminUISpec` fetch + render | < 1s p95 | Custom telemetry |
| Memory after 30 min of active use | < 500 MB | Manual profiling per release |

Lazy-loading rules:

- Monaco editor lazy-loaded only when entering an edit context.
- Recharts is in the workspace bundle; share page uses static SVG snapshots when feasible.
- Per-route code splitting via TanStack Router's lazy-route imports.

---

## 12. Confirmation Patterns (destructive operations)

Inherits from `ADMIN-GEN.md` §3.4 and `AUTH.md` §3.6.

| Operation | Confirmation |
|---|---|
| Sign out | None (cookie cleared; one-click un-sign-out via "Sign back in"). |
| Discard refinement | None (creates no version). |
| Apply destructive refinement | Inline checkbox: "I understand existing data will be wiped" + Apply button. |
| Revoke connector | Modal: "Revoke Stripe? This will stop syncing. Existing data stays." [Revoke] [Cancel]. |
| Revoke API key | Modal with key-prefix shown; type prefix to confirm. |
| Delete share link | Modal; one-click confirm. |
| Archive project | Modal: "Archive 'growth'? You can restore it within 30 days." |
| Delete project (post-archive) | Modal: type project slug to confirm; double opt-in. |
| Delete org | Modal: type org slug to confirm + email confirmation link. |
| Change deployment mode (Hosted → BYO) | Wizard: provide DSN, test connection, plan migration window, two-step confirm. |
| Bulk delete in admin | Two-person approval (M3+) per `ADMIN-GEN.md` §3.4. |

---

## 13. Design Patterns Applied

Cross-references to `50-design-patterns.md`. Each row says where the pattern lives in this feature.

| Pattern | Where in WEB-APP |
|---|---|
| **Strategy** | Transport adapters: REST / SSE / placeholder. Theme tokens: light / dark. |
| **Observer / Pub-Sub** | SSE event consumption in saga viewer + refine + workspace cross-tab updates. |
| **Repository** | (server-side; web app consumes via gateway). |
| **Command** | Refinement proposals: typed command preview + apply. Destructive ops: confirmable typed command. |
| **Adapter** | API client: gateway methods adapt domain calls to transport calls. |
| **Specification** | List-view filters: `FilterSpec` per column from `ADMIN-GEN`. |
| **Factory** | `<RouteLayout>` factory selects shell based on route segment. |
| **Singleton** | TanStack Query client; Router; theme provider — one per app. |
| **State machine** | Saga viewer's stage rail; connector install flow (each connector kind has a typed state machine). |
| **Schema-Driven UI** | Workspace tabs are pure renders of `AdminUISpec` — see `ADMIN-GEN.md`. |
| **Boundary** | UI ↔ feature service ↔ gateway ↔ transport — enforced by ESLint import rules. |

---

## 14. Test Plan

TDD-first per `00-decisions.md` §9. Target coverage: 90% statements; 100% on `error-system`, `auth`, `share-page` (security-critical).

### 14.1 Unit (Vitest)

- Token contrast assertions (`@baseflo/ui/tokens.test.ts`): every semantic color combination meets WCAG AA.
- Error registry: every backend error code maps to a registered frontend copy or falls through to `BF-WEB-UNKNOWN-001`.
- Gateway service: each method has a happy + error path test against `placeholderTransport`.
- State reducers: stage-rail reducer over a known event sequence produces expected state.
- Form validators (Zod schemas): valid + each invalid case.

### 14.2 Component (Vitest + Testing Library)

- Every composite component in `@baseflo/ui` has a test for its five states (loading / empty / ready / warning / error).
- Accessibility smoke: `@axe-core/react` assertion on each component test.
- Keyboard navigation: tab order, escape closes modals, enter submits forms.

### 14.3 Integration (Playwright + `@axe-core/playwright`)

Golden-path flows; `gateway.placeholderTransport` injected via `window.__BASEFLO_TEST_TRANSPORT__` for deterministic SSE event sequences.

| Flow | Assertions |
|---|---|
| Sign-up → welcome → first org → first project → connect Postgres → saga → workspace.ready | Reaches workspace; URL stable; KPI strip non-empty. |
| Sign-in returning user → org dashboard → click project → workspace overview | Loads in <2s; no console errors; axe clean. |
| ICP-B `/start` → drop CSV + connect Stripe → saga → unified customers tab | "Customers (1247 unique, 488 resolved)" badge present. |
| Saga viewer: clarification round-trip | Modal blocks input; answer dispatched; saga resumes. |
| Saga viewer: SSE disconnect + reconnect | Reconnect chip shows; `?seq=` resume produces same final state. |
| Workspace → tab → row detail → PII reveal | Reveal logged in audit table; auto-remask after 30s. |
| Refinement: propose → preview → apply → version switch | New `version-id` in URL; refine history shows entry. |
| Export → request CSV → download → audit row written | File downloaded; audit list updated. |
| Share link create → public access → revoke → 410 | Public page shows when active; 410 when revoked. |
| Settings → invite teammate → invite email visible | Pending invite row shown. |
| Mobile viewport on `/o/.../v/.../customers` | `/unsupported` page rendered, not broken layout. |

### 14.4 Contract tests (Vitest cross-package)

- `@baseflo/contracts` types compile cleanly against generated types from server OpenAPI.
- `AdminUISpec` round-trip: server fixtures load and render without missing props.

### 14.5 Visual regression

Playwright screenshots at fixed viewport sizes (1280, 1440, 1920) on five canary screens; manual review on diff > 0.1% pixel delta.

### 14.6 Performance regression

Lighthouse CI runs on every PR; budgets in `lighthouserc.js` (per §11). PR fails on regression > 5%.

---

## 15. Error Codes (`WEB-ERROR-SYSTEM` → `@baseflo/error-system`)

Centralized registry in `packages/error-system/src/error-codes.ts`. Every code maps to: title, message, severity, recovery action. The registry is exhaustive — unknown codes fall through to `BF-WEB-UNKNOWN-001`.

### 15.1 Backend codes the frontend handles

The frontend consumes `BF-AREA-NNN` codes from the server. **Rule:** do not invent backend prefixes — mirror what the server emits. Examples consumed: `BF-AUTH-001..006`, `BF-CONN-001..005`, `BF-CONN-STRIPE-002`, `BF-AGENT-001..010`, `BF-COHERENCE-001`, `BF-SCHEMA-001..010`, `BF-EXPORT-001..003`, `BF-SHARE-001..003`.

### 15.2 Frontend-only codes (`BF-WEB-NNN`)

| Code | Condition | UI behavior |
|---|---|---|
| `BF-WEB-001` | Network unreachable / offline | Sticky banner: "You're offline. We'll resume when you're back." Polls `/api/v1/health` every 5s. |
| `BF-WEB-002` | API request failed: 5xx | Inline `ErrorCallout` + "Retry" button. |
| `BF-WEB-003` | API request failed: 4xx unhandled | Same as 002 but no retry. |
| `BF-WEB-004` | SSE disconnected | Inline pill "Reconnecting…"; auto-retry 3 times with backoff; then `BF-WEB-005`. |
| `BF-WEB-005` | SSE reconnect exhausted | Banner "Lost connection to live updates. Refresh the page." + Refresh button. |
| `BF-WEB-006` | Invalid URL params (Zod parse fail) | Redirect to safe parent route + toast. |
| `BF-WEB-007` | Browser unsupported (no EventSource, no IntersectionObserver) | Page-level message with required browsers. |
| `BF-WEB-008` | Mobile viewport on workspace-class route | `/unsupported` page rendered. |
| `BF-WEB-009` | Reveal-PII denied (server returned 403 BF-ADMIN-003) | Inline message + "Ask your admin" pre-filled email. |
| `BF-WEB-010` | TanStack Query stale-load failure | Skeleton stays + retry every 30s; banner if persistent. |
| `BF-WEB-011` | Form validation failed | Field-level error via `aria-describedby`. |
| `BF-WEB-012` | Form submission optimistic update failed; rollback applied | Inline error + reset state. |
| `BF-WEB-013` | Login redirect detected loop | Hard sign-out + clear cookies + reload to `/sign-in`. |
| `BF-WEB-014` | Connector OAuth callback state mismatch | Page-level error with "Start over" + reroute to `/connectors`. |
| `BF-WEB-015` | Saga conversation_id not found | "This saga is no longer available" + link to project. |
| `BF-WEB-016` | Refinement plan rejected by user (discard) | Toast confirmation; not an error. (Code reserved for analytics tag only.) |
| `BF-WEB-017` | Workspace AdminUISpec malformed | Skeletons stay + report incident; user sees "Refresh — if this persists, contact support." |
| `BF-WEB-018` | Export job timed out (>5 min) | Inline "Export taking longer than usual" + "Email me when ready" option. |
| `BF-WEB-019` | Share link revoked (server 410) | Branded "Link revoked" page. |
| `BF-WEB-020` | Share link expired (server 410, expired) | Branded "Link expired" page. |
| `BF-WEB-021` | Saga terminal failure (server emitted error.terminal) | Saga shell error template + "Start over with same prompt" CTA. |
| `BF-WEB-022` | Multi-tab conflict on same workspace edit | Modal: "Another tab edited this. [Discard] [Reload]". |
| `BF-WEB-023` | Plan limit reached on action (e.g., 4th project on Pro) | Modal explaining the limit + "Upgrade" link to billing. |
| `BF-WEB-024` | Browser storage quota exceeded | Toast: "Storage full — preferences may not save." Falls back to in-memory only. |
| `BF-WEB-025` | View Transition API unavailable | Silent fallback (no error to user). |
| `BF-WEB-UNKNOWN-001` | Unmapped error | `ErrorCallout` with generic copy + "Contact support" link with embedded request-id. |

### 15.3 Error rendering rules

- **Inline:** validation errors, soft warnings.
- **Toast:** non-blocking action results (succeeded, failed retry).
- **Banner:** session-level concerns (offline, plan limit, SSE down).
- **Modal:** blocking errors (auth required, conflict).
- **Page:** terminal failures (404, 500, expired share).

Never raw exception names, stack traces, or backend internal error messages reach the user. **Normalization rule:** every backend payload is normalized through `error-system/src/error-normalizer.ts` before reaching any UI component; unknown shapes fall through to `BF-WEB-UNKNOWN-001`.

---

## 16. Internationalization

Deferred to M5+ but designed in:

- All user-visible strings live in `packages/i18n/src/en.ts`. Component code references `t("project.create.cta")`, never inline strings.
- Date/time formatted via `Intl.DateTimeFormat`; numbers via `Intl.NumberFormat`.
- Currency rendered via `Intl.NumberFormat` with `style: "currency"` and the column's currency from `ColumnIR.minor_unit_for`.
- RTL layout designed in via `[dir="rtl"]` CSS attribute selectors; all components use logical CSS properties (`margin-inline-start`, not `margin-left`).
- v1 ships English (`en`) only.

---

## 17. Telemetry & Observability

Frontend-side telemetry feeds the same observability stack as the server (`OPS-LOGS`, `OPS-TRACES`, `OPS-METRICS`).

| Event | When emitted | Tags |
|---|---|---|
| `web.route.viewed` | Route loader resolves | route, org_slug |
| `web.connector.installed` | Successful install | kind, project_id |
| `web.saga.subscribed` | EventSource opened | conversation_id |
| `web.saga.event_received` | Per SSE event | kind, sequence, latency_ms |
| `web.refinement.proposed` | Plan returned | project_id |
| `web.refinement.applied` | New version live | project_id, new_version_id |
| `web.export.requested` | Export job created | format, version_id |
| `web.share.created` | Share link issued | scope, expires_at |
| `web.error` | Any registered code | code, route, severity |
| `web.perf.lcp`, `web.perf.fid`, `web.perf.cls`, `web.perf.inp` | Web Vitals | route |

Sink: a single `/api/v1/web-telemetry` endpoint that fans out to Sentry (errors), OTel (traces), Prometheus (metrics).

PII: never sent. The user's email and ID stay server-side; the frontend ships only org/project slugs and feature-event metadata.

---

## 18. Security

Inherits backend posture (`SECURITY.md`). Frontend-specific items:

- **CSP**: strict; `default-src 'self'`; no `unsafe-inline` or `unsafe-eval`. Inline styles only via tokens (CSS variables, no `style=` attributes from data).
- **Cookies**: session cookie is `httpOnly`, `Secure`, `SameSite=Lax`. The frontend never reads or writes the session cookie directly.
- **CSRF**: protected by `SameSite=Lax` for v1; explicit CSRF tokens in M3+ (per `ALPHA-TEST-PLAN.md` §7).
- **XSS**: all dynamic strings render via React (auto-escaped); `dangerouslySetInnerHTML` is forbidden by ESLint outside the registered Shiki render component.
- **Clickjacking**: `X-Frame-Options: DENY` (server header).
- **Token leak prevention**: connector tokens never reach the frontend; the install flow opens a server-issued redirect, the callback completes server-side, and only metadata returns to the client.
- **Open-redirect prevention**: post-sign-in redirects validated against an allowlist of internal paths only. External `redirectTo` query params are rejected.
- **API-key copy-once**: when a user creates an API key, the secret is shown once and cannot be retrieved again. The UI emphasizes this with a one-time copy modal.

---

## 19. Dependencies

Forward dependencies (this feature depends on):

- [`AUTH`](AUTH.md) — backend session contract; `SessionDTO` shape.
- [`ADMIN-GEN`](ADMIN-GEN.md) — `AdminUISpec` rendering inside workspace.
- [`SDK-AND-API`](SDK-AND-API.md) — REST + OpenAPI for type generation.
- [`JOBS-AND-SSE`](JOBS-AND-SSE.md) — saga event channel; replay semantics.
- [`REFINEMENT`](REFINEMENT.md) — refinement service contract.
- [`CONN-FRAMEWORK`](CONN-FRAMEWORK.md) — connector install flow shape.
- [`ANALYTICS`](ANALYTICS.md) — analytics tab panels.
- [`DIGEST`](DIGEST.md) — daily digest preview on overview.
- [`SECURITY`](SECURITY.md) — encryption, audit, export, deletion behavior.
- [`OBSERVABILITY`](OBSERVABILITY.md) — telemetry sinks.

Backward dependencies (features that depend on this):

- `ADMIN-GEN` lives *inside* the workspace shell.
- `WEB-MARKETING` (M2) shares design tokens via `@baseflo/ui`.
- `WEB-DESKTOP` (M5+) wraps this same web app via Tauri v2.

---

## 20. Milestone Plan

The web app ships in five sub-milestones aligned to the engine roadmap (`01-architecture.md` §12). Each sub-milestone is independently demoable.

### M0 — Web Foundations (week 1–2 after pivot)

- `WEB-SHELL` scaffolding: monorepo, vite, router, providers, layouts, `@baseflo/ui` skeleton, tokens, error system, gateway + transports.
- `WEB-AUTH`: sign-in, sign-up, magic-link, Google OAuth callback, session refresh, sign-out.
- `WEB-ONBOARD`: `/welcome` first-run wizard.
- `WEB-DESIGN-SYSTEM`: tokens, ~12 primitives, ~10 composites.
- `WEB-A11Y`: axe + jsx-a11y in CI.
- Playwright golden-path: sign-up → welcome → empty org dashboard.

### M1 — Single-source magic moment

- `WEB-PROJECT` (create + list + dashboard).
- `WEB-CONNECT` for Postgres + CSV/Excel + Sheets.
- `WEB-SAGA` viewer.
- `WEB-WORKSPACE` shell hosting `ADMIN-GEN` for the v1 schema.
- Refine panel scaffolding (composer + history; Apply happens in M2).
- `WEB-EXPORT` for CSV.
- `WEB-SHARE` create + revoke (public page basic).
- `WEB-SETTINGS`: Org + Team + Audit (read-only).

Validation gate: friend's case end-to-end through the web app (`20-gtm.md` §2.1), zero CLI invocations.

### M2 — Multi-source unification + production polish

- Add Shopify, Stripe, Mailchimp connectors in the connector hub.
- Multi-source attribution badge live.
- `WEB-REFINE` Apply path; version-switch toast; refine history.
- `WEB-WORKSPACE` Analytics tab (funnels, cohorts, geo, top-N) live.
- `WEB-EXPORT` adds SQL + JSON formats; PII export confirmation.
- `WEB-SHARE` adds password protection + custom expiration.
- `WEB-SETTINGS` adds Billing (Stripe portal link), API Keys, Custom Domain (Pro+), Deployment mode picker.
- `WEB-MARKETING` static site at `baseflo.com`.

Validation gate: a real e-commerce SMB drops Excel + Shopify and sees one view, all through the web app.

### M3 — Privacy + enterprise readiness

- BYO-DB onboarding wizard (Settings → Deployment → BYO; test connection; migration).
- Self-Host Docker download page with license key generation.
- SSO (OIDC + SAML) configuration UI.
- SCIM-managed Team tab.
- Audit log advanced filters + CSV export.
- `WEB-WORKSPACE` adds compare-versions side-by-side.
- Status page polish + incident banner system.

### M4+ — Beyond alpha

- Bulk-edit + two-person approval (`ADMIN-GEN` M4 features surfaced in UI).
- AI Copilot (in-product prompt to do safe ops) — `AI-COPILOT`.
- MCP integration UI for hosted-cloud users.
- `WEB-DESKTOP` (Tauri v2 wrap, M5+).

---

## 21. Open Questions (logged, not blocking M0)

These are the explicit ambiguities to resolve as we build. Each gets a `00-decisions.md` Changelog entry once locked.

1. **Marketing site stack** — separate Next.js / Astro / static? Decision needed before M2. Default: Astro for SEO, deployed to Cloudflare Pages.
2. **Real-time collaboration on workspace edits** — multi-user simultaneous editing of admin tabs. Currently last-writer-wins. Decision: introduce optimistic locking with cell-level conflict UI in M3 if customer demand surfaces.
3. **Storybook vs. Ladle** for component dev environment — both work; Ladle is faster but smaller community. Decision in M0; default: Storybook 8 in `apps/storybook`.
4. **Sentry replay** for session replay debugging — privacy-sensitive. Decision in M2 with explicit per-org opt-in.
5. **Feature-flag system** — LaunchDarkly is overkill; rolling our own is risk; default: `unleash-client` self-hosted. Decision in M2.

---

## 22. Out of Scope (explicit non-goals for v1)

- Native mobile apps. Tauri desktop is M5+.
- Real-time multi-cursor collaboration.
- A WYSIWYG schema editor. Refinement is text-driven.
- A full marketing CMS.
- Customizable dashboards (the dashboard is generated from KPIs in M1; user-arrangeable is M3+).
- A Slack-like inbox.
- Custom widget development by end users (built-in widget set is the bar).

---

## 23. Acceptance Criteria (alpha promotion to public launch)

Per `00-decisions.md` §10 + `20-gtm.md` §9.2, the web app is ready for soft launch (Show HN) when:

1. ✅ A new user can sign up, create an org, create a project, connect Postgres, and reach a non-empty workspace in < 5 minutes total.
2. ✅ The 90-second demo from `20-gtm.md` §5 runs end-to-end on a real connected SMB stack.
3. ✅ All `BF-WEB-*` codes have registered copy; no unmapped errors in 7-day production telemetry.
4. ✅ Lighthouse on the workspace overview ≥ 90 across performance, accessibility, best practices, SEO.
5. ✅ Zero open Blocker bugs from `ALPHA-TEST-PLAN.md` web journeys.
6. ✅ Playwright golden-path suite green on Chrome, Firefox, Safari at three viewport sizes.
7. ✅ Manual screen-reader pass clean on five primary flows (sign-in, onboarding, saga, workspace, settings).
8. ✅ Multi-org switching, sign-out, and session refresh covered by integration tests.
9. ✅ Status pill reflects real backend health.
10. ✅ Brand audit pass: zero AI-gradient regressions; one accent; consistent type scale.

When all ten land, the web app is ready for `20-gtm.md` §9.2 Show HN launch.
