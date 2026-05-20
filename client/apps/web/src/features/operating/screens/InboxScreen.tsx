import { useMemo, useState } from 'react';
import type { ArtifactRecord } from '@baseflo/api-client';
import {
  actionForArtifact,
  useActionMutations,
  useActions,
  useInboxArtifacts,
} from '../api/useOperatingData.js';
import { ActionCard } from '../components/ActionCard.js';
import { EvidenceTable } from '../components/EvidenceTable.js';
import { VegaChart } from '../components/VegaChart.js';
import { EmptyPanel, ErrorPanel, LoadingPanel, ScreenFrame, SecondaryButton } from '../../common/components/StatePanels.js';
import { TagList, WhyPanel } from '../components/WhyPanel.js';
import { compactDateTime, labelize, percent } from '../../common/model/format.js';
import type { VisualizationSpec } from 'vega-embed';

export function InboxScreen() {
  const inbox = useInboxArtifacts(100);
  const actions = useActions({ include_terminal: false, limit: 100 });
  const mutations = useActionMutations();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const items = useMemo(() => inbox.data ?? [], [inbox.data]);
  const selected = useMemo(
    () => items.find((item) => item.id === selectedId) ?? items[0] ?? null,
    [items, selectedId],
  );
  const selectedAction = selected ? actionForArtifact(actions.data ?? [], selected) : null;
  const isBusy = mutations.prepare.isPending || mutations.complete.isPending || mutations.dismiss.isPending;

  if (inbox.isPending || actions.isPending) {
    return (
      <ScreenFrame eyebrow="inbox" title="Loading the operating backlog">
        <LoadingPanel />
      </ScreenFrame>
    );
  }

  if (inbox.isError || actions.isError) {
    return (
      <ScreenFrame eyebrow="inbox" title="Could not load the inbox">
        <ErrorPanel error={inbox.error ?? actions.error} />
      </ScreenFrame>
    );
  }

  if (!items.length) {
    return (
      <ScreenFrame eyebrow="inbox" title="No action backlog yet">
        <EmptyPanel
          title="Inbox items appear after Baseflo executes analyses"
          summary="The inbox shows durable artifacts that have evidence, lineage, and proposed actions."
        />
      </ScreenFrame>
    );
  }

  return (
    <ScreenFrame
      eyebrow="inbox"
      title={`${items.length} operating reads need review`}
      summary="Each item is grounded in an analysis graph, evidence preview, lineage, and optionally a preparable action."
    >
      <div className="grid min-h-[680px] gap-5 lg:grid-cols-[420px_1fr]">
        <aside className="border border-ink/20 bg-paper-soft">
          <div className="border-b border-ink/20 px-4 py-3">
            <p className="font-sans text-[11px] font-semibold uppercase tracking-[0.22em] text-ink/45">
              backlog
            </p>
          </div>
          <div className="divide-y divide-ink/10">
            {items.map((item) => (
              <InboxListItem
                key={item.id}
                item={item}
                selected={selected?.id === item.id}
                onSelect={() => setSelectedId(item.id)}
              />
            ))}
          </div>
        </aside>

        {selected ? (
          <article className="border border-ink/25 bg-paper-soft p-5 shadow-[3px_3px_0_rgba(28,25,20,0.08)]">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-ink/40">
                  {labelize(selected.kind)} · {percent(selected.priority)}
                </p>
                <h1 className="mt-2 max-w-4xl font-serif text-4xl font-bold italic leading-tight text-ink">
                  {selected.title}
                </h1>
              </div>
              <span className="border border-ink/20 bg-paper px-2 py-1 text-xs text-ink/60">
                {labelize(selected.status)}
              </span>
            </div>
            <p className="mt-4 max-w-4xl text-base leading-7 text-ink/70">{selected.summary}</p>
            <div className="mt-4">
              <TagList tags={selected.tags} />
            </div>

            <div className="mt-6 grid gap-5 xl:grid-cols-[1fr_360px]">
              <div className="space-y-5">
                <WhyPanel>{selected.why}</WhyPanel>

                {chartFromPayload(selected) ? (
                  <div className="border border-ink/20 bg-paper-soft p-3">
                    <VegaChart spec={chartFromPayload(selected) as VisualizationSpec} />
                  </div>
                ) : null}

                <details className="border border-ink/20 bg-paper-soft">
                  <summary className="cursor-pointer p-4 text-sm font-semibold text-ink/60 hover:text-ink">
                    View evidence
                  </summary>
                  <div className="p-4 pt-0">
                    <EvidenceTable rows={previewRows(selected)} />
                  </div>
                </details>

                {selectedAction ? (
                  <ActionCard
                    action={selectedAction}
                    onPrepare={() => mutations.prepare.mutate(selectedAction.id)}
                    onComplete={() => mutations.complete.mutate(selectedAction.id)}
                    onDismiss={() => mutations.dismiss.mutate(selectedAction.id)}
                    isBusy={isBusy}
                  />
                ) : (
                  <div className="border border-dashed border-ink/25 bg-paper p-4 text-sm text-ink/55">
                    No prepared action record is attached to this artifact.
                  </div>
                )}
              </div>
              <aside className="space-y-4">
                <MetaBox label="first seen" value={compactDateTime(selected.first_seen_at)} />
                <MetaBox label="last seen" value={compactDateTime(selected.last_seen_at)} />
                <SecondaryButton onClick={() => setSelectedId(null)}>clear selection</SecondaryButton>
              </aside>
            </div>
          </article>
        ) : null}
      </div>
    </ScreenFrame>
  );
}

function InboxListItem({
  item,
  selected,
  onSelect,
}: {
  item: ArtifactRecord;
  selected: boolean;
  onSelect: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onSelect}
      className={`block w-full px-4 py-4 text-left transition ${
        selected ? 'bg-ink text-paper' : 'hover:bg-white/45'
      }`}
    >
      <div className="flex items-start justify-between gap-3">
        <p className="font-mono text-[10px] uppercase tracking-[0.16em] opacity-60">{labelize(item.kind)}</p>
        <span className="font-mono text-[10px] opacity-60">{percent(item.priority)}</span>
      </div>
      <h2 className="mt-2 text-sm font-bold leading-5">{item.title}</h2>
      <p className={`mt-2 line-clamp-2 text-xs leading-5 ${selected ? 'text-paper/70' : 'text-ink/55'}`}>
        {item.summary}
      </p>
    </button>
  );
}

function MetaBox({ label, value }: { label: string; value: string }) {
  return (
    <div className="border border-ink/20 bg-paper p-4">
      <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-ink/40">{label}</p>
      <p className="mt-1 text-sm font-semibold text-ink">{value}</p>
    </div>
  );
}

function previewRows(artifact: ArtifactRecord): Array<Record<string, unknown>> {
  const execution = artifact.payload.execution;
  if (!isRecord(execution)) return [];
  const result = execution.result;
  if (!isRecord(result)) return [];
  const rows = result.result_preview;
  return Array.isArray(rows) ? rows.filter(isRecord) : [];
}

function chartFromPayload(artifact: ArtifactRecord): Record<string, unknown> | null {
  const chart = artifact.payload.chart;
  if (isRecord(chart) && chart.vega_lite) return chart.vega_lite as Record<string, unknown>;
  const execution = artifact.payload.execution;
  if (isRecord(execution) && execution.chart) return execution.chart as Record<string, unknown>;
  return null;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}
