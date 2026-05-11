# Baseflo — Product Doc: Small Business User

Status: locked for v1. The SMB user is the primary buyer; the workspace must feel finished, trustworthy, and quietly intelligent. This doc covers their entire experience: landing → onboarding → daily use → refinement → growth.

Defers to `01-architecture.md` for system context, `00-decisions.md` for product principles, and `20-gtm.md` for positioning copy.

---

## 1. Who They Are

Three buyer profiles for v1:

1. **Solo operator with messy data.** Yoga studio, salon, cleaning company, coach, indie e-comm shop. Lives in spreadsheets, Notion, Mailchimp, Stripe, maybe Shopify. Does data entry weekly. Knows there's a better way; can't find it.
2. **Small team (2-10 people) with fragmented tools.** Boutique agency, niche SaaS, restaurant group, fitness studio chain. One person semi-runs ops, but the data lives across HubSpot/Excel/Stripe/internal tools.
3. **Migrating-from-bloat customer.** Currently on Zoho, Salesforce, or HubSpot Pro. Pays $200-2000/month for features they don't use. Wants something that fits their actual business and reads what they already have.

What they share:
- Non-technical or light-technical (uses spreadsheets fluently, hasn't written SQL).
- Time-poor.
- Trust is hard-earned and easily lost.
- Email-noise-fatigued: 10+ vendor emails a week they don't read.
- Want one place. Cannot articulate that need until they see it.

## 2. The North-Star Promise

> **Connect what you already use. See your business in one place. Stop copy-pasting.**

The user never hears the words "agentic," "schema," "IR," "compiler," "KPI." They hear: *"Your customers, your bookings, your payments, your top sellers — one place, every morning."*

## 3. End-to-End User Journey

### 3.1 Landing

`baseflo.com` — single fold. Tagline above the fold: *"Run your business from one place. Connected to what you already use."* Single text box. Ghost-text examples rotating slowly:
- *"A handmade ceramics shop"*
- *"A yoga studio with class bookings"*
- *"A consulting practice with monthly retainers"*
- *"A real-estate brokerage with active listings"*
- *"A pharmacy with prescription tracking"*

Trust signals visible above the fold:
- "Connect Excel, Notion, Postgres, Shopify, Stripe, Mailchimp, Zoho, HubSpot, Twilio, Google Sheets" (logo strip).
- "Your data stays yours" (link → privacy page with deployment-mode explanation).
- "One-click export anytime."

CTA: **Build →**.

### 3.2 First Build (No Sources Yet)

Path A: user types only a description, no source connected yet.

1. Description field expands. Examples disappear.
2. They type their business description.
3. Click Build.
4. Page shifts to a 3-pane layout:
   - Left: stage-progress list (each stage has a status dot)
   - Center: a friendly skeleton workspace
   - Right: a small chat bubble, "Tell me anything that helps me get this right" (used by `ClarificationAgent` for follow-ups)
5. Within ~10s, if `ClarificationAgent` decides clarification is needed, max 3 questions appear inline. *Plain business language, never modeling jargon.* Examples: "Do customers pay one-time, monthly, or both?" / "Do you sell physical things you ship, or services delivered in-person/online?"
6. They answer or skip.
7. SSE shows real stages over ~60s: *Understanding your business → Designing your workspace → Setting up analytics → Validating coherence → Ready.*
8. Workspace loads.

### 3.3 First Build (With Sources)

Path B: user wants to connect existing data.

1. After typing the description, an option appears: *"Connect what you already use (recommended)."* Click.
2. Page shifts to source selection. Tile grid (logos + names): Google Sheets, Excel upload, Notion, Postgres, Shopify, Stripe, Mailchimp, Zoho, HubSpot, Twilio, Salesforce, custom REST.
3. They click each source they have. Per source:
   - **OAuth path:** redirect → grant → return. Smallest required scope. UI shows scopes plain-English: *"Read your customers, orders, and refund records. We do not write or charge."*
   - **API key path:** input field with help link. Validation runs immediately; shows green check or specific error.
   - **File upload (Excel/CSV):** drag-and-drop. Preview first 10 rows. Confirm.
   - **Database URL (Postgres):** form with host/port/db/user/password; tested live.
4. After each connector connects, a "Found N rows" success message appears. Live numbers from their data — trust signal.
5. After all sources are connected (or they say "no more"), click Build my workspace.
6. SSE progress over ~2-3 minutes (longer for more sources):
   - *Reading your sources…*
   - *Understanding your customers across sources…*
   - *Resolving how everything connects…*
   - *Designing your unified workspace…*
   - *Setting up analytics…*
   - *Validating coherence…*
   - *Ready.*
7. Workspace loads. **The first thing they see is the unified Customers list with deduped count and a banner:** *"We found 1,247 unique customers across your 4 sources (1,735 raw rows; 488 duplicates resolved)."* This is the first magic moment for SMB users.

### 3.4 The Workspace (Hosted Admin)

Top bar: project name, deployment mode badge, refinement panel toggle, settings, profile.

Left sidebar (tabs are auto-generated from the unified `SchemaIR`):

- **Overview** — daily digest preview, recent activity, top metric cards, sources health.
- **Customers** *(name auto-derives from agent labeling — could be "Patients" for a clinic, "Members" for a gym, etc.)*
- **Orders / Bookings / Cases / [domain noun]**
- **Products / Services / Offerings / Listings**
- **Reviews / Notes / Communications**
- **Analytics** — funnels, cohorts, regional, retention, anomalies.
- **Sources** — connector health, last sync time, reconnect/revoke.
- **Settings** — team, billing, audit log, exports, API keys, deployment.

Each tab is a typed CRUD view rendered from the unified schema, not hand-coded per project.

#### List view (per entity)

- TanStack Table with virtualization for >1k rows.
- Columns: derived from `ColumnIR`. PII columns masked by default with a click-to-reveal that's audit-logged. Money columns show with currency. Status columns show as colored chips with the agent-classified enum values. Temporal columns show relative ("3 days ago") with hover tooltip absolute.
- Sort, filter (per-column type), search, bulk select.
- Row-source indicator: small badges showing which source(s) contribute (e.g., "S+M+N" for Stripe + Mailchimp + Notion). Hover for detail.
- Top-right actions: New, Import, Export, Refine.

#### Detail view (per row)

- Full record with all reconciled fields.
- Source breakdown panel: which value came from which source, with conflict resolution info if a field disagreed across sources (e.g., *"Stripe says $447; Sheets says $432; Stripe is authoritative."*).
- Related entities: linked customers, orders, payments, etc., navigable.
- Notes / activity timeline auto-aggregated from sources.
- Edit mode: changes write back to the canonical source per the `EntityReconciler`'s policy. Audit-logged.

#### Analytics tab

- Top metric cards (today / this week / this month toggle).
- Funnel chart based on `KPIPlanner`'s output for the schema (e-commerce-shaped: visitor → signup → first order → repeat; bookings-shaped: lead → first booking → repeat → 3+ visits).
- Top-N tables: top customers, top products/services, top regions.
- Lapsing/at-risk list: customers showing decay patterns.
- Anomaly callouts: "Yesterday's failed payments are 3× the trailing average." Click to investigate.

#### Sources tab

- Per-connector status card.
- Health: connected / sync paused / error / token expired / revoked.
- Last sync time, next scheduled sync.
- Disable, reconnect, revoke (one-click; revoke goes through audit log + provider revoke endpoint).
- Conflict log: human-readable list of reconciliation decisions (*"We decided your Stripe customer.email and Notion `Email` field are the same person."*) with override controls.

### 3.5 Daily Digest (Email)

Sent 7am their local timezone (configurable). Plain text + minimal HTML, mobile-first.

Structure:
- One-line headline: *"Tuesday: 12 bookings, 4 new signups, $623, 1 thing to look at."*
- *Yesterday at a glance* — table of metrics deltas vs trailing average.
- *Worth a look* — anomalies, lapsing customers, payment failures, low inventory, something off.
- *What's selling* — top 3 with last-7-day comparison.
- One-click links to drill into the workspace.
- Footer: "Reply to opt out / change cadence / pause."

Replaces the email noise from Stripe receipts, Mailchimp reports, Shopify order alerts, etc. — but those keep flowing in their inbox unchanged. We don't break anything; we add the layer above.

### 3.6 Refinement (English-Language Evolution)

Right-rail panel, available everywhere. User types: *"Add wishlists — customers should save products they like."*

UI flow:
1. Click Refine.
2. Type the request.
3. System shows a **diff preview** in plain language:
   > *"I'll make these changes:*
   > *• Add a Wishlists table linking customers to products.*
   > *• Add a Wishlists tab in the admin.*
   > *• Update analytics to track wishlist additions and conversions to purchase.*
   > *• Existing data stays unchanged.*
   > *Apply?"*
4. They click Apply.
5. New version generates over ~30s. Their workspace seamlessly upgrades; they see the new tab.
6. Old version remains accessible from Settings → Versions; they can compare or rollback.

If `IntentInterpreter` can't parse cleanly, the system asks back: *"Did you mean (a) save for later, (b) favorites, or (c) gift registry? They have slightly different shapes."* Plain language, never modeling jargon.

### 3.7 Sharing

From any record or analytics view: **Share** button.
- Read-only link, expires by default in 7 days, optional password, optional email.
- Audit-logged.
- Recipient lands on a clean read-only view with the workspace's brand-light styling — no auth required.
- For investor or stakeholder updates this is the single feature that replaces "send a screenshot."

### 3.8 Team Collaboration

From Settings → Team: invite by email. Roles:
- **Owner** — billing, can delete project, can change deployment mode.
- **Admin** — connector management, refinement, exports, team management.
- **Editor** — read/write all data, refinement, exports.
- **Viewer** — read-only, can comment.

Audit log captures every action with actor + timestamp.

### 3.9 Settings

- **Project** — name, description, archive.
- **Team** — members, roles, invitations.
- **Billing** — current plan, usage, upgrade/downgrade.
- **Sources** — same as the Sources tab, deeper view.
- **Deployment** — current mode (Hosted / BYO-DB / Self-Host); switch with explicit "this will migrate your data" confirmation.
- **API Keys** — create/revoke; per-key scopes; last-used info; one-click rotate.
- **Audit Log** — full history; filter by actor, action, target.
- **Exports** — full data download (SQL + CSV + JSON).
- **Versions** — refinement history with rollback.
- **Privacy** — PII reveal log, data deletion request, region settings.

## 4. Loading, Empty, and Error States

### Loading
- Generation: SSE-streamed staged progress; never a generic spinner. Each stage announces what it's doing.
- Tab switches: skeleton rows for tables; chart placeholders. Sub-100ms perceived response from cache where possible.

### Empty
- "No customers yet" — *show a connector tile + "Connect a source to populate this."*
- "No analytics yet" — *"Need a few days of data. Coming up: your first cohort report at the 7-day mark."*
- "No refinements yet" — *"Try: 'Add wishlists' or 'Mark VIP customers'. We'll handle the rest."*

### Errors
- Connector token expired: banner on Sources tab → *"Your Shopify connection expired. Reconnect to keep syncing."* One click.
- Connector source unavailable: clear health badge + last-known-good timestamp; do not silently fall back.
- Refinement failed coherence gate twice: clarification question surfaces in a friendly modal: *"I want to make sure I understand. When you say 'subscriptions,' do you mean recurring billing (like monthly), gated content (like a paywall), or something else?"*
- Generation failed terminally: clear error with code (`BF-AGENT-NNN`), one-click retry, and a "Talk to us" link that opens a prefilled support form with the run ID.

## 5. Microcopy Principles

- Plain English, no jargon. *"What's selling"* not *"Top SKU rank by revenue"*.
- Verbs and direct address. *"Connect your Stripe"* not *"Stripe integration available"*.
- Trust over cleverness. *"Your Stripe data is encrypted"* not *"Bank-grade security"*.
- Specific over general. *"Sarah K. asked about prenatal class — follow up"* not *"Customer interaction logged"*.
- Calm confidence on success; precise honesty on failure.

## 6. Privacy Surfaces (User-Visible)

The privacy story lands in three places the user actually sees:

1. **Sources tab → per-connector scope display** — exactly what we read, exactly what we don't.
2. **PII reveal flow** — masked by default; click-to-reveal logs the action; audit log shows who saw what.
3. **Settings → Privacy → Export everything** — single button; user gets an email with a signed link to download SQL + CSV + JSON of their entire workspace within a few minutes.

These three are the daily expression of the brand promise *"Your data stays yours."*

## 7. Pricing Exposure (Illustrative)

User sees plans on `/pricing` and in Settings → Billing.

| Plan | Price | What they get |
|---|---|---|
| Hobby | $29/mo | 1 project, hosted, 2 sources, 5k rows, our domain, 30-day analytics history |
| Pro | $79/mo | 3 projects, hosted, unlimited sources, 50k rows, custom domain, 12-month analytics, team of 3 |
| Business | $499/mo | Unlimited projects, BYO-DB option, SSO, audit log retention 1y, priority support, team of 25 |
| Enterprise | Custom | Self-host, dedicated, SOC2, custom connectors, EU/region, SLA |

Free trial: 14 days on Pro, no credit card. Hobby has a free starter (1 project, 1 source, 1k rows).

Pricing values illustrative; locked after first 10 validation conversations per `00-decisions.md` §8.

## 8. Help & Support

- In-product: Help icon → searchable docs, video walkthroughs, "What's this?" contextual on every advanced UI element.
- Email: support@baseflo.com — 24h response on Hobby, 4h on Pro, 1h on Business, contracted SLA on Enterprise.
- Community: Discord linked from the help menu.
- Status page: `status.baseflo.com` — real-time component status.

## 9. The First-Week Success Criteria

A user has succeeded with Baseflo in their first week if:

1. They've connected at least one source.
2. They've opened the workspace at least 3 days out of 7.
3. They've taken at least one action (added a record, edited a field, exported, refined, shared).
4. They've received and opened at least one daily digest.
5. They have not contacted support with a confused question. (Confused contact = onboarding bug.)

Tracked as activation cohorts; reviewed weekly.

## 10. Anti-Patterns to Avoid

- Onboarding wizards with more than 3 steps.
- Empty admin panels with no path forward.
- Generic placeholder data ("John Doe / john@example.com / $42").
- Loading spinners with no context.
- Vendor-style email noise from us. *We send the digest; nothing else daily.*
- Forcing migration. The point is they don't have to.
- Surfacing model decisions ("the agent decided X"). Surface the result, not the machinery.
- Asking the user to model their business in terms of "entities" or "tables." Ask in business words.
