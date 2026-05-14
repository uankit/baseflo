import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useMemo, useState } from 'react';
import { IconCheck, IconRefresh, IconX } from '@baseflo/ui/icons';
import { useGateway } from '../../providers/GatewayProvider.js';
import {
  asRecord,
  asRecordArray,
  asString,
  insightActions,
  topInsights,
  useOperatingBrief,
} from './operatingData.js';
import {
  ActionCard,
  EmptyPaper,
  EvidenceTable,
  LoadingPaper,
  PageKicker,
  PrimaryButton,
  SectionTitle,
  TagPill,
  compactRow,
  insightAudience,
  insightTags,
  insightTeam,
  teamLabel,
  titleCase,
} from './OperatingUI.js';

type DetailTab = 'actions' | 'evidence' | 'audience' | 'lineage';

export function OperatingInbox() {
  const gateway = useGateway();
  const queryClient = useQueryClient();
  const briefQuery = useOperatingBrief();
  const brief = briefQuery.data;
  const insights = topInsights(brief);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [activeTag, setActiveTag] = useState<string>('all');
  const [detailTab, setDetailTab] = useState<DetailTab>('actions');

  const tags = useMemo(() => {
    const all = new Set<string>();
    insights.forEach((insight) => insightTags(insight).forEach((tag) => all.add(tag)));
    return ['all', ...Array.from(all).sort()];
  }, [insights]);

  const filtered = activeTag === 'all'
    ? insights
    : insights.filter((insight) => insightTags(insight).includes(activeTag));
  const activeInsight =
    filtered.find((insight) => asString(insight.id) === activeId) ??
    filtered[0] ??
    insights[0];
  const activeActions = insightActions(activeInsight, brief);
  const rows = asRecordArray(activeInsight?.result_preview);
  const lineage = asRecordArray(activeInsight?.lineage);

  const approve = useMutation({
    mutationFn: (actionId: string) => gateway.operating.approveAction(actionId),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['operating', 'brief'] });
    },
  });

  const dismiss = useMutation({
    mutationFn: (insightId: string) => gateway.operating.dismissInsight(insightId),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['operating', 'brief'] });
    },
  });

  if (briefQuery.isLoading) return <LoadingPaper label="Opening action desk…" />;

  return (
    <div className="grid h-[calc(100vh-53px)] bg-paper text-ink lg:grid-cols-[360px_minmax(0,1fr)]">
      <aside className="min-h-0 border-r border-ink/20 bg-paper-soft">
        <div className="border-b border-ink/18 p-4">
          <PageKicker>Inbox · action desk</PageKicker>
          <h1 className="mt-2 font-serif text-[34px] font-bold italic leading-none">
            {insights.length} open reads
          </h1>
          <div className="mt-4 flex flex-wrap gap-2">
            {tags.map((tag) => (
              <button key={tag} type="button" onClick={() => setActiveTag(tag)}>
                <TagPill active={tag === activeTag}>{tag === 'all' ? 'all' : titleCase(tag)}</TagPill>
              </button>
            ))}
          </div>
        </div>

        <div className="h-[calc(100vh-199px)] overflow-auto">
          {filtered.length ? (
            filtered.map((insight) => {
              const id = asString(insight.id);
              const selected = asString(activeInsight?.id) === id;
              const actions = insightActions(insight, brief);
              return (
                <button
                  key={id || asString(insight.title)}
                  type="button"
                  onClick={() => {
                    setActiveId(id);
                    setDetailTab(actions.length ? 'actions' : 'evidence');
                  }}
                  className={`block w-full border-b border-ink/12 border-l-4 p-4 text-left transition hover:bg-white/55 ${
                    selected ? 'border-l-flame bg-white/75' : 'border-l-transparent'
                  }`}
                >
                  <div className="mb-2 flex items-center gap-2">
                    <TagPill active={selected}>{teamLabel(insightTeam(insight))}</TagPill>
                    <span className="font-mono text-[10px] uppercase tracking-[0.12em] text-ink/38">
                      {actions.length} action{actions.length === 1 ? '' : 's'}
                    </span>
                  </div>
                  <div className="font-serif text-[19px] font-bold italic leading-tight text-ink">
                    {asString(insight.title, 'Untitled inference')}
                  </div>
                  <div className="mt-2 font-mono text-[10px] text-ink/45">
                    {insightAudience(insight)}
                  </div>
                </button>
              );
            })
          ) : (
            <div className="p-4">
              <EmptyPaper title="No matching reads" />
            </div>
          )}
        </div>
      </aside>

      <main className="min-h-0 overflow-auto p-5 md:p-8">
        {!activeInsight ? (
          <EmptyPaper title="Inbox is clear" body="New reads will arrive here when Baseflo scans connected data." />
        ) : (
          <div className="mx-auto max-w-[1120px]">
            <header className="border-b-2 border-ink pb-5">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div className="min-w-0">
                  <div className="mb-3 flex flex-wrap items-center gap-2">
                    <TagPill active>{teamLabel(insightTeam(activeInsight))}</TagPill>
                    {insightTags(activeInsight).slice(0, 5).map((tag) => (
                      <TagPill key={tag}>{titleCase(tag)}</TagPill>
                    ))}
                  </div>
                  <h1 className="max-w-[900px] font-serif text-[40px] font-bold italic leading-[1.04] md:text-[56px]">
                    {asString(activeInsight.title, 'Untitled inference')}
                  </h1>
                </div>
                <div className="flex gap-2">
                  <PrimaryButton
                    variant="outline"
                    disabled={dismiss.isPending}
                    onClick={() => {
                      const id = asString(activeInsight.id);
                      if (id) dismiss.mutate(id);
                    }}
                    icon={<IconX className="h-3.5 w-3.5" />}
                  >
                    dismiss
                  </PrimaryButton>
                  <PrimaryButton variant="outline" icon={<IconRefresh className="h-3.5 w-3.5" />}>
                    snooze
                  </PrimaryButton>
                </div>
              </div>
              <p className="mt-4 max-w-[760px] font-sans text-[15px] leading-7 text-ink/72">
                {asString(activeInsight.summary, asString(activeInsight.why))}
              </p>
              <div className="mt-4 border-l-2 border-flame pl-4 font-sans text-sm leading-6 text-ink/70">
                {asString(activeInsight.why, 'The evidence is attached below.')}
              </div>
            </header>

            <div className="mt-5 flex flex-wrap gap-2 border-b border-ink/18 pb-3">
              {(['actions', 'evidence', 'audience', 'lineage'] as const).map((tab) => (
                <button
                  key={tab}
                  type="button"
                  onClick={() => setDetailTab(tab)}
                  className={`border px-3 py-1.5 font-sans text-[12px] font-bold ${
                    detailTab === tab ? 'border-ink bg-ink text-paper' : 'border-ink/35 bg-paper text-ink/65 hover:bg-white'
                  }`}
                >
                  {titleCase(tab)}
                </button>
              ))}
            </div>

            <section className="mt-5">
              {detailTab === 'actions' ? (
                <div>
                  <SectionTitle>Choose one</SectionTitle>
                  {activeActions.length ? (
                    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                      {activeActions.map((action) => (
                        <ActionCard
                          key={asString(action.id, asString(action.title))}
                          action={action}
                          onApprove={(id) => approve.mutate(id)}
                          disabled={approve.isPending}
                        />
                      ))}
                    </div>
                  ) : (
                    <EmptyPaper title="No action drafted yet" body="The evidence is still available for review." />
                  )}
                </div>
              ) : null}

              {detailTab === 'evidence' ? (
                <div>
                  <SectionTitle>Evidence rows</SectionTitle>
                  <EvidenceTable rows={rows} />
                </div>
              ) : null}

              {detailTab === 'audience' ? (
                <div className="grid gap-4 lg:grid-cols-[1fr_300px]">
                  <div>
                    <SectionTitle>Audience preview</SectionTitle>
                    <EvidenceTable rows={rows} compact />
                  </div>
                  <div className="border border-ink/35 bg-paper-soft p-4">
                    <SectionTitle>Affected set</SectionTitle>
                    <div className="font-serif text-4xl font-bold italic">{insightAudience(activeInsight)}</div>
                    <p className="mt-3 font-sans text-sm leading-6 text-ink/62">
                      {rows[0] ? compactRow(rows[0], 5) : 'No preview rows attached.'}
                    </p>
                  </div>
                </div>
              ) : null}

              {detailTab === 'lineage' ? (
                <div>
                  <SectionTitle>Why this read exists</SectionTitle>
                  {lineage.length ? (
                    <div className="space-y-2">
                      {lineage.map((item, index) => (
                        <div key={index} className="border border-ink/25 bg-paper-soft p-3 font-mono text-[11px] leading-5 text-ink/62">
                          {Object.entries(item)
                            .map(([key, value]) => `${key}: ${String(value)}`)
                            .join(' · ')}
                        </div>
                      ))}
                    </div>
                  ) : (
                    <pre className="overflow-auto border border-ink/25 bg-paper-soft p-4 text-[11px] text-ink/62">
                      {JSON.stringify(asRecord(activeInsight.analysis_graph), null, 2)}
                    </pre>
                  )}
                </div>
              ) : null}
            </section>

            {asString(activeInsight.status) === 'approved' ? (
              <div className="mt-6 flex items-center gap-2 border border-moss/45 bg-emerald-50 p-3 font-sans text-sm text-moss">
                <IconCheck className="h-4 w-4" />
                Approved
              </div>
            ) : null}
          </div>
        )}
      </main>
    </div>
  );
}
