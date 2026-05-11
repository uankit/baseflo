# Baseflo — Go-to-Market

Status: working hypothesis. Pricing values, channel ratios, and ICP weighting are illustrative until validated with first 10 customers and updated in `00-decisions.md` §8. The pitch and positioning are locked.

---

## 1. Positioning

### 1.1 Category

**Business operations layer.** Not "AI app builder," not "BaaS," not "data warehouse," not "CRM." We sit between the tools customers already use and the way they want to run their business.

### 1.2 The Pitch (3 lengths)

**One-liner:**
> Run your business from one place. Connected to what you already use.

**Paragraph (landing-page hero):**
> Your customers, your bookings, your payments — scattered across Stripe, Mailchimp, Excel, and Notion. Baseflo connects what you already use, agentically reconciles it into one workspace, and gives you a hosted admin panel, smart analytics, and a daily digest. No migration, no copy-pasting, no email noise from ten vendors. Your data stays yours.

**60-second pitch (for video, demo, podcast):**
> Most small businesses already have their data — it's in Stripe, Mailchimp, Excel, Notion, Shopify, maybe a custom system. The problem isn't that they don't have data. The problem is it's everywhere. Today they spend hours every week copy-pasting between tools and they still can't see, in one place, who their customers are or what's actually happening in the business. Baseflo changes that. You connect the tools you already use, in 60 seconds Baseflo agentically reconciles your data into one unified view — same customer recognized across Stripe, Notion, Mailchimp — and gives you a hosted admin panel, smart analytics, and one daily digest replacing all the vendor email noise. You don't migrate. You don't write code. You don't see "AI" anywhere. You see your business, finally, in one place. Free to try, $29 to start, your data stays in your own database if you want.

### 1.3 What We Are Not

- Not Lovable. They build frontends; we build the operations layer.
- Not Supabase. They give you a database; we give you a place to run a business.
- Not HubSpot. They make you migrate; we read what you have.
- Not Airbyte. They ingest; we *reconcile and operate*.
- Not Retool. They give you a tool to build admin panels; we generate the admin panel.
- Not PostHog. They track events you've instrumented; we generate schema-aware analytics from your existing data.

### 1.4 The Wedge Sentence (used in demos and elevator)

> *"Your business is already happening. Baseflo just shows you what's happening — in one place, every morning."*

## 2. Who We Sell To (ICPs)

### 2.1 ICP-A — Indie Dev / Solo Operator

- **Who:** Solo dev who built a frontend with Lovable / Cursor / Bolt, needs a backend.
- **Pain:** Backend is the gating step between MVP and live. Glueing Supabase + Clerk + Stripe + admin = 2-6 weeks.
- **Wedge:** "Working backend in 90 seconds. Paste two lines into Cursor and ship today."
- **Distribution:** Twitter, Hacker News (Show HN), Product Hunt, indie hackers, Lovable/Cursor ecosystem (cross-promote with their communities).
- **Likely plan:** Hobby ($29) or Pro ($79).
- **Conversion mechanism:** The friend's case (real person, real demo).

### 2.2 ICP-B — Small Business with Messy Existing Data

- **Who:** Yoga studio, salon, agency, niche e-comm, real estate broker, coach, consultancy. 1-10 employees.
- **Pain:** Lives in Excel + Notion + Mailchimp + Stripe. Copies data between tools weekly. Can't see "who is this customer across all our touchpoints."
- **Wedge:** "Drop your spreadsheet, connect your Stripe, see your business in 5 minutes — no migration."
- **Distribution:** Vertical-specific content (e.g., "How yoga studios should think about customer retention"), Reddit (r/smallbusiness, r/yogateachers, etc.), Indie Hackers, Twitter via ICP-A (devs recommend us to their small-business friends).
- **Likely plan:** Pro ($79) or Business ($499).
- **Conversion mechanism:** The unified Customers tab moment.

### 2.3 ICP-C — Migrating-from-Bloat Customer

- **Who:** Currently on HubSpot Pro / Zoho One / Salesforce Essentials. 5-50 employees. Pays $200-2,000/mo for tools they don't use 80% of.
- **Pain:** Paying too much. Onboarded poorly. Configured wrong. Custom HubSpot fields are a nightmare.
- **Wedge:** "Connect your existing HubSpot, see what we'd build for the way you actually work, decide if you want to migrate."
- **Distribution:** Comparison content ("HubSpot vs Baseflo for X-type business"), targeted ads on procurement and category-search keywords, partnerships with consultants who help SMBs leave bloated CRMs.
- **Likely plan:** Business ($499) or Enterprise.
- **Conversion mechanism:** Side-by-side comparison + audit-style insight (here's what HubSpot can't show you about your own data).

### 2.4 ICP-D — Privacy-Conscious / Regulated (M3+)

- **Who:** Mid-market in regulated-adjacent verticals (legal, healthtech, fintech, edtech), or EU customers. 50-500 employees.
- **Pain:** Won't accept "your data is in our Postgres." Needs BYO-DB or self-host. Has SOC2/HIPAA/GDPR exposure.
- **Wedge:** "Same product, your environment. Connect to your own Postgres, run on your own infra. Your data never leaves your perimeter."
- **Distribution:** Sales-led; partner channel (consultancies, MSPs); compliance-focused content ("How to get a unified customer view without violating GDPR").
- **Likely plan:** Business ($499) or Enterprise (custom).
- **Conversion mechanism:** BYO-DB demo on their data, security review, POC.

### 2.5 ICP Weighting (working hypothesis)

- v1 (M1-M3): 60% ICP-A (devs), 30% ICP-B (SMB), 10% ICP-C/D (deferred).
- v2 (M4-M6): 40% ICP-A, 50% ICP-B, 10% ICP-C/D.
- v3 (M7+): 30% ICP-A, 40% ICP-B, 20% ICP-C, 10% ICP-D.

Devs are the discovery and amplification engine; SMBs are the long-term TAM; enterprise is the high-revenue tail.

## 3. Distribution Strategy

### 3.1 Top of Funnel (M1-M3)

- **Twitter / X:** founder-led; build-in-public posts; demo videos. Target: 200 followers → 2,000 in 90 days.
- **Show HN:** one strong launch post when M1 is shippable. The 90-second demo video is the artifact.
- **Product Hunt:** launch when M2 is solid (multi-source unification working).
- **Lovable / Cursor / Bolt communities:** cross-promote; the friend's case is the wedge story. We are the natural completion of their AI-built frontend.
- **Indie Hackers:** weekly milestone posts; AMA at month 3.
- **Reddit:** vertical-specific communities (r/yogateachers, r/smallbusiness, r/woodworking, etc.) sharing real stories of how a yoga studio / coach / shop uses us — only after we have real customer permission and stories.

### 3.2 Middle Funnel

- **Comparison content:** "Baseflo vs HubSpot Free," "Baseflo vs Notion + Excel," "Why we left Zoho." Honest, with the limitations called out.
- **Vertical playbooks:** "The Yoga Studio Operations Stack," "The Small Agency Stack," etc. Each names every tool the vertical uses today and shows how Baseflo unifies them.
- **Newsletter:** monthly, signal-heavy. Real customer stories. New connector announcements. New refinement examples.

### 3.3 Bottom of Funnel

- **Free trial:** 14 days on Pro, no credit card.
- **Pricing transparency:** every plan's exact features visible; no "contact us" except for Enterprise.
- **Demo on demand:** 15-minute Calendly slots with the founder for the first 6 months.
- **Activation cohort tracking:** weekly cohort review by trial date; intervene at signs of stalled activation.

### 3.4 Partnerships (M4+)

- **Consultancies and MSPs** that help SMBs choose tools (referral fee).
- **Vertical-specific software** (booking platforms, POS systems) that don't have CRM-shaped sibling tools (deeper integration / co-marketing).
- **AI tool ecosystems** (Lovable, Bolt, Cursor) for the "complete the frontend" pitch.

## 4. Pricing

### 4.1 Plans (illustrative, validate after 10 conversations)

| Plan | Price | Target ICP | Limits | What's included |
|---|---|---|---|---|
| **Free Starter** | $0 | Self-host devs, evaluators | 1 project, 1 source, 1k rows, our domain | Hosted, daily digest, SDK, refinement |
| **Hobby** | $29/mo | ICP-A (indie dev) | 1 project, 2 sources, 5k rows | Hosted, custom subdomain, 30-day analytics |
| **Pro** | $79/mo | ICP-A or small ICP-B | 3 projects, unlimited sources, 50k rows, 3 users | Custom domain, 12mo analytics, refinement, daily digest, exports, share links |
| **Business** | $499/mo | ICP-B/C | Unlimited projects, BYO-DB, 25 users | SSO, 1y audit, priority support, custom branding |
| **Enterprise** | Custom | ICP-D | Self-host or dedicated | SOC2, 7y audit, dedicated AE, SLA, EU region, custom connectors |

### 4.2 Pricing Logic

- Hobby is *aggressively cheap* to capture solo devs as the discovery engine.
- Pro is the gravity well: devs upgrade when their friend's business uses it; SMBs land here directly.
- Business is the "you outgrew Pro and your customer demands BYO-DB" tier.
- Enterprise is contracted, sales-led.
- Free Starter and Free self-host Docker exist to seed the market and earn trust.

### 4.3 Unit Economics Targets

- Gross margin: 75%+ at scale (after LLM provider costs and infra).
- LTV:CAC ratio: target 3:1 by M12.
- Payback period: <12 months.
- LLM cost per generation: aim for <$0.50 average via prompt caching (per `02-tech-stack.md` and `03-agentic-workflow.md`).

## 5. The 90-Second Demo (Master Storyboard)

This is the master demo video. Every variation derives from it.

**Setup:** A real (consented) small business — let's say a yoga studio. The screen shows the studio owner's actual cluttered desktop: Stripe tab, Mailchimp tab, a Google Sheet with bookings, Notion with customer notes.

**Beat 1 (0:00-0:10):** Voiceover, the owner: *"Here's what running my yoga studio looks like every Sunday."* Camera shows them flipping between tabs.

**Beat 2 (0:10-0:25):** Cut to baseflo.com. Single text box. They type: *"I run a yoga studio. I want one place to see customers, bookings, payments."* Click Build. *"Connect your sources"* page appears. They click Google Sheets, OAuth, Mailchimp, Stripe, Notion. Each shows live row counts. *"Found 247 bookings, 1,243 contacts, 89 charges, 156 customer notes."*

**Beat 3 (0:25-0:50):** Click Build my workspace. SSE progress streams: *Reading sources → Understanding customers → Resolving relationships → Designing workspace → Setting up analytics → Ready.* The progress is real, not faked.

**Beat 4 (0:50-1:10):** Workspace loads. They click Customers. The unified count: **1,247 unique** (vs 1,735 raw — 488 duplicates resolved). They click "Sarah K." — the unified card shows 12 bookings, $447 lifetime, newsletter subscriber, the note about prenatal class. Voiceover: *"This is the first time I've seen all of this in one place."*

**Beat 5 (1:10-1:25):** Click Analytics tab. Lapsing list shows 8 regulars who haven't booked. They click one — Sarah K. again — and refresh the note: *"Reach out about Tuesday class."* Note saves; writes back to Notion. *"My data still lives where it lives. Baseflo just gives me one place to see it and act on it."*

**Beat 6 (1:25-1:30):** End card. *"Run your business from one place. Connected to what you already use. Free to try at baseflo.com."*

## 6. Validation Conversations (First 10 Customers)

The script for the first 10 conversations — both before launch (validating the idea) and after launch (validating activation).

**Before:**
1. *Walk me through your last week. What tools did you open? What did you copy-paste?*
2. *If I could give you one place that read all your tools and showed you your business in one view — would that change your week?*
3. *What's the thing you keep meaning to fix and never get to?*
4. *What would make this an instant no for you?*
5. *If this existed today, what would you pay per month?*

**After (post-trial):**
1. *Where did you get stuck on day one?*
2. *What did you actually use?*
3. *What did you ignore?*
4. *Did you tell anyone about this? Who?*
5. *Would you keep paying $X/mo? If not, what would change that?*

Answers go into a public spreadsheet. Patterns drive the M2-M3 roadmap.

## 7. Common Objections & Responses

| Objection | Response |
|---|---|
| "Why not just use HubSpot?" | HubSpot makes you migrate. We read what you already use. |
| "Why not just use Supabase?" | Supabase gives you a database. We give you the place to run a business — admin, analytics, refinement, daily digest, all included. |
| "Is this AI?" | Yes, but you don't see it. The agents do the unification work behind the scenes; you see the result. We don't surface model decisions. |
| "Where does my data live?" | Default: in our Postgres, encrypted with your key, audit-logged, exportable in one click. Or in your own Postgres (Business plan). Or self-hosted on your infra (Enterprise). Your choice. |
| "What if you go out of business?" | One-click full export anytime. Self-host Docker available. Open data formats (CSV/SQL/JSON). You can leave with everything. |
| "How is this not just another CRM?" | Most CRMs make you migrate to them. We connect to what you have. Most CRMs are vertical-flavored. We adapt to your business. Most CRMs are pre-shaped grids. We agentically design the schema for *your* operation. |
| "Is this expensive?" | $29/mo to start; free self-host. Cheaper than HubSpot Free + Mailchimp + Notion combined. |
| "What about my privacy/compliance?" | BYO-DB and Self-Host are real options from day one. SOC 2 within 12 months. GDPR-ready out of the box. |

## 8. Brand & Voice

### 8.1 Brand Voice
- Plain English. No jargon.
- Calm confidence. Specific over general. Honest over clever.
- Builder energy, not corporate. Talk to customers like the founder still answers every email (because they do).

### 8.2 Visual Direction
- Clean, modern, not "AI futuristic." No glowing purple gradients.
- Editorial typography (system fonts plus a clean sans for hero).
- Color: a single primary brand color (TBD), neutrals everywhere else.
- Real screenshots of real (consented) workspaces in marketing — never lorem-ipsum mockups.

### 8.3 Voice Examples

**Wrong (too techy):**
> "Leverage agentic AI to unify your business data layer with intelligent semantic reconciliation."

**Right:**
> "Connect Stripe, Notion, Excel — see one customer, not five copies."

**Wrong (too corporate):**
> "Baseflo enables small and medium-sized businesses to streamline their operational stack."

**Right:**
> "Stop copy-pasting between tools. Run your business from one place."

## 9. Launch Sequence

### 9.1 Pre-Launch (M1 → M2)
- 10 closed-beta customers, hand-picked across ICPs.
- Build-in-public weekly Twitter posts.
- Newsletter signup live.
- Status page live before any customer onboards.

### 9.2 Soft Launch (end of M2)
- Show HN: "Baseflo: connect your business tools, get one place to run them."
- Founder responds to every comment for 48h.
- Goal: 200 sign-ups, 20 activated trials, 5 paying.

### 9.3 Public Launch (end of M3)
- Product Hunt launch.
- Multi-source unification demo as the headline.
- Goal: 2,000 sign-ups, 200 activated, 50 paying.

### 9.4 Growth Phase (M4+)
- Vertical playbooks roll out.
- Comparison content goes live.
- Partnerships activate.
- Goal: 10,000 sign-ups, 1,000 activated, 250 paying by M6.

## 10. Failure Mode We Fear Most

If validation says "yeah cool, I'd try it" without specificity, the wedge isn't real and we should reframe before scaling spend. Specificity ("the multi-source customer view would have saved me 4 hours last week, here's the receipt") is the only signal worth scaling on.

The *worst* outcome isn't building the wrong product — it's building the right product with a wedge nobody can articulate, then attributing flat sign-ups to "marketing." Validation discipline is the antibody.
