import { useState } from 'react';
import { useNavigate, useParams } from '@tanstack/react-router';
import { useMutation } from '@tanstack/react-query';
import { motion } from 'framer-motion';
import {
  Button,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  Input,
  Label,
  Textarea,
  Badge,
  OnboardingChecklist,
  PulseDot,
} from '@baseflo/ui';
import {
  IconZap,
  IconUsers,
  IconOrders,
  IconProducts,
  IconLayers,
  IconAnalytics,
  IconDatabase,
  IconExport,
  IconTrendingUp,
  IconShield,
  IconBolt,
  IconCheck,
  IconSparkles,
} from '@baseflo/ui/icons';
import type { CreateProjectRequest } from '@baseflo/contracts';
import { useGateway } from '../../providers/GatewayProvider.js';

const EXAMPLE_BUSINESSES = [
  { label: 'yoga studio', icon: IconUsers },
  { label: 'coffee shop', icon: IconOrders },
  { label: 'design agency', icon: IconLayers },
  { label: 'crochet supply', icon: IconProducts },
  { label: 'salon', icon: IconUsers },
  { label: 'online store', icon: IconOrders },
  { label: 'consultancy', icon: IconAnalytics },
];

const EXAMPLE_GOALS = [
  'customers + bookings + payments',
  'orders + refunds + customer notes',
  'classes + packages + members',
  'projects + invoices + clients',
];

const STARTER_CONNECTORS = [
  { id: 'sheets', label: 'Google Sheets', icon: IconLayers },
  { id: 'stripe', label: 'Stripe', icon: IconTrendingUp },
  { id: 'csv', label: 'CSV / Excel', icon: IconExport },
  { id: 'shopify', label: 'Shopify', icon: IconProducts },
  { id: 'postgres', label: 'Postgres', icon: IconDatabase },
];

const AGENTS = [
  { id: 'source', name: 'Source', icon: IconBolt, border: 'border-accent/30', bg: 'bg-accent-soft', text: 'text-accent' },
  { id: 'recon', name: 'Recon', icon: IconUsers, border: 'border-purple-300', bg: 'bg-purple-50', text: 'text-purple-600' },
  { id: 'schema', name: 'Schema', icon: IconShield, border: 'border-emerald-300', bg: 'bg-emerald-50', text: 'text-emerald-600' },
  { id: 'insight', name: 'Insight', icon: IconTrendingUp, border: 'border-amber-300', bg: 'bg-amber-50', text: 'text-amber-600' },
];

/**
 * ICP-B intake (`/o/$orgSlug/start`). Per docs/40-features/WEB-APP.md §5.4 +
 * docs/20-gtm.md §5 demo. Single page. Picks toolset, kicks the saga.
 */
export function StartLaneView() {
  const { orgSlug } = useParams({ from: '/o/$orgSlug/start' });
  const navigate = useNavigate();
  const gateway = useGateway();
  const [businessKind, setBusinessKind] = useState('');
  const [businessGoal, setBusinessGoal] = useState('');
  const [picked, setPicked] = useState<Set<string>>(new Set());

  const createProject = useMutation({
    mutationFn: async () => {
      const name = businessKind ? `${businessKind} workspace` : 'My business';
      const req: CreateProjectRequest = {
        name,
        description: `${businessKind} — track ${businessGoal}.`,
        deploymentMode: 'hosted',
      };
      const project = await gateway.projects.create(orgSlug, req);
      return project;
    },
    onSuccess: (project) => {
      navigate({
        to: '/o/$orgSlug/p/$projectSlug/v/$versionId',
        params: { orgSlug, projectSlug: project.slug, versionId: 'pending' },
      });
    },
  });

  const togglePick = (id: string) => {
    setPicked((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const checklistItems = [
    { id: 'profile', label: 'Mission profile selected', done: !!businessKind },
    { id: 'goals', label: 'Tracking objectives set', done: !!businessGoal },
    { id: 'crew', label: 'Crew assembled', done: picked.size > 0 },
  ];
  const readyCount = checklistItems.filter((i) => i.done).length;

  return (
    <div className="relative min-h-full bg-atmospheric bg-grid-dots py-12">
      <div className="mx-auto w-full max-w-3xl px-4">
        {/* Agent status strip */}
        <motion.div
          initial={{ opacity: 0, y: -8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="mb-6 flex items-center justify-center gap-3"
        >
          <div className="flex items-center gap-2 rounded-full border border-border/80 bg-surface/80 px-4 py-2 shadow-sm backdrop-blur-sm">
            <PulseDot tone="accent" size={6} active />
            <span className="text-xs font-medium uppercase tracking-wider text-fg-muted">
              4 agents standing by
            </span>
            <div className="ml-1 flex items-center gap-1.5">
              {AGENTS.map((a) => (
                <div
                  key={a.id}
                  className={`flex h-6 w-6 items-center justify-center rounded-full border ${a.border} ${a.bg} ${a.text}`}
                  title={`${a.name} Agent`}
                >
                  <a.icon size={12} />
                </div>
              ))}
            </div>
          </div>
        </motion.div>

        {/* Hero header */}
        <motion.header
          initial={{ opacity: 0, y: -6 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.1 }}
          className="mb-8 flex flex-col items-center gap-2 text-center"
        >
          <h1 className="font-serif text-3xl font-semibold leading-tight tracking-tight text-fg">
            Launch your business brain
          </h1>
          <p className="max-w-md text-sm text-fg-muted">
            Your agents are standing by. Configure your mission profile and they&apos;ll
            reconcile your data in 90 seconds.
          </p>
        </motion.header>

        {/* Pre-flight checklist */}
        <motion.div
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.2 }}
          className="mb-8 flex justify-center"
        >
          <div className="flex w-full max-w-lg items-center gap-4 rounded-xl border border-border/80 bg-surface/80 p-4 shadow-sm backdrop-blur-sm">
            <div className="flex flex-1 flex-col gap-1">
              <span className="text-xs font-medium uppercase tracking-wider text-fg-muted">
                Pre-flight checklist
              </span>
              <OnboardingChecklist items={checklistItems} />
            </div>
            <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full border border-accent/20 bg-accent-soft">
              {readyCount === 3 ? (
                <IconCheck size={20} className="text-success" />
              ) : (
                <span className="text-sm font-semibold text-accent">
                  {readyCount}/3
                </span>
              )}
            </div>
          </div>
        </motion.div>

        {/* Mission profile */}
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.25 }}
        >
          <Card className="overflow-hidden border-border/80 shadow-md">
            <CardHeader className="bg-surface-2/50">
              <div className="flex items-center gap-2">
                <span className="flex h-7 w-7 items-center justify-center rounded-full border border-accent/20 bg-accent-soft text-accent">
                  <IconSparkles size={14} />
                </span>
                <CardTitle>Mission profile</CardTitle>
              </div>
              <CardDescription>
                What kind of operation are you running? Pick a profile below.
              </CardDescription>
            </CardHeader>
            <CardContent className="flex flex-col gap-4 pt-6">
              <Input
                value={businessKind}
                onChange={(e) => setBusinessKind(e.target.value)}
                placeholder="E.g. yoga studio, agency, online store"
                className={businessKind ? 'border-accent/40 bg-accent-soft/30' : ''}
              />
              <div className="flex flex-wrap gap-2">
                {EXAMPLE_BUSINESSES.map((ex) => {
                  const isActive = businessKind.toLowerCase() === ex.label.toLowerCase();
                  return (
                    <button
                      key={ex.label}
                      type="button"
                      onClick={() => setBusinessKind(ex.label)}
                      className={`flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs capitalize transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-border-focus ${
                        isActive
                          ? 'border-accent bg-accent-soft text-accent shadow-sm'
                          : 'border-border bg-surface hover:bg-surface-2 hover:border-accent/30'
                      }`}
                    >
                      <ex.icon size={12} />
                      {ex.label}
                    </button>
                  );
                })}
              </div>
            </CardContent>
          </Card>
        </motion.div>

        {/* Tracking objectives */}
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.35 }}
          className="mt-4"
        >
          <Card className="overflow-hidden border-border/80 shadow-md">
            <CardHeader className="bg-surface-2/50">
              <div className="flex items-center gap-2">
                <span className="flex h-7 w-7 items-center justify-center rounded-full border border-purple-200 bg-purple-50 text-purple-600">
                  <IconUsers size={14} />
                </span>
                <CardTitle>What should your agents track?</CardTitle>
              </div>
              <CardDescription>
                Tell the recon agent what matters most to your business.
              </CardDescription>
            </CardHeader>
            <CardContent className="flex flex-col gap-4 pt-6">
              <Textarea
                value={businessGoal}
                onChange={(e) => setBusinessGoal(e.target.value)}
                rows={2}
                placeholder="customers, bookings, payments, classes, products, orders…"
                className={businessGoal ? 'border-accent/40 bg-accent-soft/30' : ''}
              />
              <div className="flex flex-wrap gap-2">
                {EXAMPLE_GOALS.map((ex) => {
                  const isActive = businessGoal === ex;
                  return (
                    <button
                      key={ex}
                      type="button"
                      onClick={() => setBusinessGoal(ex)}
                      className={`rounded-full border px-3 py-1.5 text-xs transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-border-focus ${
                        isActive
                          ? 'border-accent bg-accent-soft text-accent shadow-sm'
                          : 'border-border bg-surface hover:bg-surface-2 hover:border-accent/30'
                      }`}
                    >
                      {ex}
                    </button>
                  );
                })}
              </div>
            </CardContent>
          </Card>
        </motion.div>

        {/* Assemble crew */}
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.45 }}
          className="mt-4"
        >
          <Card className="overflow-hidden border-border/80 shadow-md">
            <CardHeader className="bg-surface-2/50">
              <div className="flex items-center gap-2">
                <span className="flex h-7 w-7 items-center justify-center rounded-full border border-emerald-200 bg-emerald-50 text-emerald-600">
                  <IconDatabase size={14} />
                </span>
                <CardTitle>Assemble your crew</CardTitle>
              </div>
              <CardDescription>
                Recruit the connectors your business already uses. You can enlist more later.
              </CardDescription>
            </CardHeader>
            <CardContent className="pt-6">
              <div className="grid gap-2 sm:grid-cols-2">
                {STARTER_CONNECTORS.map((c) => {
                  const isPicked = picked.has(c.id);
                  return (
                    <button
                      key={c.id}
                      type="button"
                      onClick={() => togglePick(c.id)}
                      aria-pressed={isPicked}
                      className={`group flex items-center gap-3 rounded-xl border p-3 text-left transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-border-focus ${
                        isPicked
                          ? 'border-accent bg-accent-soft shadow-md shadow-accent/10'
                          : 'border-border bg-surface hover:bg-surface-2 hover:border-accent/30 hover:shadow-sm'
                      }`}
                    >
                      <span
                        className={`flex h-9 w-9 items-center justify-center rounded-lg border transition-colors ${
                          isPicked
                            ? 'border-accent/30 bg-accent-soft text-accent'
                            : 'border-border bg-surface-2 text-fg-muted group-hover:text-fg'
                        }`}
                      >
                        <c.icon size={16} />
                      </span>
                      <span className="flex-1 text-sm font-medium">{c.label}</span>
                      {isPicked ? (
                        <Badge variant="accent" className="gap-1">
                          <IconCheck size={10} />
                          Recruited
                        </Badge>
                      ) : (
                        <span className="text-xs text-fg-subtle opacity-0 transition-opacity group-hover:opacity-100">
                          Select
                        </span>
                      )}
                    </button>
                  );
                })}
              </div>
            </CardContent>
          </Card>
        </motion.div>

        {/* Launch bar */}
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.55 }}
          className="mt-6 flex items-center justify-between gap-4 rounded-xl border border-border/80 bg-surface/80 p-4 shadow-sm backdrop-blur-sm"
        >
          <div className="flex items-center gap-2">
            <div className="flex -space-x-1.5">
              {AGENTS.slice(0, Math.min(picked.size + 1, 4)).map((a) => (
                <div
                  key={a.id}
                  className={`flex h-6 w-6 items-center justify-center rounded-full border-2 border-surface ${a.border} ${a.bg} ${a.text}`}
                >
                  <a.icon size={11} />
                </div>
              ))}
            </div>
            <Label className="text-xs text-fg-muted">
              {picked.size} source{picked.size === 1 ? '' : 's'} recruited
            </Label>
          </div>
          <Button
            disabled={createProject.isPending || picked.size === 0 || !businessKind}
            onClick={() => createProject.mutate()}
            className="gap-2 shadow-md shadow-accent/20 transition-shadow hover:shadow-lg hover:shadow-accent/30"
          >
            <IconZap size={14} />
            {createProject.isPending ? 'Launching…' : 'Launch workspace'}
          </Button>
        </motion.div>
      </div>
    </div>
  );
}
