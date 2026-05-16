import { Link } from '@tanstack/react-router';
import { IconConnectors } from '@baseflo/ui/icons';
import { useDataSources, useSourceIntelligenceArtifacts } from '../api/useOperatingData.js';
import { EmptyPanel, ErrorPanel, LoadingPanel, PrimaryButton, ScreenFrame } from '../../common/components/StatePanels.js';
import { WhyPanel } from '../components/WhyPanel.js';
import { compactDateTime, labelize, statusTone } from '../../common/model/format.js';

export function SourcesScreen() {
  const sources = useDataSources();
  const intelligence = useSourceIntelligenceArtifacts();

  if (sources.isPending) {
    return (
      <ScreenFrame eyebrow="sources" title="Loading connected data sources">
        <LoadingPanel />
      </ScreenFrame>
    );
  }

  if (sources.isError) {
    return (
      <ScreenFrame eyebrow="sources" title="Could not load sources">
        <ErrorPanel error={sources.error} />
      </ScreenFrame>
    );
  }

  return (
    <ScreenFrame
      eyebrow="sources · trust and lineage"
      title="The data plane behind Baseflo"
      summary="Sources is where connected data, canonical assets, semantic objects, lineage, and graph materialization are visible."
      action={
        <Link to="/connectors">
          <PrimaryButton>
            <IconConnectors className="mr-2 h-4 w-4" />
            connect source
          </PrimaryButton>
        </Link>
      }
    >
      <div className="grid gap-5 lg:grid-cols-[1fr_380px]">
        <section className="space-y-4">
          {sources.data?.length ? (
            sources.data.map((source) => (
              <article key={source.id} className="border border-ink/25 bg-paper-soft p-5">
                <div className="flex flex-wrap items-start justify-between gap-4">
                  <div>
                    <p className="font-mono text-[11px] uppercase tracking-[0.16em] text-ink/40">
                      {source.kind} · {source.id}
                    </p>
                    <h2 className="mt-2 font-serif text-3xl font-bold italic text-ink">{source.name}</h2>
                  </div>
                  <span className={`border px-2 py-1 text-xs font-semibold ${toneClass(statusTone(source.status))}`}>
                    {labelize(source.status)}
                  </span>
                </div>
                <div className="mt-4 grid gap-3 sm:grid-cols-3">
                  <SourceMeta label="created" value={compactDateTime(source.created_at)} />
                  <SourceMeta label="last sync" value={compactDateTime(source.last_synced_at)} />
                  <SourceMeta label="tables" value={String(tableCount(source.discovered_schema))} />
                </div>
                {source.last_error ? (
                  <p className="mt-4 border-l-2 border-flame pl-3 text-sm leading-6 text-flame">
                    {source.last_error}
                  </p>
                ) : null}
              </article>
            ))
          ) : (
            <EmptyPanel
              title="No sources connected yet"
              summary="Connect a source first. Baseflo will canonicalize the raw data, profile it, and then build the operating model."
            />
          )}
        </section>

        <aside className="space-y-4">
          {intelligence.error ? <ErrorPanel error={intelligence.error} /> : null}
          <PackageStat
            label="semantic entities"
            value={String(intelligence.semanticLayer.data?.entities.length ?? 0)}
            why="Entities are the user-facing business nouns Baseflo found."
          />
          <PackageStat
            label="semantic metrics"
            value={String(intelligence.semanticLayer.data?.metrics.length ?? 0)}
            why="Metrics govern the measures available for Brief, Business Live, and Ask."
          />
          <PackageStat
            label="chart specs"
            value={String(intelligence.chartGrammar.data?.charts.length ?? 0)}
            why="Charts are emitted as typed grammar instead of prose."
          />
          <PackageStat
            label="knowledge graph"
            value={`${intelligence.knowledgeGraph.data?.node_count ?? 0} nodes`}
            why={`${intelligence.knowledgeGraph.data?.edge_count ?? 0} edges materialized in Kuzu when available.`}
          />
          <WhyPanel title="lineage">
            {intelligence.lineage.data
              ? `${intelligence.lineage.data.runs.length} lineage runs and ${intelligence.lineage.data.datasets.length} datasets are available.`
              : 'Lineage appears after an operating run creates the lineage artifact.'}
          </WhyPanel>
        </aside>
      </div>
    </ScreenFrame>
  );
}

function SourceMeta({ label, value }: { label: string; value: string }) {
  return (
    <div className="border border-ink/15 bg-paper px-3 py-2">
      <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-ink/40">{label}</p>
      <p className="mt-1 text-sm font-semibold text-ink">{value}</p>
    </div>
  );
}

function PackageStat({ label, value, why }: { label: string; value: string; why: string }) {
  return (
    <div className="border border-ink/20 bg-paper-soft p-4">
      <p className="font-sans text-[11px] font-semibold uppercase tracking-[0.22em] text-ink/45">
        {label}
      </p>
      <p className="mt-2 font-serif text-4xl font-bold italic text-ink">{value}</p>
      <p className="mt-2 text-xs leading-5 text-ink/55">{why}</p>
    </div>
  );
}

function tableCount(schema: Record<string, unknown> | null | undefined): number {
  const tables = schema?.tables;
  return Array.isArray(tables) ? tables.length : 0;
}

function toneClass(tone: 'good' | 'warning' | 'neutral'): string {
  if (tone === 'good') return 'border-moss/40 bg-moss/10 text-moss';
  if (tone === 'warning') return 'border-flame/50 bg-flame/10 text-flame';
  return 'border-ink/20 bg-paper text-ink/55';
}
