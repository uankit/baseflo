# Baseflo — Product Doc: Enterprise / Privacy-Conscious Customer

Status: locked for v1 architecture; many features ship in M3+ but the architecture supports them from day one. This doc covers BYO-DB, self-host, SSO, audit, compliance, custom connectors, and the dedicated-support tier.

Defers to `01-architecture.md` §4 (deployment modes), §5 (privacy & security), `00-decisions.md` for the privacy model, and `04-database-schema.md` for the audit log spec.

---

## 1. Who They Are

Three buyer profiles:

1. **Privacy-conscious mid-market** (50-500 employees). EU customer base, regulated industry-adjacent (legal, fintech, healthtech, edtech). Will not accept "your data is in our Postgres" — needs BYO-DB or self-host.
2. **Regulated industries** (pharmacy, clinical practice, financial services, government contractors). HIPAA, SOC2, PCI-DSS, GDPR exposure. Self-host is non-negotiable; SSO and audit are table stakes.
3. **Large brands wanting white-label / agency multi-client.** Boutique consultancies and agencies running 10-50 client workspaces; need granular RBAC, audit, custom branding, and per-client BYO-DB.

What they share:
- A procurement / security / legal review process before they buy.
- Existing identity provider (Okta, Azure AD, Google Workspace).
- Existing compliance posture they can't compromise.
- A CISO or CTO involved in the decision.
- Higher willingness to pay; longer sales cycle; stickier once landed.

## 2. The North-Star Promise

> **The same Baseflo, in your environment, on your terms.**

Same agentic engine. Same admin. Same SDK. Same daily digest. The deployment model and trust controls flex to fit their world.

## 3. Deployment Modes for This Buyer

### 3.1 BYO Database (Bring Your Own Postgres)

Their data lives in **their** Postgres (Neon, Supabase, AWS RDS, Google Cloud SQL, Azure Database, on-prem). Our engine connects with a connection string they provide. We never store customer rows; we only store control-plane metadata (project config, agent run telemetry, audit log).

**Setup:**
1. From Settings → Deployment, switch to "BYO Database" mode.
2. Paste a Postgres connection string. Optionally provide a CA cert for TLS.
3. We test the connection live; show: roles, schemas, write privileges.
4. Run a one-time migration: we emit DDL into a schema named per project; no other schemas touched.
5. Done. Reads and writes go to their database.

**Boundaries:**
- We never copy data out of their DB. Analytics queries (KPI execution, cohort generation) run *against* their DB or via a read-replica they provide.
- The daily digest is composed by querying their DB, generating the summary, and sending; the digest body contains aggregates, not raw rows.
- Connector tokens still live in our control plane (encrypted with their KMS where they provide one; otherwise our KMS scoped to their org).
- Backups are their responsibility (we don't manage their DB); we surface a friendly reminder in Settings.

**Benefits:**
- Their data never leaves their environment.
- They can audit every query through their DB's query log.
- Compliance is largely upstream: if their DB meets HIPAA/PCI/SOC2, the data plane is compliant.

### 3.2 Self-Host (Docker / Kubernetes)

Everything runs on their infrastructure: engine, control plane, admin UI, queue, Postgres. We ship a Docker image and a Helm chart.

**Distribution:**
- Public Docker Hub: `baseflo/engine:<version>` (signed images).
- Helm chart: `baseflo-helm` repo with values for Kubernetes deployment.
- Air-gapped install: documented; license activation supports offline mode (license validates against our license server when reachable; cached for 30 days when not).

**Setup:**
1. They obtain a license key through sales (or self-serve for the lower self-host tier).
2. Pull the image / install the chart.
3. Provide: Postgres URL (control plane), Redis URL (queue), object storage (S3-compatible, including MinIO), KMS endpoint or local key file, OpenAI/Anthropic API key (theirs, or a future self-hosted model endpoint).
4. Run migrations.
5. Start the engine. Admin UI on port 8443 by default. SSO can be configured before first user signs in.

**Updates:**
- Stable channel: monthly releases.
- Security channel: as needed.
- They control upgrade timing. We ship release notes including migration impact.

**Telemetry:**
- Off by default. If opted in, anonymized usage statistics (counts, feature usage, no customer data) flow to us. We never receive customer rows under any circumstance.

**License model:**
- Per-instance per-month or per-year. Sized by: number of projects, number of users, number of source connectors active.
- Offline grace: 30 days from last successful license check.

### 3.3 Hosted Cloud — EU Region

For EU customers who want cloud convenience without US data residency. Same hosted-cloud product, deployed in `eu-west-1`. Data Processing Addendum (DPA) signed at order time. Cross-region transfers blocked by config.

Triggered when: first paying EU customer locks the M3+ EU region build. Architecture supports it from day one (per `01-architecture.md` §4.1).

## 4. Identity & Access (SSO and Beyond)

### 4.1 SSO (M2-M3)

Supported providers:
- **OIDC** (generic + Google Workspace + Microsoft Entra ID).
- **SAML 2.0** (Okta, Azure AD, OneLogin, Auth0).
- **SCIM 2.0** for user provisioning/deprovisioning.

Configuration in Settings → Authentication → Identity Provider. Test mode lets the admin verify before flipping the org to SSO-only.

### 4.2 Roles & Permissions

Beyond the SMB roles (Owner / Admin / Editor / Viewer), enterprise gets:
- **Custom roles** with granular permissions: per-tab read/write, per-action approval requirements, PII reveal restricted to designated roles.
- **Two-person approval** for destructive operations (delete project, change deployment mode, export full data).
- **Time-bounded access** (e.g., contractor access expires in 7 days).
- **IP allowlists** per organization.
- **Session timeout policies** configurable per role.

### 4.3 Audit Log Surfaces

Per `04-database-schema.md` §4.22, every read and write of customer data writes an `audit_events` row. Enterprise customers get:

- Full audit log UI in Settings → Audit, with filters: actor, action, target, time range, IP.
- Export to SIEM: Splunk, Datadog, custom syslog endpoints. Configured per org.
- Per-action policies: e.g., "every PII reveal generates an alert to security@customer.com."
- Retention: 7 years configurable (vs 1 year SMB default).
- Tamper-evident: audit log is append-only with cryptographic chaining (each row's hash includes the previous row's hash); we publish a daily transparency receipt.

## 5. Compliance Posture

### 5.1 Day-One Posture (M0)

- **GDPR-ready:** DPA available, data export, data deletion (with 30-day soft-delete then hard delete), right-to-rectification surfaced through refinement and the admin edit flow, processing record maintained.
- **Standard SaaS controls:** TLS 1.3, AES-256 at rest, per-tenant KMS, encrypted connector tokens, SSO, audit log, RBAC.
- **Subprocessor list:** published at `baseflo.com/subprocessors`; updated with 30-day notice before any addition.

### 5.2 SOC 2 (M3-M6)

- Type 1 within 6 months of first paying enterprise customer.
- Type 2 within 12 months.
- Auditor: TBD; preference for Vanta-backed accelerated audit.
- Report available under NDA to enterprise prospects in active evaluation.

### 5.3 HIPAA (M5+)

- Self-host mode is the path; we sign a BAA for hosted only after substantial process work.
- Initial HIPAA story is "self-host on your HIPAA-compliant infra, we sign a BAA covering our self-host code and any technical support touchpoints."

### 5.4 PCI-DSS

- We do not process card data. Stripe (or other processor) handles PAN; we receive only tokenized references.
- For customers who must demonstrate scope reduction, we provide a Responsibility Matrix.

### 5.5 EU AI Act

- We classify our LLM use as "general-purpose AI" with structured generation. We document model providers, training data sources (provider-published), and human-in-loop touchpoints.
- For customers in regulated sectors who must demonstrate AI risk management, we provide an AI Risk Statement and an audit trail of all agent decisions per project.

## 6. Custom Connectors

Enterprise customers often have internal systems (custom CRM, in-house ERP, mainframe, weird REST APIs). Our connector framework (`01-architecture.md` §3.4) is plugin-based; building a custom connector is:

1. Implement the `Connector` protocol (~6 methods).
2. Ship as a plugin module.
3. Register in their tenant.

For self-host customers, this is something their team can do. For hosted-cloud customers, we offer:

- **Custom connector build service** (one-time engagement; we build, they own).
- **Connector marketplace** (M5+; community-built connectors with quality verification).

## 7. Data Plane Guarantees

Per deployment mode, here's exactly where data lives:

| Mode | Customer business data | Connector tokens | Audit log | Agent run telemetry |
|---|---|---|---|---|
| Hosted Cloud | Our Postgres, encrypted with their KEK in our KMS, schema-isolated per tenant | Our control plane, encrypted with their KEK | Our control plane | Our control plane |
| BYO Database | Their Postgres | Our control plane (or theirs if self-managed KMS) | Our control plane (or theirs if SIEM is wired) | Our control plane |
| Self-Host | Their Postgres on their infra | Their control plane (the bundled one) | Their control plane | Their control plane (opt-in to send anonymized to us) |

This table is the durable, non-negotiable contract. Every feature decision references it.

## 8. White-Label / Agency Mode (M4+)

For agencies running multiple client workspaces:

- Branded admin UI per workspace (logo, colors, custom domain).
- Cross-workspace navigation for the agency operator (single login, multi-org switcher).
- Per-client billing pass-through: agency invoiced; clients pay agency.
- Per-client connector tokens isolated; agency staff role-restricted.

## 9. Onboarding (Enterprise-Specific)

The enterprise sales motion is high-touch by design.

**Pre-sale:**
1. Discovery call: deployment mode, identity provider, regulated industry, data residency, current stack.
2. Solution design: drafted within 48h after discovery; lists exactly which deployment mode, which connectors, which custom build is needed.
3. Security review: NDA-protected SOC2 report (when ready), DPA, security questionnaire pre-filled.
4. POC: 2-week proof-of-concept on their data (BYO-DB or self-host trial).

**Implementation:**
1. Kickoff: Slack channel with our team + their team.
2. Deploy: BYO-DB connection or self-host install.
3. Connect: their sources (often custom).
4. Configure: SSO, roles, audit policies.
5. Train: 2-hour walkthrough for their admins; recorded for their docs.
6. Go-live: hands-off; we monitor closely for 30 days.

**Ongoing:**
- Quarterly business reviews.
- Dedicated account engineer (Business plan and above).
- Direct Slack Connect channel (Enterprise plan).

## 10. Pricing (Enterprise-Specific, Illustrative)

| Plan | Annual Contract | Includes |
|---|---|---|
| Business | $499/mo (commit annual) | BYO-DB, SSO, 1y audit retention, priority support, 25 users |
| Enterprise | $30k - $250k+ ARR | Self-host or hosted, SOC 2 report, dedicated account engineer, 7y audit retention, custom connectors discounted, SLA, EU/region |
| Enterprise Plus | Custom | All Enterprise + on-prem, regulated-industry compliance support, 24/7 SLA, dedicated infrastructure |

Negotiation levers: number of projects, number of users, custom connector quotas, SLA tiers, training hours.

## 11. SLA Tiers

| Tier | Uptime | Response time (P1) | Resolution time (P1) |
|---|---|---|---|
| Standard (Business) | 99.5% | 4 business hours | 1 business day |
| Premium (Enterprise) | 99.9% | 1 hour 24/7 | 4 hours |
| Critical (Enterprise Plus) | 99.95% | 15 minutes 24/7 | 2 hours |

P1 = production down or data inaccessible. P2/P3 with their own response times.

## 12. Anti-Patterns to Avoid

- Treating enterprise as "SMB with more buttons." It's a different sales motion, different trust signals, different pricing.
- Promising SOC2 before we have it. Roadmap is fine; checkbox-claiming isn't.
- Bolting compliance on later. Architecture supports BYO-DB / self-host / audit / KMS from day one because retrofit is more expensive than upfront.
- Letting the enterprise feature surface area pollute the SMB experience. Same engine; different UI affordances.
- Custom-snowflaking the engine per enterprise customer. Customizations live in connectors, prompts (per-tenant overrides), and config — never in core engine code.
