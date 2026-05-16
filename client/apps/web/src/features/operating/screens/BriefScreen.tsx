import { Link } from '@tanstack/react-router';
import { useBriefArtifact, useInsightRanking } from '../api/useOperatingData.js';
import { EmptyPanel, ErrorPanel, LoadingPanel, ScreenFrame, SecondaryButton } from '../../common/components/StatePanels.js';
import { TagList, WhyPanel } from '../components/WhyPanel.js';
import { labelize, percent } from '../../common/model/format.js';

export function BriefScreen() {
  const brief = useBriefArtifact();
  const ranking = useInsightRanking();
  const briefPackage = brief.parsed.data;
  const rankingPackage = ranking.parsed.data;
  const contractError = brief.parsed.error ?? ranking.parsed.error;

  if (brief.isPending) {
    return (
      <ScreenFrame eyebrow="brief" title="Preparing today’s operating brief">
        <LoadingPanel />
      </ScreenFrame>
    );
  }

  if (contractError) {
    return (
      <ScreenFrame eyebrow="brief" title="Brief contract mismatch">
        <ErrorPanel error={contractError} />
      </ScreenFrame>
    );
  }

  if (brief.isError || !briefPackage) {
    return (
      <ScreenFrame eyebrow="brief" title="No brief yet">
        <EmptyPanel
          title="Baseflo has not created a brief artifact yet"
          summary="Run Business Live after connecting data. The brief is generated from the same operating run and will show the highest-signal reads."
          action={
            <Link to="/workspace/business">
              <SecondaryButton>open business live</SecondaryButton>
            </Link>
          }
        />
      </ScreenFrame>
    );
  }

  return (
    <ScreenFrame
      eyebrow="today’s brief · generated from the latest run"
      title={briefPackage.headline}
      summary={briefPackage.summary_points.join(' ')}
    >
      <div className="grid gap-5 lg:grid-cols-[1fr_360px]">
        <section className="space-y-4">
          {briefPackage.summary_points.map((point, index) => (
            <article key={point} className="border border-ink/25 bg-paper-soft p-5">
              <p className="font-mono text-[11px] uppercase tracking-[0.16em] text-ink/40">
                brief point {index + 1}
              </p>
              <p className="mt-2 text-lg leading-7 text-ink">{point}</p>
            </article>
          ))}
          {rankingPackage?.ranked.length ? (
            <section className="mt-8">
              <p className="mb-3 font-sans text-[11px] font-semibold uppercase tracking-[0.22em] text-ink/45">
                ranked operating items
              </p>
              <div className="space-y-3">
                {rankingPackage.ranked.slice(0, 8).map((item) => (
                  <article key={`${item.item_kind}:${item.item_id}`} className="border border-ink/20 bg-paper-soft p-4">
                    <div className="flex items-start justify-between gap-4">
                      <div>
                        <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-ink/40">
                          #{item.rank} · {labelize(item.item_kind)}
                        </p>
                        <h2 className="mt-1 font-serif text-2xl font-bold italic text-ink">{item.title}</h2>
                      </div>
                      <span className="font-mono text-xs text-ink/50">{percent(item.score)}</span>
                    </div>
                    <p className="mt-2 text-sm leading-6 text-ink/65">{item.why_ranked}</p>
                    <div className="mt-3">
                      <TagList tags={item.tags} />
                    </div>
                  </article>
                ))}
              </div>
            </section>
          ) : null}
        </section>
        <aside className="space-y-4">
          <WhyPanel title="why this brief">{briefPackage.why}</WhyPanel>
          <div className="border border-ink/20 bg-paper-soft p-4">
            <p className="font-sans text-[11px] font-semibold uppercase tracking-[0.22em] text-ink/45">
              urgent refs
            </p>
            <p className="mt-2 font-serif text-4xl font-bold italic text-ink">
              {briefPackage.urgent_artifact_ids.length}
            </p>
            <p className="mt-1 text-xs text-ink/55">artifact ids attached by the backend</p>
          </div>
        </aside>
      </div>
    </ScreenFrame>
  );
}
