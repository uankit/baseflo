import type { ReactNode } from 'react';
import {
  IconArrowRight,
  IconCheck,
  IconChevronRight,
  IconDatabase,
  IconRefresh,
  IconSparkles,
  IconWarning,
  IconZap,
} from '@baseflo/ui/icons';
import {
  asNumber,
  asRecord,
  asRecordArray,
  asString,
  asStringArray,
  type AnyRecord,
} from './operatingData.js';

export const TEAM_LABEL: Record<string, string> = {
  sales: 'Sales',
  marketing: 'Marketing',
  ops: 'Ops',
  growth: 'Growth',
  product: 'Product',
  biz_analyst: 'Analyst',
};

export function teamLabel(id: unknown): string {
  const value = asString(id);
  if (!value) return 'Baseflo';
  return TEAM_LABEL[value] ?? titleCase(value);
}

export function titleCase(value: string): string {
  return value
    .replace(/[_-]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

export function formatValue(value: unknown): string {
  if (typeof value === 'number' && Number.isFinite(value)) {
    if (Math.abs(value) >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`;
    if (Math.abs(value) >= 100_000) return `${Math.round(value / 1_000)}K`;
    if (Math.abs(value) >= 1_000) return value.toLocaleString();
    if (!Number.isInteger(value)) return value.toFixed(2);
    return value.toLocaleString();
  }
  if (value === null || value === undefined || value === '') return '—';
  return String(value);
}

export function formatAge(value: unknown): string {
  const iso = asString(value);
  if (!iso) return '';
  const then = new Date(iso);
  if (Number.isNaN(then.getTime())) return '';
  const minutes = Math.max(0, Math.round((Date.now() - then.getTime()) / 60_000));
  if (minutes < 1) return 'now';
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours}h`;
  return `${Math.round(hours / 24)}d`;
}

export function compactRow(row: AnyRecord, limit = 4): string {
  return Object.entries(row)
    .filter(([key]) => key !== 'signal_rank')
    .slice(0, limit)
    .map(([key, value]) => `${titleCase(key)} ${formatValue(value)}`)
    .join(' · ');
}

export function insightTeam(insight: AnyRecord | undefined): string {
  const source = asRecord(insight?.source);
  const evidence = asRecord(insight?.evidence);
  return asString(insight?.team_id) || asString(source.team_id) || asString(evidence.team_id);
}

export function insightTags(insight: AnyRecord | undefined): string[] {
  return asStringArray(insight?.tags).slice(0, 6);
}

export function insightAudience(insight: AnyRecord | undefined): string {
  const audience = asRecord(insight?.audience_spec);
  const rowCount = asNumber(audience.row_count, asNumber(insight?.row_count));
  if (rowCount) return `${rowCount.toLocaleString()} rows`;
  const preview = asRecordArray(insight?.result_preview);
  return preview.length ? `${preview.length} shown` : 'audience attached';
}

export function PrimaryButton({
  children,
  onClick,
  disabled,
  icon,
  variant = 'solid',
}: {
  children: ReactNode;
  onClick?: () => void;
  disabled?: boolean;
  icon?: ReactNode;
  variant?: 'solid' | 'outline' | 'ghost';
}) {
  const className =
    variant === 'solid'
      ? 'border-ink bg-flame text-paper hover:bg-[#c84f2d]'
      : variant === 'ghost'
        ? 'border-transparent bg-transparent text-ink hover:bg-ink/5'
        : 'border-ink/70 bg-paper text-ink hover:bg-white';
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={`inline-flex h-8 items-center gap-2 border px-3 font-sans text-[12px] font-bold leading-none transition disabled:cursor-not-allowed disabled:opacity-50 ${className}`}
    >
      {icon ? <span className="grid h-3.5 w-3.5 place-items-center">{icon}</span> : null}
      <span>{children}</span>
    </button>
  );
}

export function TagPill({ children, active = false }: { children: ReactNode; active?: boolean }) {
  return (
    <span
      className={`inline-flex h-5 items-center rounded-full border px-2 font-sans text-[10px] font-semibold leading-none ${
        active ? 'border-ink bg-ink text-paper' : 'border-ink/40 bg-paper/80 text-ink/75'
      }`}
    >
      {children}
    </span>
  );
}

export function MetricChip({
  label,
  value,
  tone = 'neutral',
}: {
  label: string;
  value: string;
  tone?: 'neutral' | 'good' | 'warn';
}) {
  const dot = tone === 'good' ? 'bg-emerald-600' : tone === 'warn' ? 'bg-amber-600' : 'bg-ink/35';
  return (
    <div className="flex min-w-0 items-center gap-2 border border-ink/25 bg-paper px-3 py-2">
      <span className={`h-2 w-2 shrink-0 rounded-full ${dot}`} />
      <div className="min-w-0">
        <div className="truncate font-mono text-[10px] uppercase tracking-[0.14em] text-ink/45">{label}</div>
        <div className="truncate font-sans text-sm font-bold text-ink">{value}</div>
      </div>
    </div>
  );
}

export function EvidenceTable({ rows, compact = false }: { rows: AnyRecord[]; compact?: boolean }) {
  if (!rows.length) {
    return (
      <div className="border border-dashed border-ink/25 bg-paper/60 p-4 font-sans text-sm text-ink/45">
        No evidence preview attached yet.
      </div>
    );
  }
  const columns = Array.from(new Set(rows.flatMap((row) => Object.keys(row)))).slice(0, compact ? 4 : 7);
  return (
    <div className="overflow-auto border border-ink/45 bg-paper shadow-[2px_2px_0_rgba(28,25,20,0.18)]">
      <table className="w-full min-w-[520px] text-left font-sans text-[12px]">
        <thead>
          <tr className="border-b border-ink/25 bg-ink/[0.035]">
            {columns.map((column) => (
              <th key={column} className="px-3 py-2 font-mono text-[10px] font-semibold uppercase tracking-[0.12em] text-ink/55">
                {titleCase(column)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.slice(0, compact ? 4 : 8).map((row, index) => (
            <tr key={index} className="border-b border-ink/10 last:border-b-0">
              {columns.map((column) => (
                <td key={column} className="max-w-[220px] truncate px-3 py-2 text-ink/80">
                  {formatValue(row[column])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function TinyProof({ rows }: { rows: AnyRecord[] }) {
  const values = rows
    .slice(0, 5)
    .map((row) => {
      const numeric = Object.values(row).find((value) => typeof value === 'number' && Number.isFinite(value));
      return typeof numeric === 'number' ? numeric : 1;
    });
  const max = Math.max(...values, 1);
  if (!rows.length) {
    return (
      <div className="flex h-20 items-center justify-center border border-ink/25 bg-paper/70">
        <IconDatabase className="h-5 w-5 text-ink/25" />
      </div>
    );
  }
  return (
    <div className="flex h-24 items-end gap-2 border border-ink/25 bg-paper/70 px-4 py-3">
      {values.map((value, index) => (
        <div key={index} className="flex flex-1 flex-col items-center gap-1">
          <div
            className={`w-full max-w-8 ${index === 0 ? 'bg-flame' : 'bg-ink/18'}`}
            style={{ height: `${Math.max(18, (value / max) * 64)}px` }}
          />
        </div>
      ))}
    </div>
  );
}

export function ActionCard({
  action,
  onApprove,
  disabled,
}: {
  action: AnyRecord;
  onApprove?: (id: string) => void;
  disabled?: boolean;
}) {
  const id = asString(action.id);
  const status = asString(action.status);
  const mode = asString(action.execution_mode, 'prepare_for_user');
  return (
    <article className="border border-ink/60 bg-paper p-4 shadow-[3px_3px_0_rgba(28,25,20,0.18)]">
      <div className="mb-2 flex items-center justify-between gap-2">
        <TagPill>{titleCase(mode)}</TagPill>
        {status === 'approved' ? <IconCheck className="h-4 w-4 text-emerald-700" /> : <IconZap className="h-4 w-4 text-flame" />}
      </div>
      <h3 className="font-serif text-xl font-bold italic leading-tight text-ink">{asString(action.title, 'Prepare action')}</h3>
      <p className="mt-2 font-sans text-[13px] leading-5 text-ink/70">
        {asString(action.why, asString(action.summary, 'Ready for review.'))}
      </p>
      {asString(action.risk) ? (
        <p className="mt-3 flex gap-2 font-sans text-[11px] leading-4 text-ink/45">
          <IconWarning className="mt-0.5 h-3 w-3 shrink-0" />
          <span>{asString(action.risk)}</span>
        </p>
      ) : null}
      <PrimaryButton
        onClick={() => {
          if (id) onApprove?.(id);
        }}
        disabled={!id || disabled || status === 'approved'}
        icon={status === 'approved' ? <IconCheck className="h-3.5 w-3.5" /> : <IconArrowRight className="h-3.5 w-3.5" />}
        variant={status === 'approved' ? 'outline' : 'solid'}
      >
        {status === 'approved' ? 'approved' : 'approve'}
      </PrimaryButton>
    </article>
  );
}

export function InferenceRow({
  insight,
  actions,
  selected,
  onOpen,
  onPrimaryAction,
}: {
  insight: AnyRecord;
  actions?: AnyRecord[];
  selected?: boolean;
  onOpen?: () => void;
  onPrimaryAction?: () => void;
}) {
  const rows = asRecordArray(insight.result_preview);
  const tags = insightTags(insight);
  const confidence = asNumber(insight.confidence);
  const primary = actions?.[0];
  return (
    <article
      className={`group grid gap-4 border bg-paper p-4 shadow-[2px_2px_0_rgba(28,25,20,0.16)] transition md:grid-cols-[minmax(0,1fr)_220px] ${
        selected ? 'border-flame' : 'border-ink/55 hover:border-ink'
      }`}
    >
      <div className="min-w-0">
        <div className="mb-2 flex flex-wrap items-center gap-2">
          <span className="font-mono text-[11px] uppercase tracking-[0.12em] text-ink/38">
            {asString(insight.id, 'new').slice(0, 8)}
          </span>
          <TagPill active={teamLabel(insightTeam(insight)) !== 'Baseflo'}>{teamLabel(insightTeam(insight))}</TagPill>
          {tags.slice(0, 3).map((tag) => (
            <TagPill key={tag}>{titleCase(tag)}</TagPill>
          ))}
          {confidence ? (
            <span className="font-mono text-[10px] uppercase tracking-[0.12em] text-ink/45">
              {Math.round(confidence * 100)}% conf
            </span>
          ) : null}
        </div>
        <button type="button" onClick={onOpen} className="block text-left">
          <h2 className="font-serif text-[26px] font-bold italic leading-[1.05] text-ink md:text-[30px]">
            {asString(insight.title, 'Untitled inference')}
          </h2>
        </button>
        <p className="mt-2 max-w-3xl font-sans text-[14px] leading-6 text-ink/72">
          {asString(insight.summary, asString(insight.why))}
        </p>
        <div className="mt-3 flex flex-wrap items-center gap-2">
          {primary ? (
            <PrimaryButton onClick={onPrimaryAction} icon={<IconZap className="h-3.5 w-3.5" />}>
              {asString(primary.title, 'act now')}
            </PrimaryButton>
          ) : null}
          <PrimaryButton onClick={onOpen} variant="outline" icon={<IconChevronRight className="h-3.5 w-3.5" />}>
            open
          </PrimaryButton>
          <span className="font-mono text-[11px] text-ink/45">{insightAudience(insight)}</span>
        </div>
      </div>
      <TinyProof rows={rows} />
    </article>
  );
}

export function PageKicker({ children }: { children: ReactNode }) {
  return <div className="font-mono text-[11px] font-semibold uppercase tracking-[0.18em] text-ink/45">{children}</div>;
}

export function SectionTitle({ children, action }: { children: ReactNode; action?: ReactNode }) {
  return (
    <div className="mb-3 flex items-center justify-between gap-3">
      <PageKicker>{children}</PageKicker>
      {action}
    </div>
  );
}

export function LoadingPaper({ label = 'Reading business state…' }: { label?: string }) {
  return (
    <div className="grid min-h-[420px] place-items-center bg-paper text-ink">
      <div className="flex items-center gap-3 border border-ink/35 bg-white/70 px-4 py-3 font-sans text-sm text-ink/65">
        <IconRefresh className="h-4 w-4 animate-spin" />
        {label}
      </div>
    </div>
  );
}

export function EmptyPaper({ title, body }: { title: string; body?: string }) {
  return (
    <div className="border border-dashed border-ink/35 bg-white/45 p-8">
      <div className="flex items-center gap-2 font-serif text-2xl font-bold italic text-ink">
        <IconSparkles className="h-5 w-5 text-flame" />
        {title}
      </div>
      {body ? <p className="mt-2 max-w-xl font-sans text-sm leading-6 text-ink/58">{body}</p> : null}
    </div>
  );
}
