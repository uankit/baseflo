# Baseflo — Frontend Architecture & Design System

Status: locked **2026-05-07** by `00-decisions.md` §10. Every choice has an ADR-style justification, considered alternatives, and a rejection rationale. Disagreements go to a Changelog entry; do not silently swap libraries.

This document is the architectural authority for the hosted web app (`app.baseflo.com`). It defers to `00-decisions.md` for organizational lock-ins, `01-architecture.md` for system context, `02-tech-stack.md` for the cross-system stack table, and `40-features/WEB-APP.md` for the feature spec, IA, and screen-by-screen behavior.

This is **not** a mockup spec. Pixel-level mockups belong in Figma; component-level mockups live in Storybook stories. This document defines the *rules of the game* before any pixel or line of TypeScript exists.

---

## 1. Why this document exists

`02-tech-stack.md` lists *what* the frontend uses (React 18, Vite, Radix, Tailwind, TanStack family, Recharts, etc.) in single-line entries. That is enough for a backend architect to skim. It is not enough to commit to a multi-month build.

This document answers *why each choice, what was rejected, and on what trigger we'd revisit*. It also defines the design-system architecture (tokens, themes, component package boundaries) and the design process (Figma → code handoff, review gates, accessibility checks). After this document is locked, the next artifact is the Figma mockup; after that, scaffolding code.

The bar: a senior engineer arriving on the project should be able to read this document end-to-end and know what the frontend looks like, why each library is here, and what the boundaries are — *without reading any code*.

---

## 2. Locked Frontend Decisions (ADR Index)

Every decision has its own subsection with: choice, alternatives considered, rejection rationale for each, revisit trigger. `02-tech-stack.md` rows are the binding summary; this section is the deep reasoning.

| # | Layer | Choice | One-line rationale |
|---|---|---|---|
| 2.1 | Framework | React 18 + Vite (SPA) | App-first, SSE-heavy, authed surface; SSR adds cost without value. |
| 2.2 | Routing | TanStack Router (file-based, typed) | Typed params + loaders; no Next-coupled router lock-in. |
| 2.3 | Server state | TanStack Query | First-class cache, retries, stale-while-revalidate; co-author with Router. |
| 2.4 | Local state | Zustand | Light, typed, no boilerplate; stays out of server-state's lane. |
| 2.5 | Forms | react-hook-form + Zod resolver | Zero re-renders by default; Zod-typed validation surface. |
| 2.6 | Schema validation | Zod | Already locked for SSE + REST validation; reuse on forms. |
| 2.7 | Styling | Tailwind + CSS variables (token preset) | Layout via classes, theming via tokens; no runtime CSS-in-JS. |
| 2.8 | UI primitives | Radix UI | Accessible-by-default; full visual control; the bar for headless primitives. |
| 2.9 | Component library | `@baseflo/ui` (shadcn-style internal lib) | We own the source; no external lock-in; brand it ourselves. |
| 2.10 | Tables | TanStack Table + TanStack Virtual | Headless + virtualized; required for big admin lists; matches admin-gen contract. |
| 2.11 | Charts | Recharts (M1); re-evaluate Vega-Lite (M2) | Recharts ships fast; Vega-Lite is more powerful but heavier — earn it later. |
| 2.12 | Code display | Shiki | Server-render-friendly; identical to VS Code grammars; no JS-based highlighter weight. |
| 2.13 | Code editing | Monaco (lazy-loaded only when entering edit context) | Same engine as VS Code; only loaded for SQL/JSON edits. |
| 2.14 | Icons | lucide-react (curated subset) | Open license, broad coverage, consistent geometry, tree-shakeable. |
| 2.15 | Animation | CSS-first; Framer Motion only when essential | Tokens-driven motion; reach for Framer for layout transitions, not button hovers. |
| 2.16 | Date/time | date-fns (pure functions; tree-shakeable) | Lighter than Luxon; first-class TS types; immutable API. |
| 2.17 | Tests (unit/component) | Vitest + Testing Library | Vite-native; fast HMR-driven tests; superset of Jest semantics. |
| 2.18 | Tests (e2e) | Playwright + `@axe-core/playwright` | Cross-browser; screenshot diff; a11y enforced in same suite. |
| 2.19 | Build / monorepo | Vite + pnpm + Turbo | Locked. Vite for dev/build; pnpm for workspace deps; Turbo for cache + task graph. |
| 2.20 | Type generation | `openapi-typescript` + custom generator for SDK + admin form schemas | One source of truth (FastAPI OpenAPI); no hand-maintained drift. |
| 2.21 | Linting / formatting | ESLint flat config + Prettier (shared in `@baseflo/config`) | Single source for rules across packages; CI gate. |
| 2.22 | SSE | native `EventSource` wrapped by reconnection layer | Browser primitive; no library churn; replay via `?seq=` per `04-database-schema.md` §4.13. |
| 2.23 | Component dev environment | Storybook 8 (separate `apps/storybook`) | Industry standard; Ladle is faster but smaller community — not worth the bet. |
| 2.24 | Visual regression | Playwright screenshot diff (built-in) | Native to test runner; no extra service; fits CI. |
| 2.25 | Bundle analysis | `rollup-plugin-visualizer` + Vite-bundle-stats CI | Per-PR bundle delta; fail on regression > 5%. |

The remainder of §2 expands each ADR. Read it in full once; reference rows 2.1, 2.7, 2.8 most often.

### 2.1 Framework — React 18 + Vite (SPA)

**Choice.** A Vite-built single-page application. No SSR, no SSG, no hybrid framework.

**Alternatives considered:**

- **Next.js (App Router or Pages Router).** SSR + ISR + Server Components + Server Actions + middleware. Rejected because: (a) Baseflo is an authenticated workspace, not a marketing or content site; SEO does not apply to authed routes. (b) The product is SSE-heavy; Server Components don't fit a streaming-conversation surface. (c) Server Actions duplicate the FastAPI backend's role; we'd be building two backends. (d) Next adds a deploy-time, runtime, and mental-model coupling we don't need. (e) Tauri v2 desktop wrap (M5+) is harder with Next; trivial with Vite static output. (f) Founder familiarity with Next's mental model varies; Vite's surface is small. (g) Edge runtime constraints mean less for an authed app.
- **Remix (React Router v7).** Better data-loader story than Next, no RSC coupling. Rejected because: (a) Same SSR-without-need argument. (b) TanStack Router gives us typed loaders without the SSR overhead. (c) Smaller community than React Router v6+TanStack ecosystem we already use elsewhere.
- **Astro (with React islands).** Excellent for content sites. Rejected: an authed workbench is the opposite of a content site; the islands model fights against deeply interactive workspace state.
- **SvelteKit / SolidStart / Qwik.** Mature enough for production. Rejected: founder + engineer familiarity is React; switching frameworks just to "feel modern" trades known unknowns for unknown unknowns. Pydantic AI's React-related ecosystem (TanStack family, Radix, Recharts) is what we lean on hardest.
- **Vanilla React + Webpack / Parcel / Rollup.** Vite is a Rollup-based bundler with a Webpack-compatible plugin surface and a faster dev experience. No reason to pick anything else when Vite covers the same ground.

**Trade-offs accepted:**

- Marketing site (`baseflo.com`) is a *separate* deployment per `30-features.md` §P (`WEB-MARKETING`, M2). Astro on Cloudflare Pages is the leading candidate; that's a separate ADR at M2.
- Public share page (`/s/{token}`) lives inside the same SPA. SEO indexing is not a goal; a small SSR variant for share pages is logged as Open Question §9.2 if first-customer demand arrives.
- Initial bundle is larger than a server-rendered first page. Mitigated by per-route code-splitting (TanStack Router lazy routes) and a 250 KB gzipped initial bundle budget (per `40-features/WEB-APP.md` §11).

**Revisit trigger:** if shareable / publicly indexable surfaces grow into the product (M3+ enterprise lead-gen pages), evaluate moving share + marketing to Astro and keeping the auth'd app on Vite. Do **not** migrate the auth'd app to a hybrid framework.

### 2.2 Routing — TanStack Router (file-based, typed)

**Choice.** TanStack Router with file-based routes + typed params + typed loaders + typed search params. Routes live under `apps/web/src/routes/`.

**Alternatives:**

- **React Router v6+.** Mature, ubiquitous, typed via Data API. Rejected because: TanStack Router's loaders + search-param schemas + per-route error boundaries fit our model better; type inference for params is more thorough; loader-first design eliminates `useEffect`-based fetches.
- **Wouter / Reach Router.** Too minimal; we need data-loader semantics.
- **Next App Router.** Tied to Next; not portable. Rejected with the framework choice (§2.1).
- **Hand-rolled.** A perennial mistake.

**Why TanStack Router specifically:**

- File-based, but you can opt out per route. We use file-based for auth + workspace + share + saga; programmatic for nested admin tabs (driven by `AdminUISpec`).
- Typed search params via Zod schemas: `?refine=open&seq=42` is type-safe end-to-end.
- Pending and error components per route, eliminating the loading-state spaghetti pattern.
- Route loaders integrate with TanStack Query's queryClient — one cache, two reads.
- No SSR coupling; same code works in local dev, hosted SPA, and Tauri desktop.

**Revisit trigger:** if the desktop wrap (M5+) needs deep-link routing different from web, evaluate at that point — TanStack Router's transport-agnostic API likely makes it a non-issue.

### 2.3 Server state — TanStack Query

**Choice.** TanStack Query (React Query v5+) for every server-fetched resource. Query keys are typed; mutations use `useMutation` with optimistic updates where safe.

**Alternatives:**

- **SWR.** Smaller, simpler. Rejected: we need the deeper feature surface (mutations, query invalidation graphs, optimistic updates with rollback, suspense integration, infinite-query). SWR can do it, but TanStack Query is the leader.
- **Apollo Client / urql.** GraphQL-native. Rejected: we expose REST + SSE, not GraphQL (deferred to M5+ per `30-features.md` `API-GRAPHQL`).
- **RTK Query.** Bundled with Redux Toolkit. Rejected with Redux (§2.4).
- **Direct fetch + `useEffect`.** The thing we're paying TanStack Query to avoid.

**Conventions:**

- Query keys are objects, not strings: `["org", orgSlug, "projects"]`.
- Stale times default to 30 seconds; resources that change faster (saga events, audit log) bypass cache and stream.
- Optimistic updates only on operations the server confirms quickly (rename project, toggle archive). Refinements + exports go through their own job-status polling.
- Cache hydration: route loaders pre-fill the cache; components subscribe via `useQuery` with the same key.

### 2.4 Local state — Zustand

**Choice.** Zustand for cross-component UI state inside a feature. One store per feature (or per shell concern).

**Alternatives:**

- **Redux Toolkit.** Powerful, well-tooled. Rejected: too heavy for a UI store; the boilerplate-to-value ratio is bad when we don't have global server-state in Redux either (TanStack Query owns that).
- **Jotai / Recoil.** Atom-based. Rejected: marginal differences from Zustand for our use; team familiarity with Zustand is higher.
- **React Context only.** Too coarse for cross-feature ephemeral state (theme, command palette, refine-rail open).

**Boundary rules:**

- Server data is **never** in Zustand. TanStack Query is authoritative.
- Zustand stores live next to the feature folder when feature-scoped (`features/refine-panel/store.ts`), or in `shared/` when cross-feature (`shared/stores/themeStore.ts`).
- Selectors are the public surface; never expose `set` outside the store module.

### 2.5 Forms — react-hook-form + Zod resolver

**Choice.** `react-hook-form` for form state + `@hookform/resolvers/zod` for validation against Zod schemas defined in `@baseflo/contracts`.

**Alternatives:**

- **Formik.** Older API, more re-renders, less typed. Rejected.
- **TanStack Form.** Newer; promising. Rejected for v1: less production-tested with Radix UI primitives. Revisit at M3.
- **Conform.** Server-first; works best with Remix/Next form actions. Doesn't fit a Vite SPA + REST backend.
- **Native HTML forms only.** We need cross-field validation, complex nested forms (connector install, settings), and typed error messages — native forms get verbose.

### 2.6 Schema validation — Zod

**Choice.** Zod for: SSE payload validation at decode time, REST response validation for safety-critical paths, form schemas, URL search-param schemas in TanStack Router.

**Alternatives:**

- **Yup.** Older; less TS inference; OK but Zod is the new standard.
- **Valibot.** Smaller bundle, similar API. Reasonable; we may revisit if bundle size becomes critical.
- **No runtime validation.** The frontend would silently break on backend contract drift. Not acceptable for production.

**Convention:** every type that crosses the network boundary has a Zod schema in `@baseflo/contracts`. The TS type is derived from the schema (`type X = z.infer<typeof XSchema>`). Adding a backend field is two lines: schema + regen.

### 2.7 Styling — Tailwind + CSS variables (token preset)

**Choice.** Tailwind CSS for utility classes (layout, sizing, responsiveness, breakpoints); CSS custom properties (`--color-*`, `--space-*`, `--radius-*`) for design tokens; the Tailwind config consumes the tokens. Components in `@baseflo/ui` reference tokens through Tailwind classes, never hex.

**Alternatives:**

- **CSS Modules.** Scoped styles; works fine. Rejected: more file overhead per component; harder to enforce "use the token, not a hex" through tooling.
- **Vanilla Extract.** Type-safe CSS-in-TS. Rejected: build complexity; Tailwind's atomic-class model is faster for our team.
- **Emotion / styled-components.** Runtime CSS-in-JS. Rejected: runtime cost; SSR concerns; we lean static.
- **Panda CSS / StyleX.** Newer; promising. Rejected: too new; Tailwind ecosystem is huge and well-documented.
- **Plain CSS files.** Doable but the team velocity gain from Tailwind is substantial.

**Token-via-Tailwind pattern (binding):**

```css
/* tokens.css */
:root {
  --color-accent: hsl(217 91% 60%);
  --color-bg: hsl(220 20% 98%);
  --space-4: 1rem;
  --radius-md: 6px;
}
```

```ts
// tailwind.config.ts (excerpt)
export default {
  theme: {
    extend: {
      colors: {
        accent: 'hsl(var(--color-accent) / <alpha-value>)',
        bg: 'hsl(var(--color-bg) / <alpha-value>)',
      },
      spacing: {
        4: 'var(--space-4)',
      },
      borderRadius: {
        md: 'var(--radius-md)',
      },
    },
  },
};
```

Component code:

```tsx
<button className="bg-accent text-white rounded-md px-4 py-2"> ... </button>
// not: bg-blue-500
// not: style={{ backgroundColor: '#3b82f6' }}
```

ESLint rule (custom): `no-tailwind-color-literal` forbids any color class outside the registered semantic palette. Same for spacing / radius / shadow.

### 2.8 UI primitives — Radix UI

**Choice.** Radix UI for every accessible primitive: `Dialog`, `Popover`, `Tooltip`, `DropdownMenu`, `ContextMenu`, `Tabs`, `Accordion`, `Collapsible`, `Select`, `RadioGroup`, `Checkbox`, `Switch`, `Slider`, `Toggle`, `ToggleGroup`, `Toolbar`, `ScrollArea`, `AlertDialog`, `HoverCard`, `Avatar`, `Progress`, `Toast`.

**Alternatives:**

- **Headless UI.** Tailwind Labs' offering. Smaller surface; less mature than Radix; rejected.
- **Ariakit.** Excellent; comparable to Radix on accessibility. Rejected on community/ecosystem size; Radix has more docs, more examples, more team familiarity.
- **Reach UI.** Older; less actively maintained.
- **Hand-rolled.** Accessibility is hard; rolling Dialog from scratch invites bugs. Forbidden for primitives that exist in Radix.

**Wrapping rule:** every Radix primitive used in the app is wrapped once in `@baseflo/ui` with our token classes. App code imports from `@baseflo/ui`, never from `@radix-ui/*` directly. Reason: if we ever swap Radix for Ariakit, only `@baseflo/ui` changes.

### 2.9 Component library — `@baseflo/ui` (shadcn-style internal)

**Choice.** A first-party component library inside our monorepo. Source-available to ourselves; copy-in pattern for primitives (we own the source); composite components follow.

**Alternatives:**

- **MUI / Material-UI.** Heavier, harder to brand. Rejected per `02-tech-stack.md`.
- **Chakra UI.** Decent; similar weight to MUI. Rejected: brand dilution; Tailwind already covers the layout primitives.
- **Mantine.** Solid; ships many primitives. Rejected: built-in styling collides with Tailwind; would force a binary choice.
- **shadcn/ui (the published collection).** Use the *pattern*, not the package — copy components into our repo and adapt. The shadcn CLI is fine for bootstrapping; it does not become a runtime dependency.

**Boundary:**

```
packages/ui/
├── src/
│   ├── primitives/        ← Radix wraps
│   ├── composites/        ← StatusPill, KPIWidget, AttributionBadge, PIIField, ...
│   ├── layouts/           ← Shells (App, Auth, Workspace, Saga, Share, Settings)
│   ├── charts/            ← Recharts wraps
│   ├── tables/            ← TanStack Table wraps
│   ├── code/              ← Shiki + lazy Monaco wraps
│   ├── icons/             ← lucide curated re-exports
│   └── tokens/            ← tokens.css + Tailwind preset
├── stories/               ← Storybook stories per component
└── package.json
```

**Versioning:** `@baseflo/ui` ships in lockstep with the web app for v1. No external publish. SemVer applied per major change to design tokens (breaking) or component prop API (breaking).

### 2.10 Tables — TanStack Table + TanStack Virtual

**Choice.** TanStack Table v8 for headless table logic; TanStack Virtual for row + column virtualization; rendered by our `<DataTable>` composite in `@baseflo/ui/tables`.

**Alternatives:**

- **ag-grid.** Powerful; spreadsheet-like. Rejected: licensing (community vs enterprise); brand mismatch (heavy); brand-control limited.
- **react-table v7.** Older API; replaced by TanStack Table v8 (same author).
- **Material Table / Mantine Table.** Visual lock-in.

**Required behavior** (per `40-features/WEB-APP.md` §5.8 + `ADMIN-GEN.md`):

- Sort + filter per column (pluggable widgets driven by `WidgetKind`).
- Pagination + infinite scroll (server-side).
- Row virtualization for >500 rows.
- Keyboard nav (arrow + tab + enter).
- Multi-source attribution badge per row.
- PII column rendering via `<PIIField>`.

### 2.11 Charts — Recharts (M1); Vega-Lite re-evaluated M2

**Choice.** Recharts for v1 (bar, line, area, KPI sparklines, gauge). All wrapped with brand tokens in `@baseflo/ui/charts`.

**Alternatives:**

- **Vega-Lite.** More expressive; declarative spec. Defer to M2 for analytics tab where we may need richer compositions.
- **Visx.** Lower-level; D3-on-React. Useful when we need a custom chart Recharts can't do; not needed in v1.
- **Nivo.** Heavy; opinionated styling.
- **Victory.** OK; less momentum.
- **Plot (Observable).** Very nice for quick exploratory plots; not for product UI.

**Convention:** every chart accepts only typed data (no `any`); empty / loading / error states are required props; legends + accessible descriptions are mandatory.

### 2.12 Code display — Shiki

**Choice.** Shiki for read-only syntax highlighting (SQL, JSON, YAML, TS in docs/help).

**Alternatives:**

- **Prism / highlight.js.** Older; weaker grammars; results visibly diverge from VS Code.
- **Server-side highlight via Pygments.** No reason to add a server dependency for client display.

**Why Shiki:** uses TextMate grammars (same as VS Code); identical highlighting for users who copy-paste back into their editor; reasonable bundle size when pre-loaded grammars are limited to our actual languages.

### 2.13 Code editing — Monaco (lazy-loaded)

**Choice.** Monaco editor for any *editable* code surface (custom KPI SQL editor in M3+; connector custom-mapping editor in M3+). Lazy-loaded via dynamic import only when an edit context is entered.

**Alternatives:**

- **CodeMirror 6.** Lighter; more flexible; modern API. Reasonable; revisit if Monaco's bundle becomes a problem. For v1, the lazy-load makes Monaco's weight irrelevant.
- **Lexical.** Rich-text-first; not the right fit for code.

### 2.14 Icons — lucide-react (curated subset)

**Choice.** lucide-react. Re-exported by name from `@baseflo/ui/icons`; ad-hoc imports of `lucide-react` outside that package forbidden by ESLint.

**Alternatives:**

- **Heroicons.** Tailwind Labs; smaller set.
- **Tabler Icons.** Comparable to lucide; less broad.
- **Phosphor Icons.** Different geometry; overkill for our needs.

### 2.15 Animation — CSS-first; Framer Motion only when essential

**Choice.** CSS transitions and `View Transition API` are the default. Framer Motion is allowed only for layout transitions where CSS cannot express the animation cleanly (saga stage rail expanding, refine rail sliding in).

**Alternatives:**

- **Framer-motion-everywhere.** Tempting but heavyweight; not needed for hover states.
- **GSAP.** Out of scope; heavy.
- **react-spring.** Comparable to Framer; less momentum lately.

**Rule:** an animation must (a) communicate state change or (b) provide spatial continuity. Decorative animations are forbidden. `prefers-reduced-motion` always honored.

### 2.16 Date/time — date-fns

**Choice.** date-fns for parsing, formatting, arithmetic. Times rendered with `Intl.DateTimeFormat`.

**Alternatives:**

- **Day.js.** Smaller; chainable API. OK; date-fns is more functional and tree-shakes better.
- **Luxon.** Strongest tz support. We don't need that level for v1; backend handles tz.
- **Moment.** Deprecated.

### 2.17 Tests (unit/component) — Vitest + Testing Library

**Choice.** Vitest as runner; `@testing-library/react` + `@testing-library/user-event` for component tests. Coverage via `v8` provider.

**Alternatives:**

- **Jest.** Slower with Vite stack; ESM friction. Rejected: Vitest is faster + Vite-native.
- **Web Test Runner.** Decent; smaller community.
- **Bun test.** Promising; still maturing.

### 2.18 Tests (e2e) — Playwright + axe-core

**Choice.** Playwright. `@axe-core/playwright` runs on every test to enforce WCAG 2.1 AA. Visual regression via Playwright's built-in screenshot comparison.

**Alternatives:**

- **Cypress.** Decent UX; slower; weaker multi-tab support; smaller browser matrix.
- **Selenium.** Heavy.
- **Puppeteer.** Chromium-only; Playwright supersedes.

### 2.19 Build / monorepo — Vite + pnpm + Turbo

**Choice.** Vite per app; pnpm workspaces for inter-package deps; Turbo for task graph + caching.

**Alternatives:**

- **npm workspaces.** Slower; weaker hoisting story.
- **yarn (modern).** Decent; pnpm is faster + more disk-efficient.
- **Nx.** Heavier; brings opinions we don't need. Turbo is enough.
- **Bazel.** Massively over-engineered for our scope.

### 2.20 Type generation — `openapi-typescript` (+ custom generators)

**Choice.** `openapi-typescript` to generate REST request/response types from FastAPI's OpenAPI document. A custom generator in `packages/contracts/codegen/` produces SDK methods + admin form schemas from the same source.

**Alternatives:**

- **orval.** Generates SDK methods directly; opinionated React Query hooks. Reasonable; we may adopt for the SDK package generator.
- **datamodel-code-generator.** Python-only.
- **Hand-written.** Forbidden — drift was flagged in the prior audit.

**Convention:** the generated file is committed (`packages/contracts/src/generated/`). PR diff shows server-driven changes.

### 2.21 Linting / formatting — ESLint flat config + Prettier

**Choice.** ESLint v9 flat config; Prettier for formatting; shared rules in `packages/config/eslint/` + `packages/config/prettier/`.

**Custom rules** (added by us):
- `import/no-restricted-paths`: routes can't import transports; UI can't import gateways; agents can't import connectors (server-side; same flat-config style).
- `no-tailwind-color-literal`: Tailwind classes must use semantic tokens (no `bg-blue-500`).
- `jsx-a11y/*`: standard a11y rules; one exception per file requires a justifying comment.

### 2.22 SSE — native `EventSource` + reconnection wrapper

**Choice.** Native `EventSource` API. A small wrapper in `@baseflo/api-client/src/sse.ts` adds: `?seq=` resumption, exponential backoff on disconnect, max-retries policy, structured event decoding via Zod.

**Alternatives:**

- **`sse.js`.** Polyfill for older browsers + adds POST support. Not needed; Baseflo only supports current browsers + `EventSource` is available.
- **WebSocket.** Bidirectional but more complex; overkill for our one-way streaming. Defer to M5+ if a real-time collaboration feature requires it.
- **Long-polling.** Strictly worse on every axis.

### 2.23 Component dev environment — Storybook 8

**Choice.** Storybook 8 in a separate `apps/storybook` Vite app, sharing components from `@baseflo/ui`.

**Alternatives:**

- **Ladle.** Faster; smaller community. Reasonable; not worth the bet for a long-running project.
- **Histoire.** Nice; ecosystem smaller.

**Convention:** every composite component in `@baseflo/ui` ships at least one story per state (loading, empty, ready, warning, error). Stories double as component tests via Storybook's testing addon.

### 2.24 Visual regression — Playwright screenshots

**Choice.** Playwright's built-in `toHaveScreenshot()` for canary screens (5–10 per release). Diff threshold: 0.1% pixel delta; manual review on diff.

### 2.25 Bundle analysis — `rollup-plugin-visualizer` + CI delta

**Choice.** Per-PR bundle size diff via Vite's stats output, posted as a GitHub PR comment. Hard CI fail on regression > 5% on initial bundle or > 10% on any per-route chunk.

---

## 3. Why NOT Next.js (extended)

The user named Next as a candidate. The full reasoning, since it's the most-asked alternative:

| Concern | Next.js | Vite + TanStack | Verdict |
|---|---|---|---|
| Authenticated workspace UX | Possible; SSR adds little | Native fit | Vite |
| SEO of marketing pages | Excellent (RSC, ISR) | Separate Astro deploy | Next would force a single deploy; we want separation |
| SSE handling | Works; not the strength | Native fit; clean Vite + EventSource | Vite |
| Server-Action / mutation story | Strong server-actions | Plain REST through FastAPI | Vite (we have a real backend) |
| Cold-start (edge runtime) | Fast | N/A | Tied |
| Local dev speed | Slower; Next dev compiles routes | Vite HMR is instant | Vite |
| Bundle size on first paint | Smaller (SSR HTML) | Larger initial JS | Next; mitigated by route splitting |
| Tauri / desktop wrap path | Hard (Next's runtime + RSC) | Trivial (static export) | Vite |
| RSC mental model | New, evolving | Mature SPA model | Vite (de-risk) |
| Vendor lock-in (Vercel) | Real but escapable | None | Vite |
| Routing typing | Good (App Router) | Better (TanStack typed loaders) | Vite |
| Streaming + Suspense | Excellent | Equivalent via Suspense + TanStack Query | Tied |
| Hire-ability of engineers | Higher | High | Slight Next edge; immaterial at our size |
| Migration cost away from it | Painful | Zero (it's just a Vite SPA) | Vite |
| Image optimization | Built-in | Manual | Next; mitigated by sharp images at build |

**Summary:** Next is the right answer when SEO, edge SSR, or a content-site is the dominant use case. Baseflo is the opposite: an authed workbench with SSE streams, a desktop-wrap target, and a real backend. Vite is a better fit on every axis except marketing-site SEO — which we solve by keeping `baseflo.com` on a separate Astro deployment.

If a future product surface becomes content-heavy and needs SEO at scale, we'd add Astro for that surface, not migrate the auth'd app to Next.

---

## 4. Design System Architecture

### 4.1 Token taxonomy

All tokens are CSS custom properties. Categories:

| Category | Prefix | Examples |
|---|---|---|
| Color (semantic) | `--color-*` | `--color-bg`, `--color-fg`, `--color-accent`, `--color-success`, `--color-private` |
| Typography | `--font-*`, `--text-*`, `--leading-*`, `--tracking-*` | `--font-sans`, `--text-base`, `--leading-tight` |
| Space | `--space-*` (4px base) | `--space-1` (0.25rem) … `--space-12` (3rem) |
| Radius | `--radius-*` | `--radius-sm` (4px), `--radius-md` (6px), `--radius-lg` (8px), `--radius-pill` |
| Shadow | `--shadow-*` | `--shadow-sm`, `--shadow-md`, `--shadow-lg` |
| Motion | `--motion-*` | `--motion-fast` (120ms), `--motion-normal` (200ms), `--motion-slow` (320ms) |
| Z-index | `--z-*` | `--z-sticky`, `--z-overlay`, `--z-modal`, `--z-toast`, `--z-tooltip` |
| Density | `--density-*` | `--density-compact`, `--density-comfortable` (M2+) |

**Rules:**

- No hex literals in component code. ESLint enforces.
- No hardcoded `px` values in component code, except `1px` borders. Use `--space-*` units.
- Tokens are *semantic*, not visual. We have `--color-success`, not `--color-green`. Color values can change; the meaning doesn't.
- Token *additions* are non-breaking (`@baseflo/ui` minor bump). Token *removals or visual changes* are breaking (major bump).

### 4.2 Theme strategy

- **v1: light only.** Per `20-gtm.md` §8.2 (light-first, neutral, calm).
- **Dark mode: prepared in M0, shipped in M3.** Implementation detail: `:root[data-theme="dark"]` overrides token values; component code never branches on theme.
- **No system-default override yet.** User toggle in user menu; persists to `localStorage` per `40-features/WEB-APP.md` §19.
- **High-contrast mode:** considered for M5+ when accessibility audit feedback arrives.

### 4.3 Component categorization

```
Tier 1 — Primitives (Radix wraps + tokens)
   Button, Input, Textarea, Checkbox, Switch, Radio, Select, Slider,
   Dialog, Popover, Tooltip, DropdownMenu, ContextMenu, Menu,
   Tabs, Accordion, Collapsible, Toggle, ToggleGroup, Toolbar,
   ScrollArea, AlertDialog, HoverCard, Avatar, Progress, Toast, Separator

Tier 2 — Composites (built from primitives)
   StatusPill, ValidationBadge, RoleBadge, PlanBadge, DeploymentModeBadge,
   AttributionBadge, PIIField, MoneyCell, StatusChip, ConnectionDot,
   KPIWidget, MetricStrip, EmptyState, ErrorCallout, LoadingSkeleton,
   OnboardingStep, StageRailItem, AgentActivityRow, ArtifactPreviewCard,
   RefinePlanCard, ShareLinkCard, AuditRow, CommandPalette,
   ConfirmDestructive, CodePanel (Shiki), EditorPanel (lazy Monaco),
   FormField, FormError, FormSection

Tier 3 — Patterns (multi-component compositions)
   SignInCard, ConnectorCard, ConnectorInstallModal, SagaStageRail,
   WorkspaceSideNav, WorkspaceTopBar, RefineRail, SettingsSidebar,
   AuditLogTable, MembersTable, BillingPanel, OnboardingWizard,
   ShareLinkBuilder, ExportRequestPanel

Tier 4 — Templates (full-page layouts)
   AuthShell, AppShell, WorkspaceShell, SagaShell, ShareShell, SettingsShell
```

A component graduates a tier when it's used in 3+ places. Below that, it lives in the consuming feature folder.

### 4.4 `@baseflo/ui` package boundary

| Lives in `@baseflo/ui` | Lives in feature folders |
|---|---|
| Primitives | Feature-specific compositions |
| Composites used in 3+ places | Feature views (e.g., `ConnectorHubView`) |
| Layout shells | Route-bound page components |
| Tokens | Local feature stores |
| Charts (generic) | Feature-specific chart configs |
| Tables (generic) | Feature-specific column configs |

Rule of thumb: if the component is reusable and visual, it's in `@baseflo/ui`. If it knows about a route, an API endpoint, or a feature's domain logic, it lives in the feature folder.

### 4.5 Versioning (within the monorepo)

- `@baseflo/ui` is internal-only for v1. Versioned in `package.json` for changelog clarity, but not published externally.
- Major bump = breaking visual change or component prop API change. Triggers a manual visual-regression review.
- Minor bump = additive (new component, new variant, new token).
- Patch = bug fix, internal refactor with no visual or API change.
- Storybook deploys from the latest commit on `main`; visual regressions fail CI.

### 4.6 Brand: name, wordmark, voice

- **Name:** `Baseflo` (no `w`). Per `00-decisions.md` §1.
- **Wordmark:** lowercase `baseflo` in `Inter` (or final brand font, TBD post-M2). One accent dot or ligature acceptable; nothing more.
- **Voice:** Per `20-gtm.md` §8 and `40-features/WEB-APP.md` §7.4 — plain English, calm confidence, builder energy. Specific over general. Honest over clever.
- **Logo:** none in v1 beyond the wordmark. A monochrome glyph derived from the wordmark may ship in M2 for favicon + small-format use.

### 4.7 Visual reference points

We borrow *qualities*, not visuals, from these products:

| Reference | What we borrow |
|---|---|
| **Linear** | Restraint; keyboard-first; command palette; low visual noise; tabular numbers in tables. |
| **Stripe Sigma / Dashboard** | Calm confidence; SQL-friendly; precise; dense-but-breathable. |
| **Metabase** | Approachable BI; share-link clarity; chart honesty (axis labeling). |
| **Hex / Notion data tools** | Inspectable detail; expandable sections; narrative-plus-output. |
| **Vercel + Stripe security pages** | Calm trust posture; no fear-based copy; precise language. |

We do **not** borrow visuals from any of them. Baseflo's surface is its own.

### 4.8 Visual non-goals (anti-pattern fence)

Updated 2026-05-08 per `00-decisions.md` Changelog. The line has shifted from "no motion / no glow at all" to **"decoration vs state-bearing"** — motion and accent-glow are allowed when they communicate live state, real progress, or a trust moment, and forbidden when they're decoration.

**Allowed (state-bearing — motion has a job):**

- ✅ Soft accent ring / pulse on the currently-running agent stage (communicates "thinking now").
- ✅ Live-ticking token / latency counters (communicate real progress).
- ✅ Count-up animation on trust numbers (unique entities, duplicates resolved, KPI deltas) on first reveal.
- ✅ Slide-in motion when a fresh artifact lands or a new activity entry arrives.
- ✅ Subtle pulse on a connector chip while it's actively syncing.
- ✅ Editorial serif (`font-serif`) on moments of trust or reveal — sign-in headline, workspace.ready hero, the unified-customer count on first workspace open, share-page summary, refinement plan title.
- ✅ Two registers in one app: **calm** in tables / admin / settings (where users live for 30+ minutes), **confident-with-motion** at agent activity, reveal moments, and trust signals.

**Still forbidden:**

- ❌ Purple → pink AI gradients.
- ❌ Glassmorphism / blur backgrounds.
- ❌ Decorative glow that doesn't communicate state.
- ❌ Neon-on-dark "futuristic" palettes.
- ❌ Multiple icon families on one screen.
- ❌ Cards inside cards (one elevation layer per pane).
- ❌ Marketing-hero composition inside settings or admin tabs (workspace.ready and the saga viewer are explicitly hero moments — exempt).
- ❌ Dark side-nav + light main (no inverse-themed regions).
- ❌ Loading spinners as the only loading state.
- ❌ Toasts that auto-dismiss critical info.
- ❌ Color-only state (every status conveys via color + icon + label).
- ❌ Animations that play without a triggering event (`prefers-reduced-motion: reduce` always honored — motion is replaced with instant transitions, not approximated).
- ❌ Decorative chart axes (grid lines without ticks; gradients without legend).
- ❌ "Powered by AI" badges, "magic" sparkles, robot icons.

---

## 5. Design Process / Flow

The discipline by which design moves from idea to shipped UI. Every step is enforceable; every deviation requires a comment.

### 5.1 Tools

| Concern | Tool | Notes |
|---|---|---|
| Mockups | Figma | Single org-shared file per milestone (`Baseflo / Web M0`, `Web M1`, …); pages per shell. |
| Tokens (design-side) | Tokens Studio for Figma | Reads/writes design tokens to a JSON file in the repo. |
| Token sync (code-side) | Style Dictionary (or hand-coded if small) | Reads the JSON; emits `tokens.css`, Tailwind preset, TS constants. |
| Component dev | Storybook 8 | `apps/storybook`; deployed per-PR for review. |
| Accessibility check (design-time) | Stark plugin in Figma + manual contrast check | Designer responsibility before handoff. |
| Accessibility check (code) | `@axe-core/playwright` + `eslint-plugin-jsx-a11y` | CI gate; engineer responsibility. |
| Visual regression | Playwright screenshots | CI on canary screens. |
| Copy review | Linear ticket per screen; ux-writing reviewer | Founder is final approver until a writer joins. |

### 5.2 Token sync flow

```
  Designer in Figma (Tokens Studio plugin)
              │
              ▼
  packages/ui/src/tokens/tokens.json   ← committed to git
              │
              ▼
  Style Dictionary build
              │
              ├──► packages/ui/src/tokens/tokens.css
              ├──► packages/ui/src/tokens/tailwind-preset.ts
              └──► packages/ui/src/tokens/index.ts (TS exports)
              │
              ▼
       app components consume via Tailwind classes
              │
              ▼
  Playwright visual-regression confirms no drift
```

**Rule:** designers commit `tokens.json` via PR; engineers regenerate the artifacts. PRs that change visual output without a tokens.json change fail CI (token-drift detector).

### 5.3 Design ↔ code handoff

Per-screen handoff package (in Figma):

1. **Frame** with the canonical breakpoint (1280px workspace; 640px share page; 480px auth).
2. **States layer**: loading, empty, ready, warning, error, disabled — visible on the same frame as variants.
3. **Annotations layer**: spacing tokens, type tokens, color tokens, motion tokens called out.
4. **Component map**: each region annotated with the `@baseflo/ui` component that renders it.
5. **Copy block**: every string in the frame, ready to go to `packages/i18n/src/en.ts`.
6. **Accessibility map**: tab order, ARIA roles, screen-reader labels.
7. **Edge-case list**: what happens at 0, 1, many, max, error.

The engineer's job is to *match the frame*, not *re-design*. If the frame is wrong, the engineer raises a comment in the Figma frame; the designer fixes; re-handoff.

### 5.4 Design review gates

Each screen passes through gates in order:

1. **Designer self-review.** Token usage, component reuse, state coverage, contrast, text-truncation cases.
2. **Founder review.** Brand voice, business clarity, anti-pattern check.
3. **Engineer feasibility review.** Backend data shape availability, SSE handling, performance budget impact.
4. **Accessibility review.** Designer + engineer pair; Stark contrast pass + keyboard tab order.
5. **Copy review.** Founder until a UX writer joins; voice + honesty + clarity.

Failure at any gate routes back to design — never silent merge of a half-reviewed screen.

### 5.5 Component implementation lifecycle

```
1. Spec exists in 40-features/<feature>.md (HLD + LLD + states)
            │
2. Designer produces Figma frame + token annotations + state coverage
            │
3. Engineer creates failing test in packages/ui/tests/<Component>.test.tsx (TDD-first)
            │
4. Engineer implements component in packages/ui/src/<tier>/<Component>.tsx
            │
5. Engineer writes Storybook stories per state (loading/empty/ready/warning/error)
            │
6. Engineer + designer review in Storybook deploy URL on the PR
            │
7. Accessibility review: axe pass in Storybook test addon
            │
8. Visual regression: Playwright snapshot baseline accepted on the PR
            │
9. Component graduated to @baseflo/ui; consumed by feature folder
            │
10. App-level integration test (Playwright golden-path) covers the feature flow
```

No skipping. Especially not steps 3, 7, or 9.

### 5.6 Visual QA

Per release:

- All canary screens (sign-in, welcome, org dashboard, project create, connector hub, saga viewer, workspace overview, refine panel, exports, share page, settings) reviewed in Figma vs deployed Storybook + app at three viewport sizes (1280, 1440, 1920).
- Visual regression diff > 0.1% requires manual approval with a reason in the PR.

### 5.7 Accessibility design-time checks

Designer's responsibility before handoff:

- All foreground/background combinations meet 4.5:1 (text) and 3:1 (UI). Stark plugin verifies.
- Focus rings designed and visible.
- Tab order makes sense; designer numbers focusable elements on the annotation layer.
- Touch targets ≥ 44×44px.
- Status conveyed by color + icon + label (never color alone).
- Charts have a tabular-data alternative shown by default or on a clear toggle.

Engineer's responsibility post-handoff:

- `@axe-core/playwright` on every Playwright test.
- `eslint-plugin-jsx-a11y` clean.
- Manual screen-reader pass (NVDA + VoiceOver) on every primary flow per release.

### 5.8 Copy review (UX writing)

Inherits from `40-features/WEB-APP.md` §7.4. Process:

1. Designer fills the copy block on the Figma frame.
2. Engineer copies into `packages/i18n/src/en.ts` keyed by `<feature>.<screen>.<element>`.
3. Founder reviews voice + accuracy.
4. Edge-case copy (errors, empty states, confirmations) reviewed alongside the happy-path copy.

Voice rules already locked in WEB-APP.md §7.4 are binding here.

### 5.9 Versioning + release process

- **Web app version** matches the engine's milestone number (M0, M1, M2, …).
- **`@baseflo/ui` version** is independent SemVer; pinned by the consuming app per release.
- **Design tokens** changes ship via the token-sync flow; a major-version bump triggers visual regression review.
- **Component breaking changes** ship behind a deprecation window: 1 release with both old + new exported; one release with a console.warn; one release with the removal.

---

## 6. Architectural Boundaries (enforced)

These are not guidelines. They are enforced by ESLint rules and CI gates. Violations are not mergeable.

| Boundary | Enforcement |
|---|---|
| Routes cannot import transports | ESLint `import/no-restricted-paths` |
| UI components cannot import gateways | ESLint `import/no-restricted-paths` |
| App code cannot import `@radix-ui/*` directly | ESLint `import/no-restricted-imports` |
| App code cannot import `lucide-react` directly (must go through `@baseflo/ui/icons`) | ESLint `import/no-restricted-imports` |
| Feature folders cannot import each other; they share via `shared/` | ESLint `import/no-cycle` + path restrictions |
| Component code cannot use hex literals or arbitrary Tailwind colors | Custom ESLint rule `no-tailwind-color-literal` |
| Component code cannot use hardcoded px values (except 1px borders) | Custom ESLint rule (added M0) |
| `dangerouslySetInnerHTML` is forbidden outside the registered Shiki render component | ESLint `react/no-danger` exception list |
| `console.log` is forbidden in source code | ESLint rule; logs go through `@baseflo/api-client/src/logger.ts` |
| `any` is forbidden | `@typescript-eslint/no-explicit-any` |
| Test files (`*.test.ts(x)`) must exist for every component, hook, and service | CI script counts pairings |

Adding a new boundary rule requires a Changelog entry in `00-decisions.md`.

---

## 7. The Stack at a Glance

```
┌──────────────────────────────────────────────────────────────────────┐
│  USER                                                                 │
│    Browser (Chrome / Safari / Firefox / Edge — current versions)     │
└──────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌──────────────────────────────────────────────────────────────────────┐
│  REACT 18 + VITE  (apps/web)                                         │
│                                                                       │
│   TanStack Router (file-based, typed)                                 │
│      ↓                                                                │
│   TanStack Query (server cache)  +  Zustand (UI state)               │
│      ↓                                                                │
│   Feature folders (services / hooks / components)                    │
│      ↓                                                                │
│   @baseflo/ui  (Radix + Tailwind + tokens; primitives → composites   │
│                  → patterns → templates)                              │
│      ↓                                                                │
│   @baseflo/api-client  (gateway; transports: REST + SSE + placeholder)│
│      ↓                                                                │
│   @baseflo/contracts  (Zod schemas + generated types)                │
│      ↓                                                                │
│   @baseflo/error-system  (BF-WEB-NNN registry + normalizer)          │
│                                                                       │
│   @baseflo/sdk  (public dev SDK; reused inside the app)              │
└──────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
                          FastAPI (server)
                          REST + SSE
```

Tooling: pnpm + Turbo + Vitest + Playwright + Storybook + ESLint + Prettier + axe + Lighthouse CI.

---

## 8. Open Questions

Logged here, locked at the noted milestone.

1. **Marketing site stack.** Astro vs Next vs static-Vite; default Astro. Locked at M2.
2. **Real-time multi-cursor collaboration on workspace edits.** Optimistic locking only in v1; CRDT-style collab evaluated M3+.
3. **Sentry session replay.** Privacy-sensitive. Decision M2 with explicit per-org opt-in.
4. **Feature-flag system.** Self-hosted unleash vs LaunchDarkly vs hand-rolled. Decision M2.
5. **Public share-page SEO/SSR.** A small SSR variant for `/s/{token}` pages may be added in M3 if customer demand surfaces. Until then, share pages are SPA-rendered with dynamic `<title>` + meta tags.
6. **Mobile app.** Tauri v2 desktop wrap is M5+; native iOS/Android out of scope for v1.
7. **Internationalization rollout.** Strings keyed in M0; ja/es/de/fr/hi shortlist locked at M5 based on customer geography.
8. **Storybook deploy host.** Chromatic vs self-host on Cloudflare Pages. Decision M0; default Chromatic if budget allows for the visual regression service, else Cloudflare Pages.

---

## 9. Out of Scope

For v1 (M0–M3):

- Native mobile apps.
- Real-time multi-cursor on workspace edits.
- A WYSIWYG schema editor (refinement is text-driven; UI does diff preview only).
- A CMS / blog inside the app.
- User-arrangeable dashboards (auto-generated from KPIs in M1; arrangeable in M3+).
- Slack-like inboxes / DM surfaces.
- Custom widget development by end users (built-in widget set only).
- Custom font hosting beyond `Inter` and `JetBrains Mono`.
- A11y deep accessibility customization (font scaling, custom focus styles) beyond browser-native behavior. Considered M5+.

---

## 10. Decision Log

| Date | Change | Author |
|---|---|---|
| 2026-05-07 | Initial frontend architecture & design system locked. React 18 + Vite, TanStack Router/Query, Radix + Tailwind tokens, Recharts, Vitest + Playwright, Storybook 8, `@baseflo/ui` shadcn-style internal lib. ADRs §2.1–2.25. | Founder + AI architect |
| 2026-05-07 | Visual reference points and anti-pattern fence locked (§4.7, §4.8). | Founder + AI architect |
| 2026-05-07 | Design process gates (§5.4) and architectural boundaries (§6) made enforceable in CI. | Founder + AI architect |

---

## Appendix A — What this document does NOT decide

- **Specific Figma file structure.** Designer owns; checked in to the design tools doc later.
- **Exact pixel values for tokens.** `tokens.json` is the source; this doc names the categories.
- **Which screens ship in which sprint.** That's `40-features/WEB-APP.md` §20 milestone plan.
- **Per-screen layout, copy, and component composition.** That's the Figma file + WEB-APP.md §5.

If a question lives in any of those, do not answer it here. If a question contradicts anything here, raise it in `00-decisions.md` first.

---

## Appendix B — Things every new contributor reads in order

1. `00-decisions.md` — what's locked, what's open.
2. `01-architecture.md` §3.7 + §7 — the contract for admin generation and SSE.
3. **This document.**
4. `40-features/WEB-APP.md` — the feature spec, IA, screens, error codes.
5. `05-coding-rules.md` — the coding bar.
6. `50-design-patterns.md` — patterns the codebase uses.

That's the complete onboarding read. If something's missing for a new engineer, the gap goes back into one of these docs — not into a new doc.
