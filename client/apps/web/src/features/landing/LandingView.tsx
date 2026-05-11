import { Link } from '@tanstack/react-router';
import { Button, PulseDot } from '@baseflo/ui';
import {
  IconArrowRight,
  IconCheck,
  IconSparkles,
} from '@baseflo/ui/icons';
import { motion } from 'framer-motion';
import { useEffect, useMemo, useState } from 'react';
import { AGENTS, AGENT_ICON_MAP, TONE_STYLE_MAP } from '../../config/agents.js';

export function LandingView() {
  return (
    <div className="flex min-h-full flex-col">
      <Header />
      <main role="main" className="flex-1">
        <Hero />
        <SocialProof />
        <AgentShowcase />
        <UseCases />
        <HowItWorks />
        <FinalCTA />
      </main>
      <Footer />
    </div>
  );
}

/* ── Header ─────────────────────────────────────────────────────────────── */

function Header() {
  return (
    <header className="sticky top-0 z-sticky border-b border-border/60 bg-surface/80 backdrop-blur">
      <div className="mx-auto flex h-14 max-w-6xl items-center justify-between px-6">
        <div className="flex items-center gap-2">
          <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-accent text-xs font-bold text-fg-on-accent">
            B
          </span>
          <span className="text-lg font-semibold text-fg">Baseflo</span>
        </div>
        <nav className="flex items-center gap-5">
          <a href="#how" className="hidden text-sm text-fg-muted transition-colors hover:text-fg sm:block">
            How it works
          </a>
          <Link
            to="/sign-in"
            className="text-sm text-fg-muted transition-colors hover:text-fg"
          >
            Sign in
          </Link>
          <Link to="/sign-up">
            <Button size="sm">Start free</Button>
          </Link>
        </nav>
      </div>
    </header>
  );
}

/* ── Hero ───────────────────────────────────────────────────────────────── */

function Hero() {
  return (
    <section className="relative overflow-hidden bg-atmospheric bg-grid-dots">
      <div className="relative mx-auto max-w-6xl px-6 py-24">
        <div className="grid grid-cols-1 items-center gap-16 lg:grid-cols-2">
          <div className="flex flex-col gap-8">
            <motion.div
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5 }}
              className="flex flex-col gap-6"
            >
              <div className="flex items-center gap-2">
                <PulseDot tone="accent" size={6} />
                <span className="text-xs font-medium uppercase tracking-wider text-accent">
                  Now in public beta
                </span>
              </div>

              <h1 className="font-serif text-5xl font-medium leading-[1.1] text-fg lg:text-6xl">
                Your business runs on data.
                <br />
                <span className="text-fg-muted">Finally, it talks back.</span>
              </h1>

              <p className="max-w-md text-lg leading-relaxed text-fg-muted">
                Connect your tools. Four agents map, reconcile, and understand
                your data — then surface what actually matters and help you act
                on it. No spreadsheets. No SQL. Just answers.
              </p>

              <div className="flex flex-wrap items-center gap-4">
                <Link to="/sign-up">
                  <Button size="lg">
                    Start free
                    <IconArrowRight size={16} />
                  </Button>
                </Link>
                <span className="text-xs text-fg-subtle">
                  No credit card · 2-minute setup
                </span>
              </div>

              <div className="flex flex-wrap gap-x-5 gap-y-2 text-xs text-fg-subtle">
                {[
                  'Stripe',
                  'Shopify',
                  'Postgres',
                  'Google Sheets',
                  'CSV',
                ].map((s) => (
                  <span key={s} className="flex items-center gap-1">
                    <IconCheck size={12} className="text-success" />
                    {s}
                  </span>
                ))}
              </div>
            </motion.div>
          </div>

          <motion.div
            initial={{ opacity: 0, scale: 0.96 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.6, delay: 0.2 }}
          >
            <LiveWorkspacePreview />
          </motion.div>
        </div>
      </div>
    </section>
  );
}

/* ── Live Workspace Preview (cycles through real states) ────────────────── */

function LiveWorkspacePreview() {
  const [step, setStep] = useState(0);

  const stages = useMemo(() => {
    const agentLabels: Record<string, { done: string; thinking: string }> = {
      source: { done: '8 tables mapped', thinking: 'Reading 8 tables' },
      reconciliation: { done: '1,247 entities', thinking: '1,247 entities' },
      schema: { done: '12 tables designed', thinking: '12 tables designed' },
      insight: { done: '6 KPIs ready', thinking: '6 KPIs ready' },
    };

    const stageVerbs = ['reading Stripe', 'matching customers', 'designing unified model', 'generating KPIs'];

    return AGENTS.map((agent, idx) => {
      const labels = agentLabels[agent.id] ?? { done: 'Complete', thinking: 'Working…' };
      return {
        label: `${agent.name} Agent ${stageVerbs[idx] ?? 'working'}…`,
        agents: AGENTS.map((a, i) => ({
          id: a.id,
          state: i < idx ? 'done' : i === idx ? 'thinking' : 'idle',
          label: i < idx ? labels.done : i === idx ? labels.thinking : 'Waiting',
        })),
        kpis:
          idx === AGENTS.length - 1
            ? [
                { label: 'Revenue', value: '$48,200', highlight: true },
                { label: 'Customers', value: '1,247', highlight: true },
                { label: 'At-risk', value: '12', highlight: true },
              ]
            : [
                { label: 'Revenue', value: '—', highlight: false },
                { label: 'Customers', value: '—', highlight: false },
                { label: 'At-risk', value: '—', highlight: false },
              ],
      };
    });
  }, []);

  useEffect(() => {
    const id = setInterval(() => setStep((s) => (s + 1) % stages.length), 2800);
    return () => clearInterval(id);
  }, [stages.length]);

  const current = stages[step]!;

  return (
    <div className="relative rounded-2xl border border-border bg-surface p-6 shadow-lg">
      {/* Chrome */}
      <div className="mb-4 flex items-center gap-2 border-b border-border pb-3">
        <div className="flex gap-1.5">
          <span className="h-2.5 w-2.5 rounded-full bg-danger/60" />
          <span className="h-2.5 w-2.5 rounded-full bg-warning/60" />
          <span className="h-2.5 w-2.5 rounded-full bg-success/60" />
        </div>
        <span className="ml-2 text-[10px] font-medium uppercase tracking-wider text-fg-subtle">
          Live Preview
        </span>
      </div>

      {/* Status line */}
      <div className="mb-4 flex items-center gap-2">
        <PulseDot tone="accent" size={6} active />
        <span className="text-xs text-accent transition-all duration-300">
          {current.label}
        </span>
      </div>

      {/* KPI strip */}
      <div className="mb-5 grid grid-cols-3 gap-2">
        {current.kpis.map((kpi) => (
          <div
            key={kpi.label}
            className={`rounded-lg border p-3 transition-all duration-500 ${
              kpi.highlight
                ? 'border-accent/30 bg-accent-soft'
                : 'border-border bg-surface-2'
            }`}
          >
            <p className="text-[10px] uppercase tracking-wider text-fg-subtle">
              {kpi.label}
            </p>
            <p
              className={`mt-1 text-sm font-semibold tabular-nums transition-all duration-500 ${
                kpi.highlight ? 'text-accent' : 'text-fg-muted'
              }`}
            >
              {kpi.value}
            </p>
          </div>
        ))}
      </div>

      {/* Agent dock */}
      <div className="flex items-center justify-center gap-4 rounded-xl border border-border bg-bg p-4">
        {current.agents.map((agent) => {
          const agentConfig = AGENTS.find((a) => a.id === agent.id);
          const tone = agentConfig ? TONE_STYLE_MAP[agentConfig.tone] : null;
          return (
            <div key={agent.id} className="flex flex-col items-center gap-1.5">
              <div
                className={`flex h-9 w-9 items-center justify-center rounded-full border-2 text-xs font-bold transition-all duration-500 ${
                  agent.state === 'thinking'
                    ? `${tone?.border ?? 'border-accent'} ${tone?.bg ?? 'bg-accent-soft'} ${tone?.text ?? 'text-accent'} animate-pulse`
                    : agent.state === 'done'
                      ? 'border-success bg-success/10 text-success'
                      : 'border-border bg-surface-2 text-fg-subtle'
                }`}
              >
                {agent.id.charAt(0).toUpperCase()}
              </div>
              <span className="text-[10px] text-fg-subtle">{agent.label}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

/* ── Social Proof ───────────────────────────────────────────────────────── */

function SocialProof() {
  const stats = [
    { value: '< 90s', label: 'To first unified workspace' },
    { value: '4', label: 'Autonomous agents' },
    { value: '0', label: 'Spreadsheets required' },
  ];

  return (
    <section className="border-b border-border bg-surface/50 py-10">
      <div className="mx-auto max-w-6xl px-6">
        <div className="grid grid-cols-1 gap-8 sm:grid-cols-3">
          {stats.map((s) => (
            <div key={s.label} className="flex flex-col items-center gap-1 text-center">
              <span className="font-serif text-3xl font-semibold text-fg">{s.value}</span>
              <span className="text-xs text-fg-muted">{s.label}</span>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

/* ── Agent Showcase ─────────────────────────────────────────────────────── */

function AgentShowcase() {
  const agentDescs: Record<string, string> = {
    source:
      'Reads every table, column, and relationship from your sources. Understands semantics, not just schemas.',
    reconciliation:
      'Matches customers, orders, and products across sources. Resolves duplicates with confidence scores.',
    schema:
      'Designs a unified physical schema with proper types, indexes, and relationships — then applies it.',
    insight:
      'Generates KPIs, segments, and anomaly detection tuned to your business — not generic dashboards.',
  };

  return (
    <section className="py-20">
      <div className="mx-auto max-w-6xl px-6">
        <div className="mb-12 text-center">
          <h2 className="font-serif text-3xl font-medium text-fg">
            {AGENTS.length} agents. One brain.
          </h2>
          <p className="mt-3 text-fg-muted">
            Each specializes in a part of the data lifecycle. Together they build
            your workspace in under two minutes.
          </p>
        </div>

        <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4">
          {AGENTS.map((agent, i) => {
            const AgentIcon = AGENT_ICON_MAP[agent.icon];
            const tone = TONE_STYLE_MAP[agent.tone];
            return (
              <motion.div
                key={agent.id}
                initial={{ opacity: 0, y: 12 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.1 }}
                className="flex flex-col gap-4 rounded-xl border border-border bg-surface p-5 transition-colors hover:border-border-focus"
              >
                <div
                  className={`flex h-10 w-10 items-center justify-center rounded-lg ${tone.bg} ${tone.text}`}
                >
                  {AgentIcon && <AgentIcon size={18} />}
                </div>
                <div>
                  <p className="text-sm font-semibold text-fg">{agent.name}</p>
                  <p className="text-[10px] uppercase tracking-wider text-fg-subtle">
                    {agent.role}
                  </p>
                </div>
                <p className="text-sm leading-relaxed text-fg-muted">
                  {agentDescs[agent.id] ?? agent.personality}
                </p>
              </motion.div>
            );
          })}
        </div>
      </div>
    </section>
  );
}

/* ── Use Cases ──────────────────────────────────────────────────────────── */

function UseCases() {
  const cases = [
    {
      title: 'See true revenue across Stripe + Shopify',
      body: 'Refunds in Stripe, orders in Shopify — reconciled into one number that actually matches your bank.',
    },
    {
      title: 'Catch churn before it happens',
      body: 'The Insight agent flags at-risk accounts by combining subscription status, support tickets, and payment behavior.',
    },
    {
      title: 'Segment customers across every touchpoint',
      body: 'High-LTV repeat buyers who also opened tickets? The Recon agent knows who they are, even if names differ across tools.',
    },
    {
      title: 'No more "export to CSV" rituals',
      body: 'New data lands via webhook. The agents update the model, backfill what changed, and your KPIs refresh automatically.',
    },
  ];

  return (
    <section className="border-t border-border bg-surface/30 py-20">
      <div className="mx-auto max-w-6xl px-6">
        <h2 className="mb-12 text-center font-serif text-3xl font-medium text-fg">
          What you can do with it
        </h2>
        <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
          {cases.map((c, i) => (
            <motion.div
              key={c.title}
              initial={{ opacity: 0, y: 10 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: i * 0.08 }}
              className="rounded-xl border border-border bg-surface p-6 transition-colors hover:border-border-focus"
            >
              <div className="mb-3 flex items-center gap-2">
                <IconSparkles size={14} className="text-accent" />
                <h3 className="text-sm font-semibold text-fg">{c.title}</h3>
              </div>
              <p className="text-sm leading-relaxed text-fg-muted">{c.body}</p>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}

/* ── How It Works ───────────────────────────────────────────────────────── */

function HowItWorks() {
  const steps = [
    {
      n: '01',
      title: 'Connect your sources',
      body: 'Stripe, Shopify, Postgres, Google Sheets, or CSV. Authenticate in seconds. No ETL configuration.',
    },
    {
      n: '02',
      title: 'The agents build your workspace',
      body: 'Source maps your data. Recon matches entities. Schema designs the model. Insight generates KPIs. All automatically.',
    },
    {
      n: '03',
      title: 'Ask and act',
      body: 'Query in plain English. Get answers. Trigger exports, alerts, or webhooks. Refine the model when your business changes.',
    },
  ];

  return (
    <section id="how" className="py-20">
      <div className="mx-auto max-w-6xl px-6">
        <h2 className="mb-12 text-center font-serif text-3xl font-medium text-fg">
          How it works
        </h2>
        <div className="grid grid-cols-1 gap-8 md:grid-cols-3">
          {steps.map((step, i) => (
            <motion.div
              key={step.n}
              initial={{ opacity: 0, y: 12 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: i * 0.1 }}
              className="relative flex flex-col gap-3"
            >
              <span className="font-mono text-xs text-fg-subtle">{step.n}</span>
              <h3 className="text-lg font-medium text-fg">{step.title}</h3>
              <p className="text-sm leading-relaxed text-fg-muted">{step.body}</p>
              {i < steps.length - 1 && (
                <span className="absolute right-0 top-8 hidden text-fg-subtle md:block">
                  →
                </span>
              )}
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}

/* ── Final CTA ──────────────────────────────────────────────────────────── */

function FinalCTA() {
  return (
    <section className="relative overflow-hidden border-t border-border bg-atmospheric py-24">
      <div className="relative mx-auto max-w-2xl px-6 text-center">
        <h2 className="font-serif text-4xl font-medium leading-tight text-fg">
          Stop reconciling spreadsheets.
          <br />
          Start running your business.
        </h2>
        <p className="mx-auto mt-5 max-w-md text-fg-muted">
          Free for indie founders. Add a credit card only when you outgrow the
          generous free tier.
        </p>
        <div className="mt-10 flex flex-col items-center gap-4">
          <Link to="/sign-up">
            <Button size="lg">Start free</Button>
          </Link>
          <div className="flex flex-wrap items-center justify-center gap-x-4 gap-y-1 text-[11px] text-fg-subtle">
            <span className="flex items-center gap-1">
              <IconCheck size={12} className="text-success" />
              Unlimited sources
            </span>
            <span className="flex items-center gap-1">
              <IconCheck size={12} className="text-success" />
              Real-time sync
            </span>
            <span className="flex items-center gap-1">
              <IconCheck size={12} className="text-success" />
              Team invites
            </span>
          </div>
        </div>
      </div>
    </section>
  );
}

/* ── Footer ─────────────────────────────────────────────────────────────── */

function Footer() {
  return (
    <footer className="border-t border-border py-10">
      <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-4 px-6 sm:flex-row">
        <div className="flex items-center gap-2">
          <span className="flex h-6 w-6 items-center justify-center rounded-md bg-accent text-[10px] font-bold text-fg-on-accent">
            B
          </span>
          <span className="text-sm font-semibold text-fg">Baseflo</span>
        </div>
        <span className="text-xs text-fg-subtle">
          © {new Date().getFullYear()} Baseflo
        </span>
      </div>
    </footer>
  );
}
