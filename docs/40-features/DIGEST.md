# `DIGEST` — Daily Digest

Status: M1. Combines `DIG-COMPOSE` + `DIG-CADENCE`. The single morning email replacing 10 vendors' email noise.

---

## 1. Overview

Every active project sends one email per day (or week, configurable) to subscribed users at their local 7am. The digest summarizes overnight activity, surfaces anomalies, lists lapsing customers, names what's selling. It's deterministically composed from `KPIDefinition` outputs + anomalies + lapsing list. Subject line is dynamic and informative; body is short, mobile-first, with one-click links into the workspace.

## 2. High-Level Design

```
Scheduled job (per-user, 7am local) ──▶ DigestComposer ──▶ Resend/Postmark ──▶ Inbox
                                              │
                                              ├─ KPI snapshots (ANALYTICS)
                                              ├─ Anomalies (ANALYTICS)
                                              ├─ Lapsing list (ANALYTICS)
                                              └─ Audit-noteworthy events
```

## 3. Low-Level Design

### 3.1 Module Layout

```
server/app/services/digest/
├── __init__.py
├── composer.py              # DigestComposer.compose(project_id, user_id) -> DigestEmail
├── sections.py              # SectionBuilder per section kind
├── headline.py              # subject line generator
├── render.py                # text + minimal HTML rendering
├── delivery.py              # Resend / Postmark adapter
└── tests/
```

### 3.2 Key Types

```python
class DigestEmail(BaseModel):
    subject: str                              # "Tuesday: 12 bookings, 4 signups, $623, 1 thing to look at"
    sections: list[DigestSection]
    project_id: UUID
    user_id: UUID
    period: DigestPeriod                      # YESTERDAY | LAST_WEEK
    sent_at: datetime

class DigestSection(BaseModel):
    kind: SectionKind                         # AT_A_GLANCE | WORTH_A_LOOK | WHAT_IS_SELLING | LAPSING | RECENT_REFINEMENTS
    title: str
    bullets: list[DigestBullet]
    deep_link_url: str | None                 # one-click into workspace

class DigestBullet(BaseModel):
    text: str
    sentiment: BulletSentiment                # INFO | POSITIVE | NEGATIVE | NEUTRAL
    delta: str | None = None                  # "+15% vs trailing 7-day avg"
```

### 3.3 Composition Rules

- Subject line: `"<Day>: <top_metric_1>, <top_metric_2>, <top_metric_3>, <count_anomalies> thing(s) to look at"`. Anomaly count drives whether the recipient should bother opening.
- Sections (in order):
  1. **At a glance**: top 3-5 KPIs of kind COUNTER, with deltas vs trailing-7-day average.
  2. **Worth a look**: anomalies + lapsing list + payment failures + connector health issues. Empty section = no problems detected.
  3. **What's selling**: top-N most-active products / services / bookings.
  4. **Recent refinements**: any project changes since last digest.
- Hard cap: 12 bullets total. Trim least-significant first.
- Mobile-first: text version is the primary; HTML is a light enhancement.
- Replies go to a tracked address; "Reply STOP" pauses digest.

### 3.4 Cadence Subscriptions

`digest_subscriptions` rows per user per project. Defaults: daily, 7am user-local, email channel.

User can adjust:
- Cadence: daily / weekly / off.
- Time: any local time.
- Channels (M3+): email / Slack / webhook.
- Sections: opt out of specific section kinds.

### 3.5 Delivery

`Resend` or `Postmark` (TBD; both support transactional email well). Bounce handling: 3 hard bounces in 30 days → pause digest, alert user.

## 4. Design Patterns Applied

| Pattern | Where | Why |
|---|---|---|
| **Builder** | `DigestComposer` assembles section by section | Each section is a small responsibility. |
| **Template Method** | Section kinds with consistent structure | Adding new section kinds is mechanical. |
| **Strategy** | Channel abstraction (email / Slack / webhook) | M3+ extensibility without composer changes. |

## 5. Test Plan

- Composer tests: known KPI snapshots + anomalies → expected digest body.
- Subject line: deterministic given inputs.
- Cadence: time-frozen test verifies 7am user-local firing.
- Bullet cap: composition with >12 candidate bullets correctly trims.
- Bounce handling: 3 bounces → digest paused.
- Coverage: 88%.

## 6. Error Codes

| Code | Condition | Recovery |
|---|---|---|
| `BF-DIG-001` | Composition failed (KPI execution error) | Skip digest for the day; ops alert. |
| `BF-DIG-002` | Delivery failed (provider error) | Retry up to 3× with backoff; DLQ on permanent failure. |
| `BF-DIG-003` | User unsubscribed | No-op silently. |

## 7. Dependencies

[`ANALYTICS`](ANALYTICS.md), [`JOBS-AND-SSE`](JOBS-AND-SSE.md) (scheduled), [`AUDIT-CORE`](AUDIT-CORE.md).

## 8. Milestone

- **M1**: email channel; daily cadence; 4 default sections.
- **M2**: per-section opt-out; weekly cadence.
- **M3**: Slack channel; webhook channel.
- **M4+**: per-user-curated digest (user can promote/demote section weight by behavior).
