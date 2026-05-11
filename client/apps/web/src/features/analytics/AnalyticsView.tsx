import { useParams } from '@tanstack/react-router';
import { useQuery } from '@tanstack/react-query';
import {
  Badge,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  EmptyState,
  ErrorCallout,
  LoadingSkeletonCard,
  MetricStrip,
  Progress,
} from '@baseflo/ui';
import { IconLightbulb, IconSparkles } from '@baseflo/ui/icons';
import { useGateway } from '../../providers/GatewayProvider.js';

export function AnalyticsView() {
  const { versionId } = useParams({
    from: '/o/$orgSlug/p/$projectSlug/v/$versionId',
  });
  const gateway = useGateway();

  const analyticsQuery = useQuery({
    queryKey: ['analytics', versionId],
    queryFn: () => gateway.workspace.getAnalytics(versionId),
  });

  if (analyticsQuery.isPending) {
    return (
      <div className="grid gap-4 lg:grid-cols-2">
        <LoadingSkeletonCard />
        <LoadingSkeletonCard />
      </div>
    );
  }
  if (analyticsQuery.isError) {
    return (
      <ErrorCallout
        title="Couldn't load analytics"
        message="Refresh and try again."
        action={{ label: 'Retry', onClick: () => analyticsQuery.refetch() }}
      />
    );
  }

  const a = analyticsQuery.data;

  return (
    <div className="flex flex-col gap-6">
      <header className="rounded-xl bg-atmospheric bg-grid-dots px-6 py-8">
        <div className="flex items-center gap-2">
          <IconLightbulb className="h-5 w-5 text-accent" />
          <h1 className="font-serif text-2xl font-semibold text-fg">Intelligence Briefing</h1>
        </div>
        <p className="mt-1 text-sm text-fg-muted">
          Schema-aware funnels, retention cohorts, top-N, geo, and lapsing detection.
        </p>
        <div className="mt-3">
          <Badge variant="accent">
            <IconSparkles className="mr-1 h-3 w-3" />
            Insight Agent generated this
          </Badge>
        </div>
      </header>

      <section>
        <div className="mb-3 flex items-center gap-2">
          <span className="h-px flex-1 bg-border" />
          <h2 className="text-xs font-bold uppercase tracking-widest text-fg-subtle">
            Funnel Analysis
          </h2>
          <span className="h-px flex-1 bg-border" />
        </div>
        {a.funnels.length === 0 ? (
          <EmptyState title="No funnels yet" />
        ) : (
          <div className="grid gap-4 lg:grid-cols-2">
            {a.funnels.map((funnel) => (
              <Card key={funnel.id} className="border-l-4 border-l-accent">
                <CardHeader>
                  <CardTitle>{funnel.name}</CardTitle>
                </CardHeader>
                <CardContent className="flex flex-col gap-3">
                  {funnel.steps.map((step, i) => {
                    const first = funnel.steps[0]?.count ?? 1;
                    const ratio = first ? step.count / first : 0;
                    return (
                      <div key={step.id} className="flex flex-col gap-1">
                        <div className="flex items-center justify-between text-sm">
                          <span className="text-fg">
                            <span className="text-fg-subtle">{i + 1}.</span> {step.label}
                          </span>
                          <span className="tabular-nums text-fg-muted">
                            {step.count.toLocaleString()}
                            {step.conversionRate != null && (
                              <Badge variant="info" className="ml-2">
                                {(step.conversionRate * 100).toFixed(1)}%
                              </Badge>
                            )}
                          </span>
                        </div>
                        <Progress value={ratio * 100} />
                      </div>
                    );
                  })}
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </section>

      <section>
        <div className="mb-3 flex items-center gap-2">
          <span className="h-px flex-1 bg-border" />
          <h2 className="text-xs font-bold uppercase tracking-widest text-fg-subtle">
            Retention Cohorts
          </h2>
          <span className="h-px flex-1 bg-border" />
        </div>
        {a.cohorts.length === 0 ? (
          <EmptyState title="No cohorts yet" />
        ) : (
          <div className="grid gap-4">
            {a.cohorts.map((c) => (
              <Card key={c.id} className="border-l-4 border-l-success">
                <CardHeader>
                  <CardTitle>{c.name}</CardTitle>
                </CardHeader>
                <CardContent>
                  <table className="w-full text-left text-sm">
                    <thead>
                      <tr className="text-xs text-fg-subtle">
                        <th scope="col" className="py-1 pr-3 text-left">
                          Cohort
                        </th>
                        <th scope="col" className="py-1 pr-3 text-right">
                          Size
                        </th>
                        {c.bucketLabels.map((label) => (
                          <th key={label} scope="col" className="py-1 pl-3 text-right">
                            {label}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {c.rows.map((row) => (
                        <tr key={row.cohortLabel} className="border-t border-border">
                          <td className="py-1 pr-3">{row.cohortLabel}</td>
                          <td className="py-1 pr-3 text-right tabular-nums">
                            {row.size.toLocaleString()}
                          </td>
                          {c.bucketLabels.map((_, i) => {
                            const ret = row.retention[i];
                            return (
                              <td key={i} className="py-1 pl-3 text-right tabular-nums">
                                {ret != null ? `${(ret * 100).toFixed(0)}%` : '—'}
                              </td>
                            );
                          })}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </section>

      <section>
        <div className="mb-3 flex items-center gap-2">
          <span className="h-px flex-1 bg-border" />
          <h2 className="text-xs font-bold uppercase tracking-widest text-fg-subtle">
            Top-N Rankings
          </h2>
          <span className="h-px flex-1 bg-border" />
        </div>
        <MetricStrip>
          {a.topN.map((list) => (
            <Card key={list.id} className="border-l-4 border-l-info">
              <CardHeader>
                <CardTitle>{list.name}</CardTitle>
              </CardHeader>
              <CardContent>
                <ol className="flex flex-col gap-1">
                  {list.rows.map((r, i) => (
                    <li key={i} className="flex items-center justify-between text-sm">
                      <span className="text-fg">{r.label}</span>
                      <span className="font-mono tabular-nums text-fg-muted">
                        {r.value.toLocaleString()} {r.unit ?? ''}
                      </span>
                    </li>
                  ))}
                </ol>
              </CardContent>
            </Card>
          ))}
        </MetricStrip>
      </section>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card className="border-l-4 border-l-warning">
          <CardHeader>
            <CardTitle>Geography</CardTitle>
          </CardHeader>
          <CardContent>
            {a.geo.length === 0 ? (
              <p className="text-sm text-fg-muted">No location data yet.</p>
            ) : (
              <ul className="flex flex-col gap-1">
                {a.geo.map((g) => (
                  <li key={g.region} className="flex items-center justify-between text-sm">
                    <span className="text-fg">{g.region}</span>
                    <span className="tabular-nums text-fg-muted">
                      {g.count.toLocaleString()}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
        <Card className="border-l-4 border-l-danger">
          <CardHeader>
            <CardTitle>Lapsing</CardTitle>
          </CardHeader>
          <CardContent>
            {a.lapsing.length === 0 ? (
              <p className="text-sm text-fg-muted">No lapsing entities detected.</p>
            ) : (
              <ul className="flex flex-col gap-2">
                {a.lapsing.map((l) => (
                  <li key={l.entityId} className="text-sm">
                    <div className="flex items-center justify-between">
                      <span className="font-medium text-fg">{l.label}</span>
                      <Badge variant="warning">{l.reason}</Badge>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      </div>

      <div className="flex justify-center pb-4">
        <Badge variant="neutral" className="text-[10px]">
          <IconSparkles className="mr-1 h-3 w-3" />
          Generated by Insight Agent · {new Date().toLocaleDateString()}
        </Badge>
      </div>
    </div>
  );
}
