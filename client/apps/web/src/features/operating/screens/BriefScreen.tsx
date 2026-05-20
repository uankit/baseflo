import { Link } from '@tanstack/react-router';
import { Counter } from '@baseflo/ui/composites';
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
      <ScreenFrame eyebrow="brief" title="Preparing today's operating brief">
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

  const body = briefPackage.body || briefPackage.summary_points?.join('\n\n') || '';

  return (
    <ScreenFrame eyebrow="today's brief" title={briefPackage.headline}>
      <div className="grid gap-5 lg:grid-cols-[1fr_360px]">
        <section className="space-y-5">
          <article className="border border-ink/25 bg-paper-soft p-6 shadow-[3px_3px_0_rgba(28,25,20,0.1)]">
            <div
              className="prose prose-neutral max-w-none text-base leading-7 text-ink/80"
              style={{ whiteSpace: 'pre-wrap' }}
            >
              {body}
            </div>
          </article>

          {rankingPackage?.ranked.length ? (
            <section>
              <p className="mb-3 font-sans text-[11px] font-semibold uppercase tracking-[0.22em] text-ink/45">
                ranked operating items
              </p>
              <div className="space-y-3">
                {rankingPackage.ranked.slice(0, 8).map((item) => (
                  <article
                    key={`${item.item_kind}:${item.item_id}`}
                    className="border border-ink/20 bg-paper-soft p-4 shadow-[2px_2px_0_rgba(28,25,20,0.06)]"
                  >
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

          {briefPackage.urgent_artifact_ids?.length ? (
            <div className="border border-flame/30 bg-flame/[0.03] p-4 shadow-[2px_2px_0_rgba(220,84,37,0.15)]">
              <p className="font-sans text-[11px] font-semibold uppercase tracking-[0.22em] text-ink/45">
                urgent items
              </p>
              <div className="mt-2 flex items-baseline gap-2">
                <Counter
                  value={briefPackage.urgent_artifact_ids.length}
                  animate
                  className="font-serif text-5xl font-bold italic text-flame"
                />
                <span className="text-sm text-ink/55">needs attention</span>
              </div>
            </div>
          ) : null}
        </aside>
      </div>
    </ScreenFrame>
  );
}
