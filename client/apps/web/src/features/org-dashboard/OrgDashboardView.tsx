import { Link, useParams } from '@tanstack/react-router';
import { useQuery } from '@tanstack/react-query';
import { format } from 'date-fns';
import {
  Button,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  EmptyState,
  LoadingSkeletonCard,
  ErrorCallout,
  OnboardingStep,
  StatusChip,
  DeploymentModeBadge,
  PulseDot,
} from '@baseflo/ui';
import {
  IconArrowRight,
  IconCommand,
  IconConnectors,
  IconDatabase,
  IconLayers,
  IconPlus,
  IconSparkles,
  IconZap,
} from '@baseflo/ui/icons';
import { useGateway } from '../../providers/GatewayProvider.js';
import { AGENTS, AGENT_ICON_MAP, TONE_STYLE_MAP } from '../../config/agents.js';

export function OrgDashboardView() {
  const { orgSlug } = useParams({ from: '/o/$orgSlug/' });
  const gateway = useGateway();

  const orgQuery = useQuery({
    queryKey: ['org', orgSlug],
    queryFn: () => gateway.orgs.get(orgSlug),
  });
  const projectsQuery = useQuery({
    queryKey: ['org', orgSlug, 'projects'],
    queryFn: () => gateway.projects.list(orgSlug),
  });

  if (orgQuery.isPending || projectsQuery.isPending) {
    return (
      <div className="grid gap-4 lg:grid-cols-2">
        <LoadingSkeletonCard />
        <LoadingSkeletonCard />
      </div>
    );
  }

  if (orgQuery.isError || projectsQuery.isError) {
    return (
      <ErrorCallout
        title="Couldn't load this organization"
        message="Refresh the page. If it keeps happening, contact support."
        action={{ label: 'Refresh', onClick: () => window.location.reload() }}
      />
    );
  }

  const projects = projectsQuery.data;

  const launchItems = [
    { id: 'connect', label: 'Connect first source', done: true },
    { id: 'workspace', label: 'Build workspace', done: projects.length > 0 },
    { id: 'invite', label: 'Invite a teammate', done: false },
    { id: 'digest', label: 'Set daily digest', done: false },
  ];

  const firstPending = launchItems.findIndex((i) => !i.done);

  return (
    <div className="flex flex-col gap-8">
      {/* Atmospheric hero */}
      <section className="-mx-6 -mt-8 bg-atmospheric px-6 py-10">
        <div className="flex flex-col gap-6 md:flex-row md:items-end md:justify-between">
          <div className="flex flex-col gap-2">
            <div className="flex items-center gap-2 text-sm font-medium text-success">
              <PulseDot size={8} active tone="success" />
              Agents ready
            </div>
            <h1 className="font-serif text-3xl font-semibold tracking-tight text-fg">
              {orgQuery.data.name}
            </h1>
            <p className="text-sm text-fg-muted">
              Plan: <span className="capitalize">{orgQuery.data.plan}</span> · Region:{' '}
              {orgQuery.data.region}
            </p>
          </div>

          {/* Quick actions */}
          <div className="flex items-center gap-2">
            <Button asChild variant="secondary">
              <Link to="/o/$orgSlug/start" params={{ orgSlug }}>
                <IconConnectors className="mr-1.5 h-4 w-4" />
                Connect tools
              </Link>
            </Button>
            <Button asChild>
              <Link to="/o/$orgSlug/projects/new" params={{ orgSlug }}>
                <IconPlus className="mr-1.5 h-4 w-4" />
                New project
              </Link>
            </Button>
          </div>
        </div>
      </section>

      {projects.length === 0 ? (
        <EmptyState
          icon={
            <div className="flex items-center gap-2">
              <IconSparkles className="h-8 w-8 text-accent" />
              <IconZap className="h-6 w-6 text-warning" />
            </div>
          }
          title="Initialize your first mission"
          description="Each project is one connected business. Stripe, Sheets, Shopify — drop them in and we'll reconcile."
          action={{
            label: 'New project',
            onClick: () => {
              window.location.href = `/o/${orgSlug}/projects/new`;
            },
          }}
          secondaryAction={{
            label: 'Drop my spreadsheet',
            onClick: () => {
              window.location.href = `/o/${orgSlug}/start`;
            },
          }}
        />
      ) : (
        <div className="grid gap-6 lg:grid-cols-3">
          <section className="lg:col-span-2">
            <div className="mb-3 flex items-center gap-2">
              <IconLayers className="h-4 w-4 text-fg-subtle" />
              <h2 className="text-sm font-semibold uppercase tracking-wide text-fg-subtle">
                Projects
              </h2>
            </div>
            <ul className="flex flex-col gap-3">
              {projects.map((p) => (
                <li key={p.id}>
                  <Link
                    to="/o/$orgSlug/p/$projectSlug"
                    params={{
                      orgSlug,
                      projectSlug: p.slug,
                    }}
                    className="block"
                  >
                    <Card className="group relative overflow-hidden border-l-4 border-l-accent bg-surface transition-all duration-normal hover:-translate-y-0.5 hover:shadow-lg">
                      <CardHeader>
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-3">
                            <div className="flex h-9 w-9 items-center justify-center rounded-md bg-accent-soft text-accent">
                              <IconDatabase className="h-4 w-4" />
                            </div>
                            <CardTitle>{p.name}</CardTitle>
                          </div>
                          <div className="flex items-center gap-2">
                            <DeploymentModeBadge mode={p.deploymentMode} />
                            <StatusChip value={p.status} />
                          </div>
                        </div>
                        {p.description && (
                          <CardDescription>{p.description}</CardDescription>
                        )}
                      </CardHeader>
                      <CardContent className="flex items-center justify-between text-xs text-fg-muted">
                        <span>Updated {format(new Date(p.updatedAt), 'MMM d, yyyy')}</span>
                        <IconArrowRight className="h-4 w-4 text-fg-subtle opacity-0 transition-opacity duration-fast group-hover:opacity-100" />
                      </CardContent>
                    </Card>
                  </Link>
                </li>
              ))}
            </ul>
          </section>

          <section className="flex flex-col gap-6">
            {/* Agent Fleet */}
            <div>
              <div className="mb-3 flex items-center gap-2">
                <IconSparkles className="h-4 w-4 text-fg-subtle" />
                <h2 className="text-sm font-semibold uppercase tracking-wide text-fg-subtle">
                  Agent Fleet
                </h2>
              </div>
              <Card>
                <CardContent className="p-4">
                  <div className="flex flex-col gap-3">
                    {AGENTS.map((agent) => {
                      const AgentIcon = AGENT_ICON_MAP[agent.icon];
                      const tone = TONE_STYLE_MAP[agent.tone];
                      return (
                        <div key={agent.id} className="flex items-center gap-3">
                          <div className={`flex h-8 w-8 items-center justify-center rounded-full ${tone.bg}`}>
                            {AgentIcon && <AgentIcon className={`h-3.5 w-3.5 ${tone.text}`} />}
                          </div>
                          <div className="flex-1">
                            <p className="text-sm font-medium text-fg">{agent.name}</p>
                            <p className="text-[11px] text-fg-subtle">{agent.role}</p>
                          </div>
                          <span className="h-1.5 w-1.5 rounded-full bg-success shadow-[0_0_4px_hsl(var(--color-success)/0.5)]" />
                        </div>
                      );
                    })}
                  </div>
                </CardContent>
              </Card>
            </div>

            {/* Launch Sequence */}
            <div>
              <div className="mb-3 flex items-center gap-2">
                <IconCommand className="h-4 w-4 text-fg-subtle" />
                <h2 className="text-sm font-semibold uppercase tracking-wide text-fg-subtle">
                  Launch sequence
                </h2>
              </div>
              <Card>
                <CardContent className="p-4">
                  <div className="flex flex-col gap-3">
                    {launchItems.map((item, i) => (
                      <OnboardingStep
                        key={item.id}
                        index={i + 1}
                        total={launchItems.length}
                        label={item.label}
                        status={
                          item.done ? 'done' : i === firstPending ? 'active' : 'pending'
                        }
                      />
                    ))}
                  </div>
                </CardContent>
              </Card>
            </div>
          </section>
        </div>
      )}
    </div>
  );
}
