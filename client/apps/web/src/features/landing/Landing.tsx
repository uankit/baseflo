import { Link } from '@tanstack/react-router';
import './landing.css';

type LoopStep = {
  num: string;
  name: string;
  desc: string;
};

const LOOP_STEPS: LoopStep[] = [
  {
    num: '1',
    name: 'Sense',
    desc: 'Ingest and profile every connected source. No assumptions about schema; the data tells us what it is.',
  },
  {
    num: '2',
    name: 'Model',
    desc: 'Infer the assets, columns, relationships, metrics, events, and memory that constitute the business.',
  },
  {
    num: '3',
    name: 'Watch',
    desc: 'Detect change, drift, anomalies, bottlenecks, and quiet opportunities — across sources.',
  },
  {
    num: '4',
    name: 'Explain',
    desc: 'Produce grounded narratives. Every claim carries lineage and confidence. No black box.',
  },
  {
    num: '5',
    name: 'Act',
    desc: 'Propose safe next steps across the tools you already use. Audience, draft, approval, write-back.',
  },
  {
    num: '6',
    name: 'Learn',
    desc: "Remember approvals, dismissals, definitions, context. Tomorrow's edition is sharper than today's.",
  },
];

type Source = {
  badge: string;
  badgeClass: string;
  name: string;
  kind: string;
};

const SOURCES: Source[] = [
  { badge: 'SH', badgeClass: 'b-shopify', name: 'Shopify', kind: 'Orders, products, customers' },
  { badge: 'ST', badgeClass: 'b-stripe', name: 'Stripe', kind: 'Charges, subs, refunds' },
  { badge: 'MC', badgeClass: 'b-mail', name: 'Mailchimp', kind: 'Sends, opens, engagement' },
  { badge: 'PG', badgeClass: 'b-pg', name: 'Postgres', kind: 'Your internal system' },
  { badge: 'GS', badgeClass: 'b-sheets', name: 'Google Sheets', kind: 'Whatever lives in tabs' },
  { badge: 'XL', badgeClass: 'b-excel', name: 'Excel', kind: 'Offline ops, spreadsheets' },
  { badge: 'CSV', badgeClass: 'b-csv', name: 'CSV uploads', kind: 'SaaS exports, one-offs' },
  { badge: 'HS', badgeClass: 'b-hubspot', name: 'HubSpot', kind: 'CRM · deals · contacts' },
  { badge: 'SK', badgeClass: 'b-stack', name: 'Slack', kind: 'Where decisions land' },
  { badge: '+', badgeClass: 'b-custom', name: 'Custom', kind: 'SDK · build a connector' },
];

const STANCE_ISNT = [
  'a spreadsheet copilot',
  'a dashboard or BI builder',
  'a generic agent platform',
  'a vertical template catalog',
  'AI-employee cosplay',
  'another tab to remember to open',
];

const STANCE_IS = [
  'the state layer your business actually runs on',
  'grounded intelligence — every claim sourced, with confidence',
  'governed action — approval, audit, rollback by default',
  'deterministic where it must be (SQL, anomalies, permissions)',
  'semantic where it can be (synthesis, language, framing)',
  'read in the morning · acted on by 9:14am',
];

export function Landing() {
  return (
    <div className="bf-landing">
      <div className="page">
        <Topbar />
        <Masthead />
        <Lede />
        <TheLoop />
        <SampleEdition />
        <PullQuote />
        <Sources />
        <Stance />
        <ClosingCTA />
        <Foot />
      </div>
    </div>
  );
}

function Topbar() {
  return (
    <header className="topbar">
      <Link to="/" className="brand">
        baseflo<span className="dot">.</span>
      </Link>
      <nav className="nav">
        <a href="#loop">The loop</a>
        <a href="#edition">The brief</a>
        <a href="#sources">Connect</a>
        <a href="#stance">Stance</a>
        <a href="#pricing">Pricing</a>
        <a href="#docs">Docs</a>
      </nav>
      <div className="top-cta">
        <Link to="/sign-in" className="signin">
          sign in
        </Link>
        <Link to="/sign-in" className="btn-lg">
          request access <span className="arr">→</span>
        </Link>
      </div>
    </header>
  );
}

function Masthead() {
  return (
    <div className="masthead">
      <div className="masthead-rule">
        <span>Est. when you first connect</span>
        <span>An adaptive operating intelligence · for businesses</span>
        <span>Filed by your data · not your team</span>
      </div>
      <h1>
        baseflo<span className="accent-dot">.</span>
      </h1>
      <div className="deck">
        "The business state layer that serious agents need before they can act."
      </div>
    </div>
  );
}

function Lede() {
  return (
    <section className="lede">
      <div>
        <div className="lede-headline">
          Run your business from <span className="accent">one place</span>.
          <br />
          Connected to what you already use.
        </div>
        <div className="lede-cta">
          <Link to="/sign-in" className="btn-lg">
            request early access <span className="arr">→</span>
          </Link>
          <a className="btn-lg ghost" href="#edition">
            see a sample edition
          </a>
          <span className="small-note">— or read the loop ↓</span>
        </div>
      </div>
      <div className="lede-body">
        <p className="dropcap">
          Baseflo is the adaptive operating intelligence layer for a business. Connect the places
          where work already lives — spreadsheets, databases, Stripe, Shopify, your CRM, your support
          tool, a custom internal system — and Baseflo learns the <i>shape</i> of the data, watches
          for meaningful change, explains why it matters, and proposes controlled next moves.
        </p>
        <p>
          No templates. No dashboards to build. No "AI employee" cosplay. Grounded intelligence
          first, governed action next.
        </p>
      </div>
    </section>
  );
}

function TheLoop() {
  return (
    <section className="section" id="loop">
      <div className="section-label">The continuous loop · what Baseflo does, every minute</div>
      <h2 className="section-title">Sense, model, watch, explain, act, learn.</h2>
      <p className="section-deck">
        Six deterministic steps. The first four earn trust by understanding and explaining the
        business. The last two move into governed action — with reasoning, lineage, and rollback
        baked in.
      </p>
      <div className="loop">
        {LOOP_STEPS.map((step) => (
          <div key={step.num} className="loop-step">
            <div className="loop-num">{step.num}</div>
            <div className="loop-name">{step.name}</div>
            <div className="loop-desc">{step.desc}</div>
            <div className="loop-arrow">→</div>
          </div>
        ))}
      </div>
    </section>
  );
}

function SampleEdition() {
  return (
    <section className="section" id="edition">
      <div className="edition">
        <div className="edition-copy">
          <div className="section-label">The Brief · your home surface</div>
          <h3>An operating brief — filed by your data, not your team.</h3>
          <p>
            Every morning, Baseflo files an edition: today's six inferences in plain language, with
            the comparisons that make them legible and the one-click actions that close the loop. No
            KPI counters. No schema diagrams. No clever charts demanding a second click to find the
            point.
          </p>
          <p>
            Just headlines a founder can act on, with the reasoning beneath each one — and the trust
            receipts (source, confidence, sample, lineage) only a click away.
          </p>
          <ul className="edition-bullets">
            <li>Stories, not metrics. Each headline is an inference with a recommended action.</li>
            <li>Sourced like journalism. Sources, confidence, sample size — visible on every claim.</li>
            <li>
              Comparisons over counters. Bangalore vs Mumbai. Engaged vs disengaged. Olive vs other
              variants.
            </li>
            <li>
              Actions in one click. Send the coupon. Place the reorder. Pause the ad on the sold-out
              SKU.
            </li>
          </ul>
          <div className="lede-cta">
            <Link to="/sign-in" className="btn-lg">
              view the prototype <span className="arr">→</span>
            </Link>
          </div>
        </div>

        <EditionPreview />
      </div>
    </section>
  );
}

function EditionPreview() {
  return (
    <div className="preview">
      <span className="preview-stamp">a sample edition</span>
      <div className="preview-mast">
        <div className="top">
          <span>EST. ON CONNECT</span>
          <span>WED · 13 MAY 2026</span>
          <span>ONE DECISION</span>
        </div>
        <div className="title">The Cotton-Co Daily</div>
        <div className="sub">
          "An operating brief, filed by your data." · sources: shopify · excel · mailchimp · stripe
        </div>
      </div>
      <div className="preview-grid">
        <div className="preview-col">
          <div className="preview-tag">Operations · Lead</div>
          <div className="preview-lead">
            Bangalore quietly outpaces Mumbai three to one — and the cause isn't what you'd guess
          </div>
          <div className="preview-body dc">
            For weeks the founder team split marketing budget evenly between the two cities, and the
            orders pull suggested the spend was working. The <i>reorders</i> pull tells a different
            story. Bangalore customers see parcels in <b>1.8 days</b>; Mumbai waits <b>3.6</b>.
            Product mix is identical. Baseflo's reading: delivery speed is the gate that lets every
            other channel work.
          </div>
          <div className="preview-rule" />
          <div className="preview-tag">Customers</div>
          <div className="preview-lead sm">Forty-seven people read your emails but never buy</div>
          <div className="preview-body">
            Engaged. Quiet. Worth ₹1.13L in lifetime value. They opened the last three sends and
            haven't ordered in sixty days.
          </div>
        </div>
        <div className="preview-col preview-side">
          <div className="preview-tag bordered">By the numbers</div>
          <div className="row">
            <span>Customers</span>
            <span className="v">4,829</span>
          </div>
          <div className="row">
            <span>Orders · 30d</span>
            <span className="v">1,247</span>
          </div>
          <div className="row">
            <span>Revenue · 30d</span>
            <span className="v">₹18.4L</span>
          </div>
          <div className="row">
            <span>Reorder rate</span>
            <span className="v">24%</span>
          </div>
          <div className="row">
            <span>Engaged-dormant</span>
            <span className="v accent">47</span>
          </div>

          <div className="preview-tag bordered spaced">Overnight</div>
          <div className="overnight">
            · 12 new orders since last edition
            <br />
            · Mailchimp opens dropped 6 pp
            <br />· Linen Set crossed 8-day cover
          </div>
        </div>
      </div>
      <div className="preview-foot">
        <span className="lab">Today's three:</span>
        <span className="chip-mini">1 · coupon · 47 cust</span>
        <span className="chip-mini">2 · reorder · 5 SKUs</span>
        <span className="chip-mini">3 · BLR look-alike</span>
      </div>
    </div>
  );
}

function PullQuote() {
  return (
    <div className="pull">
      <div className="pull-quote">
        "Not a dashboard.
        <br />
        Not a copilot.{' '}
        <span className="accent">An operating brief — filed by your data, not your team.</span>"
      </div>
      <div className="pull-attr">— The Baseflo Stance</div>
    </div>
  );
}

function Sources() {
  return (
    <section className="section" id="sources">
      <div className="section-label">Connect · v1</div>
      <h2 className="section-title">Wire it to what you already use.</h2>
      <p className="section-deck">
        No data warehouse required. Baseflo connects directly to the tools your business runs on,
        profiles what it finds, and starts filing within the hour.
      </p>
      <div className="sources">
        {SOURCES.map((source) => (
          <div key={source.name} className="source-card">
            <div className={`badge ${source.badgeClass}`}>{source.badge}</div>
            <div className="name">{source.name}</div>
            <div className="kind">{source.kind}</div>
          </div>
        ))}
      </div>
      <div className="sources-more small-note">
        More coming · Salesforce, Notion, Linear, Snowflake, BigQuery, Klaviyo, Intercom, Zendesk
      </div>
    </section>
  );
}

function Stance() {
  return (
    <section className="section" id="stance">
      <div className="section-label">The stance</div>
      <h2 className="section-title">What Baseflo is — and isn't.</h2>
      <p className="section-deck">
        There's a lot of software in the same neighbourhood. None of it is doing this. We are
        intentional about what we won't build.
      </p>
      <div className="stance">
        <div className="stance-col isnt">
          <h4>
            Baseflo is <i>not</i>
          </h4>
          <ul>
            {STANCE_ISNT.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
        <div className="stance-col is">
          <h4>
            Baseflo <i>is</i>
          </h4>
          <ul>
            {STANCE_IS.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
      </div>
    </section>
  );
}

function ClosingCTA() {
  return (
    <div className="closer">
      <h2>
        Tomorrow's edition <br />
        arrives at sunrise.
      </h2>
      <p>Connect your first source in under five minutes. We'll file the first brief inside an hour.</p>
      <div className="cta-row">
        <Link to="/sign-in" className="btn-lg">
          request early access <span className="arr">→</span>
        </Link>
        <Link to="/sign-in" className="btn-lg ghost">
          sign in
        </Link>
      </div>
      <div className="scribble-row">
        <span className="scribble-note">no credit card · no demo gating · just the brief ↑</span>
      </div>
    </div>
  );
}

function Foot() {
  return (
    <footer className="foot">
      <div>© Baseflo, 2026 · An adaptive operating intelligence layer for a business.</div>
      <div className="links">
        <a href="#docs">Docs</a>
        <a href="#security">Security</a>
        <a href="#stance">Stance</a>
        <a href="#careers">Careers</a>
        <Link to="/sign-in">Sign in</Link>
      </div>
    </footer>
  );
}
