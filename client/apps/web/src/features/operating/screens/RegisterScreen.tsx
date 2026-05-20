import { useState, useCallback, type ReactNode } from 'react';
import { Link } from '@tanstack/react-router';
import {
  IconWarning,
  IconArrowRight,
  IconCheck,
  IconChevronDown,
  IconDatabase,
  IconMail,
  IconRefresh,
  IconX,
  IconZap,
} from '@baseflo/ui/icons';
import { cn } from '@baseflo/ui/lib/utils';
import type {
  EntityRegisterCohortSummary,
  EntityRegisterRow,
  EntityRegisterTab,
} from '../model/schemas.js';
import { useEntityRegister } from '../api/useOperatingData.js';
import { useOperatingRunStream } from '../api/useOperatingRunStream.js';
import { RunProgress } from '../components/RunProgress.js';
import {
  EmptyPanel,
  LoadingPanel,
  PrimaryButton,
  ScreenFrame,
} from '../../common/components/StatePanels.js';

// ---------------------------------------------------------------------------
// Screen
// ---------------------------------------------------------------------------

export function RegisterScreen() {
  const { parsed, isPending, isError } = useEntityRegister();
  const runner = useOperatingRunStream();

  const [activeEntityType, setActiveEntityType] = useState<string | null>(null);
  const [selectedRowIds, setSelectedRowIds] = useState<Set<string>>(new Set());
  const [focusedRow, setFocusedRow] = useState<EntityRegisterRow | null>(null);
  const [connectionsPanelOpen, setConnectionsPanelOpen] = useState(false);

  const pkg = parsed.data;
  const activeTab =
    pkg?.tabs.find((t) => t.entity_type === activeEntityType) ?? pkg?.tabs[0] ?? null;

  const handleTabChange = useCallback((entityType: string) => {
    setActiveEntityType(entityType);
    setSelectedRowIds(new Set());
    setFocusedRow(null);
    setConnectionsPanelOpen(false);
  }, []);

  const handleRowClick = useCallback((row: EntityRegisterRow) => {
    setFocusedRow(row);
    setConnectionsPanelOpen(true);
  }, []);

  const toggleRowSelection = useCallback((clusterId: string) => {
    setSelectedRowIds((prev) => {
      const next = new Set(prev);
      if (next.has(clusterId)) next.delete(clusterId);
      else next.add(clusterId);
      return next;
    });
  }, []);

  const toggleAllRows = useCallback(() => {
    if (!activeTab) return;
    setSelectedRowIds((prev) => {
      if (prev.size === activeTab.rows.length) return new Set();
      return new Set(activeTab.rows.map((r) => r.cluster_id));
    });
  }, [activeTab]);

  const clearSelection = useCallback(() => setSelectedRowIds(new Set()), []);

  const refresh = () => {
    void runner.start({ mode: 'scan' }).catch(() => undefined);
  };

  if (isPending) {
    return (
      <ScreenFrame eyebrow="register" title="Building your entity register">
        <LoadingPanel />
      </ScreenFrame>
    );
  }

  if (isError || !pkg) {
    return (
      <ScreenFrame
        eyebrow="register"
        title="Connect data to see your register"
        summary="The register needs at least one completed operating run. Connect a source and run the pipeline to see your customers, invoices, products, and other business entities here."
      >
        <RunProgress events={runner.events} isRunning={runner.isRunning} error={runner.error} />
        <EmptyPanel
          title="No entity register yet"
          summary="Once Baseflo has data and a completed run, every business noun in your data — customers, invoices, products, suppliers, campaigns — appears here as a live, filterable, actionable table."
          action={
            <PrimaryButton onClick={refresh} disabled={runner.isRunning}>
              build register
            </PrimaryButton>
          }
        />
      </ScreenFrame>
    );
  }

  const selectedRows = activeTab?.rows.filter((r) => selectedRowIds.has(r.cluster_id)) ?? [];

  const crossSourceBadge =
    pkg.cross_source_cluster_count > 0
      ? ` · ${pkg.cross_source_cluster_count} cross-source`
      : '';

  return (
    <ScreenFrame
      eyebrow={`register · ${pkg.source_count} source${pkg.source_count === 1 ? '' : 's'} · ${pkg.total_row_count.toLocaleString()} records${crossSourceBadge}`}
      title="Business register"
      action={
        <PrimaryButton onClick={refresh} disabled={runner.isRunning}>
          <IconRefresh className="mr-2 h-4 w-4" />
          refresh
        </PrimaryButton>
      }
    >
      <RunProgress events={runner.events} isRunning={runner.isRunning} error={runner.error} />

      {/* Entity type tab bar */}
      <div className="flex gap-1 overflow-x-auto border-b border-ink/15 pb-0">
        {pkg.tabs.map((tab) => {
          const active = tab.entity_type === (activeTab?.entity_type ?? pkg.tabs[0]?.entity_type);
          return (
            <button
              key={tab.entity_type}
              type="button"
              onClick={() => handleTabChange(tab.entity_type)}
              className={cn(
                'flex shrink-0 items-center gap-2 border-b-2 px-4 py-2.5 text-sm font-semibold transition',
                active
                  ? 'border-flame text-ink'
                  : 'border-transparent text-ink/50 hover:border-ink/20 hover:text-ink/75',
              )}
            >
              <span>{tab.label}</span>
              <span
                className={cn(
                  'rounded px-1.5 py-0.5 font-mono text-[11px]',
                  active ? 'bg-flame/15 text-flame' : 'bg-ink/8 text-ink/45',
                )}
              >
                {tab.total_count > 200 ? `${tab.total_count.toLocaleString()}` : tab.total_count}
              </span>
            </button>
          );
        })}
      </div>

      {activeTab ? (
        <div className="relative mt-4 grid gap-4 lg:grid-cols-[1fr_320px]">
          <div className="min-w-0 space-y-3">
            {activeTab.cohort_summaries.length > 0 && (
              <div className="space-y-2">
                {activeTab.cohort_summaries.map((cohort) => (
                  <CohortCallout
                    key={cohort.cohort_id}
                    cohort={cohort}
                    entityType={activeTab.entity_type}
                  />
                ))}
              </div>
            )}

            {activeTab.rows.length > 0 ? (
              <EntityTable
                tab={activeTab}
                selectedRowIds={selectedRowIds}
                focusedClusterId={focusedRow?.cluster_id ?? null}
                onRowClick={handleRowClick}
                onToggleRow={toggleRowSelection}
                onToggleAll={toggleAllRows}
              />
            ) : (
              <div className="border border-ink/15 bg-paper-soft p-8 text-center">
                <IconDatabase className="mx-auto h-8 w-8 text-ink/25" />
                <p className="mt-3 text-sm text-ink/50">
                  No rows matched for {activeTab.label.toLowerCase()} in the last run.
                </p>
              </div>
            )}

            {activeTab.total_count > 200 && (
              <p className="text-right font-mono text-[11px] text-ink/40">
                showing 200 of {activeTab.total_count.toLocaleString()} records
              </p>
            )}
          </div>

          <aside className="space-y-3">
            {focusedRow && connectionsPanelOpen ? (
              <ConnectionsPanel
                row={focusedRow}
                onClose={() => {
                  setFocusedRow(null);
                  setConnectionsPanelOpen(false);
                }}
              />
            ) : (
              <RegisterSidebar pkg={pkg} activeTab={activeTab} />
            )}
          </aside>
        </div>
      ) : null}

      {selectedRows.length > 0 && (
        <BulkActionBar
          selectedCount={selectedRows.length}
          entityLabel={activeTab?.label ?? ''}
          availableActionTypes={activeTab?.available_action_types ?? []}
          onClear={clearSelection}
        />
      )}
    </ScreenFrame>
  );
}

// ---------------------------------------------------------------------------
// Cohort callout banner
// ---------------------------------------------------------------------------

function CohortCallout({
  cohort,
  entityType,
}: {
  cohort: EntityRegisterCohortSummary;
  entityType: string;
}) {
  const isUrgent = cohort.actionability >= 0.8;
  return (
    <div
      className={cn(
        'flex items-start justify-between gap-4 border px-4 py-3',
        isUrgent
          ? 'border-flame/40 bg-flame/6 text-ink'
          : 'border-ink/20 bg-paper-soft text-ink',
      )}
    >
      <div className="flex min-w-0 items-start gap-3">
        <IconWarning
          className={cn('mt-0.5 h-4 w-4 shrink-0', isUrgent ? 'text-flame' : 'text-ink/40')}
        />
        <div className="min-w-0">
          <p className="text-sm font-semibold">{cohort.label}</p>
          {cohort.value_hint || cohort.size_hint ? (
            <p className="mt-0.5 text-xs text-ink/60">
              {cohort.size_hint}
              {cohort.size_hint && cohort.value_hint ? ' · ' : ''}
              {cohort.value_hint}
            </p>
          ) : null}
        </div>
      </div>
      <Link
        to="/workspace/ask"
        search={{ q: `Show ${cohort.label} for ${entityType}` }}
        className="inline-flex shrink-0 items-center gap-1 border border-ink/25 px-2.5 py-1 text-xs font-semibold text-ink/70 hover:border-flame hover:text-flame"
      >
        act
        <IconArrowRight className="h-3 w-3" />
      </Link>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Entity table
// ---------------------------------------------------------------------------

const MAX_VISIBLE_COLUMNS = 5;

function EntityTable({
  tab,
  selectedRowIds,
  focusedClusterId,
  onRowClick,
  onToggleRow,
  onToggleAll,
}: {
  tab: EntityRegisterTab;
  selectedRowIds: Set<string>;
  focusedClusterId: string | null;
  onRowClick: (row: EntityRegisterRow) => void;
  onToggleRow: (clusterId: string) => void;
  onToggleAll: () => void;
}) {
  const allSelected = selectedRowIds.size === tab.rows.length && tab.rows.length > 0;
  const someSelected = selectedRowIds.size > 0 && !allSelected;
  const visibleColumns = tab.columns.slice(0, MAX_VISIBLE_COLUMNS);

  return (
    <div className="overflow-x-auto border border-ink/20">
      <table className="w-full min-w-[640px] text-sm">
        <thead>
          <tr className="border-b border-ink/15 bg-paper-soft">
            <th className="w-10 px-3 py-2.5 text-left">
              <button
                type="button"
                onClick={onToggleAll}
                className={cn(
                  'flex h-4 w-4 items-center justify-center border',
                  allSelected
                    ? 'border-flame bg-flame text-white'
                    : someSelected
                      ? 'border-flame/60 bg-flame/20'
                      : 'border-ink/30 bg-paper hover:border-flame',
                )}
                aria-label="Select all rows"
              >
                {allSelected ? <IconCheck className="h-3 w-3" /> : null}
                {someSelected ? <span className="h-1.5 w-1.5 bg-flame" /> : null}
              </button>
            </th>
            <th className="px-3 py-2.5 text-left font-mono text-[11px] uppercase tracking-[0.14em] text-ink/50">
              {tab.label.replace(/s$/, '')}
            </th>
            {visibleColumns.map((col) => (
              <th
                key={col.key}
                className="px-3 py-2.5 text-left font-mono text-[11px] uppercase tracking-[0.14em] text-ink/50"
              >
                {col.label}
              </th>
            ))}
            <th className="w-32 px-3 py-2.5 text-left font-mono text-[11px] uppercase tracking-[0.14em] text-ink/50">
              status
            </th>
          </tr>
        </thead>
        <tbody>
          {tab.rows.map((row) => {
            const isSelected = selectedRowIds.has(row.cluster_id);
            const isFocused = row.cluster_id === focusedClusterId;
            return (
              <tr
                key={row.cluster_id}
                className={cn(
                  'group border-b border-ink/10 transition-colors',
                  isSelected && 'bg-flame/5',
                  isFocused && !isSelected && 'bg-ink/4',
                  !isSelected && !isFocused && 'hover:bg-paper-soft/60',
                )}
              >
                <td className="px-3 py-2.5">
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      onToggleRow(row.cluster_id);
                    }}
                    className={cn(
                      'flex h-4 w-4 items-center justify-center border transition',
                      isSelected
                        ? 'border-flame bg-flame text-white'
                        : 'border-ink/25 bg-paper hover:border-flame',
                    )}
                    aria-label={`Select ${row.display_name}`}
                  >
                    {isSelected ? <IconCheck className="h-3 w-3" /> : null}
                  </button>
                </td>
                <td className="px-3 py-2.5">
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      onClick={() => onRowClick(row)}
                      className="text-left font-semibold text-ink hover:text-flame hover:underline"
                    >
                      {row.display_name}
                    </button>
                    {row.source_count > 1 && (
                      <span className="rounded bg-flame/10 px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-wide text-flame">
                        {row.source_count} src
                      </span>
                    )}
                  </div>
                </td>
                {visibleColumns.map((col) => (
                  <td key={col.key} className="px-3 py-2.5 text-ink/70">
                    {formatFieldValue(row.fields[col.key])}
                  </td>
                ))}
                <td className="px-3 py-2.5">
                  <div className="flex flex-wrap gap-1">
                    {row.cohort_flags.slice(0, 2).map((flag) => (
                      <CohortFlagBadge key={flag} flag={flag} />
                    ))}
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function CohortFlagBadge({ flag }: { flag: string }) {
  const urgent = flag.startsWith('overdue') || flag === 'churn_risk' || flag === 'low_stock';
  const label = flag
    .replace(/_/g, ' ')
    .replace('overdue 30d', '>30d')
    .replace('overdue 60d', '>60d');
  return (
    <span
      className={cn(
        'inline-block rounded px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-wide',
        urgent ? 'bg-flame/12 text-flame' : 'bg-ink/8 text-ink/55',
      )}
    >
      {label}
    </span>
  );
}

function formatFieldValue(value: unknown): string {
  if (value === null || value === undefined) return '—';
  if (typeof value === 'number') return value.toLocaleString();
  return String(value);
}

// ---------------------------------------------------------------------------
// Connections panel
// ---------------------------------------------------------------------------

function ConnectionsPanel({ row, onClose }: { row: EntityRegisterRow; onClose: () => void }) {
  return (
    <div className="border border-ink/20 bg-paper-soft">
      <div className="flex items-start justify-between gap-2 border-b border-ink/15 px-4 py-3">
        <div className="min-w-0">
          <p className="font-mono text-[11px] uppercase tracking-[0.16em] text-ink/40">
            {row.entity_type}
          </p>
          <p className="mt-0.5 font-serif text-xl font-bold italic leading-tight text-ink">
            {row.display_name}
          </p>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="mt-0.5 shrink-0 text-ink/40 hover:text-ink"
          aria-label="Close connections panel"
        >
          <IconX className="h-4 w-4" />
        </button>
      </div>

      {/* Key fields */}
      {Object.keys(row.fields).length > 0 && (
        <div className="border-b border-ink/10 px-4 py-3">
          <p className="mb-2 font-mono text-[11px] uppercase tracking-[0.16em] text-ink/35">fields</p>
          <dl className="space-y-1.5">
            {Object.entries(row.fields)
              .slice(0, 10)
              .map(([key, value]) => (
                <div key={key} className="flex items-baseline justify-between gap-2">
                  <dt className="text-xs text-ink/50">{humanizeKey(key)}</dt>
                  <dd className="text-right text-xs font-semibold text-ink">
                    {formatFieldValue(value)}
                  </dd>
                </div>
              ))}
          </dl>
        </div>
      )}

      {/* Cross-source sources */}
      {row.source_names.length > 0 && (
        <div className="border-b border-ink/10 px-4 py-3">
          <p className="mb-2 font-mono text-[11px] uppercase tracking-[0.16em] text-ink/35">
            sources ({row.source_count})
          </p>
          <ul className="space-y-1">
            {row.source_names.map((source) => (
              <li key={source} className="text-xs text-ink/65">
                · {source}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Decision tags */}
      {row.decision_tags.length > 0 && (
        <div className="border-b border-ink/10 px-4 py-3">
          <p className="mb-2 font-mono text-[11px] uppercase tracking-[0.16em] text-ink/35">
            actions
          </p>
          <div className="flex flex-wrap gap-1.5">
            {row.decision_tags.map((tag) => (
              <span
                key={tag}
                className="border border-flame/30 bg-flame/8 px-2 py-0.5 font-mono text-[11px] uppercase tracking-wide text-flame"
              >
                {tag.replace(/_/g, ' ')}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Member record count */}
      {row.member_record_ids.length > 1 && (
        <div className="border-b border-ink/10 px-4 py-3">
          <p className="font-mono text-[10px] uppercase tracking-[0.14em] text-ink/30">
            unified from {row.member_record_ids.length} records
          </p>
        </div>
      )}

      {/* Explore in Ask */}
      <div className="px-4 py-3">
        <Link
          to="/workspace/ask"
          search={{ q: `Tell me more about ${row.display_name}` }}
          className="flex w-full items-center justify-between text-xs font-semibold text-ink/60 hover:text-flame"
        >
          explore in Ask
          <IconArrowRight className="h-3.5 w-3.5" />
        </Link>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Register sidebar (default)
// ---------------------------------------------------------------------------

function RegisterSidebar({
  pkg,
  activeTab,
}: {
  pkg: {
    business_kind: string;
    total_row_count: number;
    source_count: number;
    cross_source_cluster_count: number;
    resolved_entity_count: number;
  };
  activeTab: EntityRegisterTab;
}) {
  return (
    <div className="space-y-3">
      <div className="border border-ink/20 bg-paper-soft p-4">
        <p className="font-mono text-[11px] uppercase tracking-[0.16em] text-ink/40">overview</p>
        <dl className="mt-3 space-y-2.5">
          <div className="flex items-baseline justify-between gap-2">
            <dt className="text-xs text-ink/55">total records</dt>
            <dd className="font-serif text-xl font-bold italic">
              {pkg.total_row_count.toLocaleString()}
            </dd>
          </div>
          <div className="flex items-baseline justify-between gap-2">
            <dt className="text-xs text-ink/55">sources</dt>
            <dd className="font-serif text-xl font-bold italic">{pkg.source_count}</dd>
          </div>
          <div className="flex items-baseline justify-between gap-2">
            <dt className="text-xs text-ink/55">resolved entities</dt>
            <dd className="font-serif text-xl font-bold italic">{pkg.resolved_entity_count}</dd>
          </div>
          {pkg.cross_source_cluster_count > 0 && (
            <div className="flex items-baseline justify-between gap-2">
              <dt className="text-xs text-flame">cross-source</dt>
              <dd className="font-serif text-xl font-bold italic text-flame">
                {pkg.cross_source_cluster_count}
              </dd>
            </div>
          )}
        </dl>
      </div>

      {activeTab.cohort_summaries.length > 0 && (
        <div className="border border-ink/20 bg-paper-soft p-4">
          <p className="mb-2 font-mono text-[11px] uppercase tracking-[0.16em] text-ink/40">
            segments
          </p>
          <div className="space-y-2">
            {activeTab.cohort_summaries.map((c) => (
              <div key={c.cohort_id} className="border border-ink/12 bg-paper px-3 py-2">
                <p className="text-xs font-semibold text-ink">{c.label}</p>
                {c.size_hint && <p className="mt-0.5 text-[11px] text-ink/50">{c.size_hint}</p>}
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="border border-ink/20 bg-paper-soft p-4">
        <p className="mb-2 font-mono text-[11px] uppercase tracking-[0.16em] text-ink/40">explore</p>
        <Link
          to="/workspace/ask"
          search={{ q: `Show me all ${activeTab.label.toLowerCase()}` }}
          className="flex items-center justify-between text-xs font-semibold text-ink/60 hover:text-flame"
        >
          ask about {activeTab.label.toLowerCase()}
          <IconArrowRight className="h-3.5 w-3.5" />
        </Link>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Bulk action bar
// ---------------------------------------------------------------------------

function BulkActionBar({
  selectedCount,
  entityLabel,
  availableActionTypes,
  onClear,
}: {
  selectedCount: number;
  entityLabel: string;
  availableActionTypes: string[];
  onClear: () => void;
}) {
  return (
    <div className="fixed bottom-6 left-1/2 z-50 -translate-x-1/2">
      <div className="flex items-center gap-3 border border-ink/30 bg-paper px-4 py-3 shadow-[4px_4px_0_rgba(28,25,20,0.2)]">
        <span className="font-mono text-[11px] text-ink/60">
          <strong className="text-ink">{selectedCount}</strong>{' '}
          {entityLabel.toLowerCase()} selected
        </span>
        <span className="h-4 w-px bg-ink/20" />
        {availableActionTypes.includes('email_draft') && (
          <ActionButton icon={<IconMail className="h-3.5 w-3.5" />} label="send message" />
        )}
        {availableActionTypes.includes('export_list') && (
          <ActionButton icon={<IconChevronDown className="h-3.5 w-3.5" />} label="export" />
        )}
        {availableActionTypes.length === 0 && (
          <ActionButton icon={<IconZap className="h-3.5 w-3.5" />} label="run action" />
        )}
        <button
          type="button"
          onClick={onClear}
          className="ml-1 text-ink/40 hover:text-ink"
          aria-label="Clear selection"
        >
          <IconX className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}

function ActionButton({ icon, label }: { icon: ReactNode; label: string }) {
  return (
    <button
      type="button"
      className="inline-flex items-center gap-1.5 border border-flame bg-flame px-3 py-1.5 text-xs font-semibold text-white shadow-[2px_2px_0_rgba(28,25,20,0.7)] transition hover:-translate-y-px active:translate-y-0"
    >
      {icon}
      {label}
    </button>
  );
}

function humanizeKey(key: string): string {
  return key
    .replace(/([a-z])([A-Z])/g, '$1 $2')
    .replace(/[_-]/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase());
}
