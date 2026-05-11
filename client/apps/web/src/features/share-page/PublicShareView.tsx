import { useParams } from '@tanstack/react-router';
import { useQuery } from '@tanstack/react-query';
import { format } from 'date-fns';
import {
  Badge,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  ErrorCallout,
  KPIWidget,
  MetricStrip,
  Spinner,
} from '@baseflo/ui';
import { IconSparkles, IconLightbulb, IconWarning } from '@baseflo/ui/icons';
import { useGateway } from '../../providers/GatewayProvider.js';
import { ShareShell } from '../../layouts/ShareShell.js';

export function PublicShareView() {
  const { shareToken } = useParams({ from: '/s/$shareToken' });
  const gateway = useGateway();

  const shareQuery = useQuery({
    queryKey: ['public-share', shareToken],
    queryFn: () => gateway.shareLinks.publicGet(shareToken),
    retry: 1,
  });

  if (shareQuery.isPending) {
    return (
      <ShareShell ownerOrgName="—">
        <div className="flex items-center justify-center py-16">
          <Spinner />
        </div>
      </ShareShell>
    );
  }

  if (shareQuery.isError) {
    return (
      <ShareShell ownerOrgName="—">
        <ErrorCallout
          title="This link is unavailable"
          message="It may have been revoked or expired. Ask the owner for a new one."
        />
      </ShareShell>
    );
  }

  const s = shareQuery.data;

  return (
    <ShareShell ownerOrgName={s.ownerOrgName}>
      <article className="flex flex-col gap-8">
        <header className="flex flex-col gap-3">
          <Badge variant="info" className="self-start">
            Generated {format(new Date(s.generatedAt), 'MMM d, yyyy')}
          </Badge>
          <h1 className="text-3xl font-semibold tracking-tight text-fg">{s.projectName}</h1>
          <p className="font-serif text-lg leading-relaxed text-fg-muted">{s.businessSummary}</p>
        </header>

        <section>
          <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-fg-subtle">
            Highlights
          </h2>
          <MetricStrip>
            {s.kpis.map((kpi, i) => (
              <KPIWidget
                key={i}
                label={kpi.label}
                value={kpi.value}
                caption={kpi.caption}
              />
            ))}
          </MetricStrip>
        </section>

        {s.topAssumptions.length > 0 && (
          <Card className="relative overflow-hidden border-l-4 border-l-accent">
            <div className="absolute right-4 top-4 text-accent/20">
              <IconLightbulb className="h-12 w-12" />
            </div>
            <CardHeader>
              <CardTitle>Top assumptions</CardTitle>
            </CardHeader>
            <CardContent>
              <ul className="flex list-disc flex-col gap-2.5 pl-5 text-sm text-fg-muted">
                {s.topAssumptions.map((a, i) => (
                  <li key={i}>{a}</li>
                ))}
              </ul>
            </CardContent>
          </Card>
        )}

        {s.topRisks.length > 0 && (
          <Card className="relative overflow-hidden border-l-4 border-l-warning">
            <div className="absolute right-4 top-4 text-warning/20">
              <IconWarning className="h-12 w-12" />
            </div>
            <CardHeader>
              <CardTitle>Top risks</CardTitle>
            </CardHeader>
            <CardContent>
              <ul className="flex list-disc flex-col gap-2.5 pl-5 text-sm text-fg-muted">
                {s.topRisks.map((r, i) => (
                  <li key={i}>{r}</li>
                ))}
              </ul>
            </CardContent>
          </Card>
        )}

        <div className="flex items-center gap-2 rounded-lg border border-dashed border-border bg-surface p-4 text-xs text-fg-muted">
          <IconSparkles className="h-4 w-4 text-accent" />
          <span>
            This workspace was synthesized by Baseflo's Insight Agent from live business data.
          </span>
        </div>
      </article>
    </ShareShell>
  );
}
