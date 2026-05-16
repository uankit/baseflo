import { Link } from '@tanstack/react-router';
import { IconRefresh } from '@baseflo/ui/icons';
import type { OperatingRunResult } from '@baseflo/api-client';
import { useBusinessLiveArtifacts, useDataSources } from '../api/useOperatingData.js';
import { useOperatingRunStream } from '../api/useOperatingRunStream.js';
import { BusinessSectionCard, MetricStrip } from '../components/BusinessLiveCards.js';
import { RunProgress } from '../components/RunProgress.js';
import { EmptyPanel, ErrorPanel, LoadingPanel, PrimaryButton, ScreenFrame } from '../../common/components/StatePanels.js';
import { WhyPanel } from '../components/WhyPanel.js';
import { labelize, percent } from '../../common/model/format.js';

export function BusinessLiveScreen() {
  const live = useBusinessLiveArtifacts();
  const sources = useDataSources();
  const runner = useOperatingRunStream();
  const businessView = live.businessView.data;
  const businessSurfaces = live.businessSurfaces.data;
  const contractError = live.businessView.error ?? live.businessSurfaces.error;
  const noCanonicalData = hasNoCanonicalData(runner.result);
  const sourcesLoaded = !sources.isPending && !sources.isError;
  const hasConnectedSources = (sources.data?.length ?? 0) > 0;

  const refresh = () => {
    void runner.start({ mode: 'scan' }).catch(() => undefined);
  };

  if (live.isPending) {
    return (
      <ScreenFrame eyebrow="business live" title="Reconstructing your operating room">
        <LoadingPanel />
      </ScreenFrame>
    );
  }

  if (contractError) {
    return (
      <ScreenFrame eyebrow="business live" title="The server returned a package the UI cannot render yet">
        <ErrorPanel error={contractError} />
      </ScreenFrame>
    );
  }

  if (live.isError || !businessView || !businessSurfaces) {
    const needsSource = noCanonicalData || (sourcesLoaded && !hasConnectedSources);
    return (
      <ScreenFrame
        eyebrow="business live"
        title={needsSource ? 'Connect a source first' : 'Connect data, then let Baseflo build your business'}
        summary={
          needsSource
            ? 'Business Live needs at least one synced data source before Baseflo can build receivables, inventory, sales, products, expenses, and other operating surfaces.'
            : 'Business Live appears after the first operating run creates a business view and generated surfaces.'
        }
      >
        <RunProgress events={runner.events} isRunning={runner.isRunning} error={runner.error} />
        <EmptyPanel
          title={needsSource ? 'No canonical business data yet' : 'No Business Live artifact yet'}
          summary={
            needsSource
              ? 'Open Sources and connect or sync your first file/store. Once Baseflo has canonical rows, this button will build your live business model.'
              : 'Run the operating pipeline once Baseflo has at least one connected source. The backend will create sections like Receivables, Inventory, Sales, Products, Expenses, and Data Quality only when the data supports them.'
          }
          action={
            needsSource ? (
              <Link
                to="/workspace/sources"
                className="inline-flex items-center justify-center border border-flame bg-flame px-4 py-2 text-sm font-semibold text-white shadow-[2px_2px_0_rgba(28,25,20,0.85)] transition hover:-translate-y-px"
              >
                open sources
              </Link>
            ) : (
              <PrimaryButton onClick={refresh} disabled={runner.isRunning}>build business live</PrimaryButton>
            )
          }
        />
      </ScreenFrame>
    );
  }

  const surfacesByKind = new Map(businessSurfaces.surfaces.map((surface) => [surface.kind, surface]));
  const allMetrics = businessView.sections.flatMap((section) => section.metrics).slice(0, 4);

  return (
    <ScreenFrame
      eyebrow="business live · generated operating model"
      title={businessView.headline}
      summary={businessView.summary}
      action={
        <PrimaryButton onClick={refresh} disabled={runner.isRunning}>
          <IconRefresh className="mr-2 h-4 w-4" />
          refresh run
        </PrimaryButton>
      }
    >
      <RunProgress events={runner.events} isRunning={runner.isRunning} error={runner.error} />

      <div className="grid gap-5 lg:grid-cols-[1fr_360px]">
        <div className="space-y-5">
          <MetricStrip metrics={allMetrics} />
          <section className="grid gap-5">
            {businessView.sections.map((section) => (
              <BusinessSectionCard
                key={section.section_id}
                section={section}
                surface={surfacesByKind.get(section.kind)}
              />
            ))}
          </section>
        </div>

        <aside className="space-y-4">
          <WhyPanel title="why this exists">{businessView.why}</WhyPanel>
          <div className="border border-ink/20 bg-paper-soft p-4">
            <p className="font-sans text-[11px] font-semibold uppercase tracking-[0.22em] text-ink/45">
              built surfaces
            </p>
            <div className="mt-3 space-y-2">
              {businessSurfaces.surfaces.map((surface) => (
                <Link
                  key={surface.surface_id}
                  to="/workspace/ask"
                  search={{ q: surface.candidate_views[0]?.question ?? `Show me ${surface.title}` }}
                  className="block border border-ink/15 bg-white/35 p-3 hover:border-flame"
                >
                  <div className="flex items-center justify-between gap-3">
                    <strong className="text-sm text-ink">{surface.title}</strong>
                    <span className="font-mono text-[10px] text-ink/45">{percent(surface.confidence)}</span>
                  </div>
                  <p className="mt-1 text-xs leading-5 text-ink/55">{surface.description}</p>
                </Link>
              ))}
            </div>
          </div>
          <div className="border border-ink/20 bg-paper-soft p-4">
            <p className="font-sans text-[11px] font-semibold uppercase tracking-[0.22em] text-ink/45">
              available entities
            </p>
            <div className="mt-3 flex flex-wrap gap-2">
              {businessView.entity_views.map((entity) => (
                <span key={entity.entity} className="border border-ink/20 bg-paper px-2 py-1 text-xs text-ink/65">
                  {labelize(entity.plural)}
                </span>
              ))}
            </div>
          </div>
        </aside>
      </div>
    </ScreenFrame>
  );
}

function hasNoCanonicalData(result: OperatingRunResult | null): boolean {
  return Boolean(
    result?.errors.some((error) => {
      const details = error.details;
      return (
        typeof details === 'object' &&
        details !== null &&
        'code' in details &&
        details.code === 'NO_CANONICAL_DATA'
      );
    }),
  );
}
