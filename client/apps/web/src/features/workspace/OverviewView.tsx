import { useQuery } from '@tanstack/react-query';
import { motion } from 'framer-motion';
import { formatDistance } from 'date-fns';
import {
  Badge,
  Card,
  CardContent,
  ErrorCallout,
  LoadingSkeletonCard,
  OnboardingChecklist,
  PulseDot,
} from '@baseflo/ui';
import {
  IconConnectors,
  IconSparkles,
  IconTrendingUp,
  IconCheck,
  IconDatabase,
} from '@baseflo/ui/icons';
import { useGateway } from '../../providers/GatewayProvider.js';
import { AGENTS, getAgent, AGENT_ICON_MAP, TONE_STYLE_MAP } from '../../config/agents.js';
import { formatKpiValue, type CurrencyCode } from '../../lib/currency.js';
import { AgentFeedPanel } from './AgentFeedPanel.js';

export function OverviewView({
  orgSlug,
  projectSlug,
  versionId,
}: {
  orgSlug: string;
  projectSlug: string;
  versionId: string;
}) {
  const gateway = useGateway();

  const overviewQuery = useQuery({
    queryKey: ['overview', versionId],
    queryFn: () => gateway.workspace.getOverview(versionId),
    enabled: versionId !== 'pending',
  });

  const projectQuery = useQuery({
    queryKey: ['project', orgSlug, projectSlug],
    queryFn: () => gateway.projects.get(orgSlug, projectSlug),
  });
  const projectId = projectQuery.data?.id;

  const connectorsQuery = useQuery({
    queryKey: ['connectors', projectId],
    queryFn: () => gateway.connectors.list(projectId!),
    enabled: !!projectId,
  });

  const artifactsQuery = useQuery({
    queryKey: ['artifacts', projectId],
    queryFn: async () => {
      if (!projectId) return [];
      const resp = (await gateway.artifacts.list(projectId)) as {
        artifacts: Array<{
          artifactId: string;
          artifactType: string;
          producedBy: string;
          createdAt: string;
        }>;
      };
      return resp.artifacts;
    },
    enabled: !!projectId,
  });

  if (overviewQuery.isPending) {
    return (
      <div className="flex flex-col gap-4">
        <LoadingSkeletonCard />
        <LoadingSkeletonCard />
      </div>
    );
  }

  if (overviewQuery.isError) {
    return (
      <ErrorCallout
        title="Couldn't load workspace"
        message="Try refreshing the page."
      />
    );
  }

  const overview = overviewQuery.data;
  const connectors = connectorsQuery.data ?? [];
  const projectCurrency = (projectQuery.data?.currency as CurrencyCode) ?? 'USD';

  return (
    <div className="flex flex-col gap-8">
      {/* Agent Status Bar — Mission Control */}
      <motion.div
        initial={{ opacity: 0, y: -8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.35 }}
        className="flex items-center gap-4 rounded-xl border border-border bg-surface/80 p-3 backdrop-blur"
      >
        <div className="flex items-center gap-2">
          <div className="relative">
            <PulseDot tone="success" active />
            <span className="absolute -inset-1 animate-ping rounded-full bg-success/20" />
          </div>
          <span className="text-sm font-semibold text-fg">Mission Control</span>
        </div>
        <div className="h-4 w-[1px] bg-border" />
        <div className="flex items-center gap-2">
          <span className="rounded bg-success/10 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-success">
            Live
          </span>
        </div>
        <div className="ml-auto flex items-center gap-3">
          {AGENTS.map((agent) => {
            const lastArtifact = artifactsQuery.data?.find(
              (a) => a.artifactType === agent.artifactType,
            );
            const lastSeen = lastArtifact
              ? formatDistance(new Date(lastArtifact.createdAt), new Date())
              : null;
            const AgentIcon = AGENT_ICON_MAP[agent.icon];
            return (
              <div key={agent.id} className="flex items-center gap-1.5" title={lastSeen ? `Last seen ${lastSeen} ago` : 'Never run'}>
                {AgentIcon && <AgentIcon size={12} className="text-fg-subtle" />}
                <span className={`h-1.5 w-1.5 rounded-full shadow-[0_0_4px_hsl(var(--color-success)/0.6)] ${lastArtifact ? 'bg-success' : 'bg-fg-subtle'}`} />
                <span className="hidden text-[11px] font-medium text-fg-muted sm:inline">
                  {agent.name}
                </span>
                {lastSeen && (
                  <span className="hidden text-[10px] text-fg-subtle md:inline">
                    {lastSeen}
                  </span>
                )}
              </div>
            );
          })}
        </div>
      </motion.div>

      {/* Hero — The Moat */}
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, delay: 0.05 }}
        className="relative overflow-hidden rounded-2xl border border-border bg-surface p-8"
      >
        <div className="absolute inset-0 bg-atmospheric opacity-50" />
        <div className="absolute inset-0 bg-grid-dots opacity-30" />
        <div className="relative">
          <div className="mb-3 flex items-center gap-2">
            <Badge variant="neutral" className="text-[10px] uppercase tracking-wider">
              Workspace Ready
            </Badge>
          </div>
          <h1 className="font-serif text-4xl font-medium text-fg">
            {overview?.digest?.headline ?? 'Workspace ready'}
          </h1>
          <p className="mt-2 max-w-2xl text-sm leading-relaxed text-fg-muted">
            {overview?.digest?.body ?? 'Your unified operating system is live.'}
          </p>
        </div>
      </motion.div>

      {/* Connected Intelligence Grid */}
      {connectors.length > 0 && (
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.1 }}
        >
          <div className="mb-3 flex items-center gap-2">
            <IconConnectors size={14} className="text-accent" />
            <h2 className="text-xs font-semibold uppercase tracking-wider text-fg-subtle">
              Connected Intelligence
            </h2>
          </div>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {connectors.map((c) => (
              <Card
                key={c.id}
                className="group relative overflow-hidden border-border transition-all hover:border-accent/30 hover:shadow-[0_0_16px_hsl(var(--color-accent)/0.08)]"
              >
                <CardContent className="flex items-center gap-3 p-4">
                  <div className="relative flex h-9 w-9 items-center justify-center rounded-lg bg-accent-soft">
                    <IconDatabase size={16} className="text-accent" />
                    {c.status === 'connected' && (
                      <span className="absolute -right-0.5 -top-0.5 h-2.5 w-2.5 rounded-full border-2 border-surface bg-success shadow-[0_0_4px_hsl(var(--color-success)/0.5)]" />
                    )}
                  </div>
                  <div className="flex-1">
                    <p className="text-sm font-semibold text-fg">{c.kind}</p>
                    <p className="text-xs text-fg-muted">
                      {c.status === 'connected' ? 'Synced' : c.status}
                    </p>
                  </div>
                  {c.status === 'connected' && (
                    <span className="flex h-2 w-2 items-center justify-center">
                      <span className="absolute inline-flex h-2 w-2 animate-ping rounded-full bg-success/40" />
                      <span className="relative inline-flex h-2 w-2 rounded-full bg-success" />
                    </span>
                  )}
                </CardContent>
              </Card>
            ))}
          </div>
        </motion.div>
      )}

      {/* KPI Gauges */}
      {overview?.kpis && overview.kpis.length > 0 && (
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.15 }}
        >
          <div className="mb-3 flex items-center gap-2">
            <IconTrendingUp size={14} className="text-accent" />
            <h2 className="text-xs font-semibold uppercase tracking-wider text-fg-subtle">
              Key Metrics
            </h2>
          </div>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {overview.kpis.map((kpi, i) => (
              <motion.div
                key={kpi.id}
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.3, delay: 0.2 + i * 0.05 }}
                className="relative overflow-hidden rounded-xl border border-border bg-surface p-5 transition-all hover:border-accent/20 hover:shadow-[0_0_20px_hsl(var(--color-accent)/0.06)]"
              >
                <div className="absolute top-0 right-0 h-16 w-16 translate-x-6 -translate-y-6 rounded-full bg-accent/5 blur-2xl" />
                <p className="text-xs font-medium uppercase tracking-wider text-fg-subtle">
                  {kpi.label}
                </p>
                <div className="mt-2 flex items-baseline gap-2">
                  <span className="font-mono text-3xl font-semibold text-fg">
                    {formatKpiValue(kpi.value, kpi.unit, projectCurrency)}
                  </span>
                  {kpi.unit && !['$', '€', '£', '¥', '₹', 'USD', 'EUR', 'GBP', 'INR', 'JPY', 'CAD', 'AUD', 'SGD'].includes(kpi.unit) && (
                    <span className="text-sm text-fg-muted">{kpi.unit}</span>
                  )}
                </div>
                {kpi.delta !== undefined && (
                  <div className="mt-2 flex items-center gap-1">
                    <span
                      className={`text-xs font-medium ${
                        (kpi.trend ?? 'neutral') === 'up'
                          ? 'text-success'
                          : (kpi.trend ?? 'neutral') === 'down'
                            ? 'text-danger'
                            : 'text-fg-muted'
                      }`}
                    >
                      {kpi.trend === 'up' ? '+' : kpi.trend === 'down' ? '' : ''}
                      {kpi.delta}
                    </span>
                    <span className="text-[10px] text-fg-subtle">vs last period</span>
                  </div>
                )}
                {/* Gauge bar */}
                <div className="mt-3 h-1 w-full overflow-hidden rounded-full bg-surface-2">
                  <div
                    className="h-full rounded-full bg-accent/60 transition-all duration-1000"
                    style={{ width: `${Math.min(100, Math.max(20, (parseFloat(String(kpi.value)) / (parseFloat(String(kpi.value)) + 50)) * 100))}%` }}
                  />
                </div>
              </motion.div>
            ))}
          </div>
        </motion.div>
      )}

      {/* Agent Intelligence Feed */}
      {projectId && (
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.18 }}
        >
          <AgentFeedPanel projectId={projectId} />
        </motion.div>
      )}

      {/* Agent Activity Log + Pre-flight Checklist */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Agent Activity Log */}
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.2 }}
          className="lg:col-span-2"
        >
          <div className="mb-3 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <IconSparkles size={14} className="text-accent" />
              <h2 className="text-xs font-semibold uppercase tracking-wider text-fg-subtle">
                Agent Activity Log
              </h2>
            </div>
            {artifactsQuery.data && artifactsQuery.data.length > 0 && (
              <span className="text-[10px] text-fg-subtle">
                {artifactsQuery.data.length} artifact{artifactsQuery.data.length === 1 ? '' : 's'} produced
              </span>
            )}
          </div>
          {artifactsQuery.data && artifactsQuery.data.length > 0 ? (
            <div className="flex flex-col gap-2">
              {artifactsQuery.data.slice(0, 8).map((artifact, i) => {
                const agentConfig = getAgent(artifact.producedBy.split('_')[0] ?? '');
                const tone = agentConfig ? TONE_STYLE_MAP[agentConfig.tone] : null;
                const agentColor = tone
                  ? `${tone.text} ${tone.bg} ${tone.border}`
                  : 'text-fg-muted bg-surface-2 border-border';
                const agentName = agentConfig?.name ?? artifact.producedBy.split('_')[0] ?? 'unknown';
                return (
                  <motion.div
                    key={artifact.artifactId}
                    initial={{ opacity: 0, x: -8 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ duration: 0.25, delay: 0.25 + i * 0.04 }}
                    className="group relative flex items-center gap-3 rounded-xl border border-border bg-surface/80 px-4 py-3 backdrop-blur transition-all hover:border-accent/20 hover:bg-surface"
                  >
                    <div className="flex flex-col items-center gap-0.5">
                      <span className="h-2 w-2 rounded-full bg-accent/60 ring-2 ring-accent/20 transition-all group-hover:bg-accent group-hover:ring-accent/40" />
                      {i < Math.min(artifactsQuery.data.length, 8) - 1 && (
                        <div className="h-full w-[1px] bg-border" />
                      )}
                    </div>
                    <span className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full border text-[10px] font-bold ${agentColor}`}>
                      {agentName.charAt(0).toUpperCase()}
                    </span>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm text-fg">
                        <span className="font-medium capitalize">{agentName}</span>{' '}
                        produced{' '}
                        <span className="font-mono text-xs">{artifact.artifactType.replace('_', ' ')}</span>
                      </p>
                      <p className="text-xs text-fg-muted">
                        {formatDistance(new Date(artifact.createdAt), new Date())} ago
                      </p>
                    </div>
                  </motion.div>
                );
              })}
            </div>
          ) : (
            <Card>
              <CardContent className="py-8 text-center">
                <p className="text-sm text-fg-muted">No agent activity yet.</p>
                <p className="mt-1 text-xs text-fg-subtle">
                  Agents will log their work here once they start building.
                </p>
              </CardContent>
            </Card>
          )}
        </motion.div>

        {/* Pre-flight Checklist */}
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.25 }}
        >
          <div className="mb-3 flex items-center gap-2">
            <IconCheck size={14} className="text-success" />
            <h2 className="text-xs font-semibold uppercase tracking-wider text-fg-subtle">
              Pre-flight Checklist
            </h2>
          </div>
          <OnboardingChecklist
            items={[
              {
                id: 'connect',
                label: 'Connect a data source',
                done: connectors.length > 0,
              },
              {
                id: 'workspace',
                label: 'Build your workspace',
                done: versionId !== 'pending',
              },
              {
                id: 'insights',
                label: 'Review your first insights',
                done: (overview?.kpis?.length ?? 0) > 0,
              },
              {
                id: 'invite',
                label: 'Invite your team',
                done: false,
              },
            ]}
          />
        </motion.div>
      </div>
    </div>
  );
}
