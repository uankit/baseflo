import { IconRefresh, IconSparkles } from '@baseflo/ui/icons';
import {
  actionBacklog,
  asRecordArray,
  asString,
  asStringArray,
  businessBrief,
  businessModel,
  crossTeamReport,
  insightActions,
  lastSyncedLabel,
  topInsights,
  useOperatingBrief,
  useOperatingScan,
} from './operatingData.js';
import {
  EmptyPaper,
  InferenceRow,
  LoadingPaper,
  MetricChip,
  PageKicker,
  PrimaryButton,
  SectionTitle,
  TagPill,
  formatValue,
  teamLabel,
  titleCase,
} from './OperatingUI.js';

export function OperatingDashboard() {
  const briefQuery = useOperatingBrief();
  const scan = useOperatingScan();
  const brief = briefQuery.data;
  const business = businessBrief(brief);
  const model = businessModel(brief);
  const cross = crossTeamReport(brief);
  const insights = topInsights(brief);
  const actions = actionBacklog(brief);
  const signals = asRecordArray(business.signals);
  const questions = asStringArray(brief?.business?.recommended_questions);
  const syncedLabel = lastSyncedLabel(brief);

  if (briefQuery.isLoading) return <LoadingPaper />;

  const headline =
    asString(business.title) ||
    asString(cross.standup_summary) ||
    (insights.length ? asString(insights[0]?.title) : 'Connect data to start the brief');
  const dek =
    asString(business.summary) ||
    asString(model.paragraph) ||
    'Baseflo will turn connected sources into inferences, evidence, and actions.';
  const assumptions = asRecordArray(model.assumptions);
  const missing = Array.isArray(model.missing_or_failed_sources)
    ? model.missing_or_failed_sources.filter((item): item is string => typeof item === 'string')
    : [];
  const urgent = insights.filter((insight) => asString(insight.severity) === 'warning').length;

  return (
    <div className="min-h-[calc(100vh-53px)] bg-paper px-4 py-6 text-ink md:px-8">
      <div className="mx-auto max-w-[1380px]">
        <header className="border-b-2 border-ink pb-7">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <PageKicker>Today&apos;s brief · founder view</PageKicker>
            <div className="flex flex-wrap items-center gap-2">
              <TagPill active>{insights.length} inferences</TagPill>
              <TagPill>{urgent} urgent</TagPill>
              <TagPill>{actions.length} actions</TagPill>
              {syncedLabel ? <span className="font-mono text-[11px] text-ink/45">read {syncedLabel}</span> : null}
              <PrimaryButton
                onClick={() => scan.mutate()}
                disabled={scan.isPending}
                variant="outline"
                icon={<IconRefresh className={`h-3.5 w-3.5 ${scan.isPending ? 'animate-spin' : ''}`} />}
              >
                refresh
              </PrimaryButton>
            </div>
          </div>
          <h1 className="mt-5 max-w-[1120px] font-serif text-[42px] font-bold italic leading-[1.02] tracking-tight md:text-[64px]">
            {headline}
          </h1>
          <p className="mt-5 max-w-[760px] font-sans text-[16px] leading-7 text-ink/68">{dek}</p>
        </header>

        <section className="grid gap-6 py-7 lg:grid-cols-[minmax(0,1fr)_340px]">
          <div className="space-y-3">
            <SectionTitle>Live operating reads</SectionTitle>
            {insights.length ? (
              insights.map((insight) => (
                <InferenceRow
                  key={asString(insight.id, asString(insight.title))}
                  insight={insight}
                  actions={insightActions(insight, brief)}
                />
              ))
            ) : (
              <EmptyPaper
                title="No inferences yet"
                body="Once Shopify or another source syncs, this page fills with grounded reads and suggested moves."
              />
            )}
          </div>

          <aside className="space-y-5">
            <section>
              <SectionTitle>Signals</SectionTitle>
              <div className="grid gap-2">
                {signals.length ? (
                  signals.slice(0, 6).map((signal, index) => (
                    <MetricChip
                      key={`${asString(signal.label)}-${index}`}
                      label={asString(signal.label, `Signal ${index + 1}`)}
                      value={asString(signal.value, formatValue(signal.value))}
                      tone={asString(signal.tone) === 'warn' ? 'warn' : asString(signal.tone) === 'good' ? 'good' : 'neutral'}
                    />
                  ))
                ) : (
                  <MetricChip label="business state" value={`${brief?.summary.assets ?? 0} assets`} />
                )}
              </div>
            </section>

            <section className="border border-ink/35 bg-paper-soft p-4">
              <SectionTitle>Baseflo&apos;s read</SectionTitle>
              <p className="font-serif text-[15px] italic leading-7 text-ink/78">
                {asString(model.paragraph, 'The connected source is being profiled.')}
              </p>
            </section>

            {actions.length ? (
              <section className="border border-ink/35 bg-paper-soft p-4">
                <SectionTitle>Action queue</SectionTitle>
                <div className="space-y-3">
                  {actions.slice(0, 4).map((action, index) => (
                    <div key={asString(action.id, `action-${index}`)} className="border-l-2 border-flame pl-3">
                      <div className="font-sans text-sm font-bold leading-snug">{asString(action.title, 'Action')}</div>
                      <div className="mt-1 font-mono text-[10px] uppercase tracking-[0.12em] text-ink/45">
                        {titleCase(asString(action.execution_mode, 'prepare'))}
                      </div>
                    </div>
                  ))}
                </div>
              </section>
            ) : null}

            {(assumptions.length || missing.length || questions.length) ? (
              <section className="border border-ink/35 bg-white/45 p-4">
                <SectionTitle>Edges</SectionTitle>
                <div className="space-y-4">
                  {assumptions.length ? (
                    <div>
                      <div className="font-mono text-[10px] uppercase tracking-[0.14em] text-ink/45">Assumptions</div>
                      <ul className="mt-2 space-y-2 font-sans text-[12px] leading-5 text-ink/65">
                        {assumptions.slice(0, 3).map((assumption, index) => (
                          <li key={index}>· {asString(assumption.text)}</li>
                        ))}
                      </ul>
                    </div>
                  ) : null}
                  {missing.length ? (
                    <div>
                      <div className="font-mono text-[10px] uppercase tracking-[0.14em] text-flame">Missing</div>
                      <ul className="mt-2 space-y-2 font-sans text-[12px] leading-5 text-ink/65">
                        {missing.slice(0, 3).map((item, index) => (
                          <li key={index}>· {item}</li>
                        ))}
                      </ul>
                    </div>
                  ) : null}
                  {questions.length ? (
                    <div>
                      <div className="font-mono text-[10px] uppercase tracking-[0.14em] text-ink/45">Ask next</div>
                      <div className="mt-2 space-y-2">
                        {questions.slice(0, 3).map((question, index) => (
                          <div key={index} className="flex gap-2 font-sans text-[12px] leading-5 text-ink/70">
                            <IconSparkles className="mt-0.5 h-3.5 w-3.5 shrink-0 text-flame" />
                            {question}
                          </div>
                        ))}
                      </div>
                    </div>
                  ) : null}
                </div>
              </section>
            ) : null}

            {asRecordArray(cross.alignments).length || asRecordArray(cross.conflicts).length || asRecordArray(cross.gaps).length ? (
              <section className="border border-ink/35 bg-paper-soft p-4">
                <SectionTitle>Across teams</SectionTitle>
                <div className="space-y-3">
                  {asRecordArray(cross.alignments).slice(0, 2).map((item, index) => (
                    <CrossNote key={`align-${index}`} label={teamLabel((item.teams as unknown[])?.[0])} body={asString(item.claim)} />
                  ))}
                  {asRecordArray(cross.conflicts).slice(0, 2).map((item, index) => (
                    <CrossNote key={`conflict-${index}`} label="Conflict" body={asString(item.claim)} tone="warn" />
                  ))}
                  {asRecordArray(cross.gaps).slice(0, 2).map((item, index) => (
                    <CrossNote key={`gap-${index}`} label="Gap" body={asString(item.claim)} tone="warn" />
                  ))}
                </div>
              </section>
            ) : null}
          </aside>
        </section>
      </div>
    </div>
  );
}

function CrossNote({ label, body, tone = 'neutral' }: { label: string; body: string; tone?: 'neutral' | 'warn' }) {
  return (
    <div className="border-l-2 border-ink/35 pl-3">
      <div className={`font-mono text-[10px] uppercase tracking-[0.14em] ${tone === 'warn' ? 'text-flame' : 'text-ink/45'}`}>
        {label}
      </div>
      <p className="mt-1 font-sans text-[12px] leading-5 text-ink/70">{body}</p>
    </div>
  );
}
