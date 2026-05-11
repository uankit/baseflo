import { useEffect, useState } from 'react';
import { format } from 'date-fns';
import { IconEye, IconEyeOff, IconLock } from '../icons/index.js';
import { cn } from '../lib/utils.js';
import { Badge } from './Badge.js';
import { Tooltip, TooltipContent, TooltipTrigger } from '../primitives/Misc.js';

// ── MoneyCell — currency-aware, minor units ──────────────────────────────────
export function MoneyCell({
  minor,
  currency = 'USD',
  className,
}: {
  minor: number;
  currency?: string;
  className?: string;
}) {
  const value = minor / 100;
  const formatted = new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency,
  }).format(value);
  return (
    <span className={cn('font-mono tabular-nums tracking-tight', className)}>{formatted}</span>
  );
}

// ── DateCell ─────────────────────────────────────────────────────────────────
export function DateCell({
  iso,
  withTime = true,
  relative = false,
}: {
  iso: string;
  withTime?: boolean;
  relative?: boolean;
}) {
  const date = new Date(iso);
  const display = relative
    ? formatRelative(date)
    : withTime
      ? format(date, 'MMM d, yyyy h:mm a')
      : format(date, 'MMM d, yyyy');
  const tooltip = format(date, 'PPpp');
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <time dateTime={iso} className="text-sm tabular-nums">
          {display}
        </time>
      </TooltipTrigger>
      <TooltipContent>{tooltip}</TooltipContent>
    </Tooltip>
  );
}

function formatRelative(date: Date): string {
  const seconds = Math.floor((Date.now() - date.getTime()) / 1000);
  if (seconds < 60) return 'just now';
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}d ago`;
  return format(date, 'MMM d, yyyy');
}

// ── StatusChip — colored chip per enum value ─────────────────────────────────
const STATUS_COLOR_MAP: Record<string, 'success' | 'warning' | 'danger' | 'info' | 'neutral'> = {
  active: 'success',
  paid: 'success',
  connected: 'success',
  ready: 'success',
  passed: 'success',
  lapsing: 'warning',
  pending: 'warning',
  generating: 'warning',
  expired: 'warning',
  warning: 'warning',
  refunded: 'info',
  inactive: 'neutral',
  cancelled: 'neutral',
  paused: 'neutral',
  archived: 'neutral',
  churned: 'danger',
  failed: 'danger',
  error: 'danger',
  revoked: 'danger',
};

export function StatusChip({ value }: { value: string }) {
  const variant = STATUS_COLOR_MAP[value.toLowerCase()] ?? 'neutral';
  return (
    <Badge variant={variant} className="capitalize">
      {value.replace(/_/g, ' ')}
    </Badge>
  );
}

// ── PIIField — masked by default; reveal logged in audit ─────────────────────
const PII_REVEAL_DURATION_MS = 30_000;

export interface PIIFieldProps {
  /** The masked placeholder shown by default. */
  masked?: string;
  /** Async reveal action; the wrapper handles auto-remask. */
  onReveal: () => Promise<{ value: string; expiresAt: string }>;
  ariaLabel?: string;
  /** Whether reveal is allowed for the current actor. */
  canReveal?: boolean;
}

/**
 * PII field with state-bearing motion. The unmask uses a soft 300ms reveal
 * (`reveal-mask` keyframe in tokens.css). Once revealed we render a small
 * countdown ring around the eye-icon button so the user sees the 30-second
 * window draining — making the audit trail visible, not just enforced.
 */
export function PIIField({
  masked = '••••••@••••••',
  onReveal,
  ariaLabel = 'Personal information',
  canReveal = true,
}: PIIFieldProps) {
  const [revealed, setRevealed] = useState<string | null>(null);
  const [expiresAt, setExpiresAt] = useState<number | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [now, setNow] = useState(Date.now());

  // Tick once a second while revealed so the countdown ring animates.
  useEffect(() => {
    if (!revealed) return;
    const id = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(id);
  }, [revealed]);

  const remainingPct =
    revealed && expiresAt
      ? Math.max(0, Math.min(100, ((expiresAt - now) / PII_REVEAL_DURATION_MS) * 100))
      : 0;

  const handleReveal = async () => {
    setPending(true);
    setError(null);
    try {
      const res = await onReveal();
      setRevealed(res.value);
      const exp = Date.parse(res.expiresAt);
      setExpiresAt(Number.isFinite(exp) ? exp : Date.now() + PII_REVEAL_DURATION_MS);
      const ttl = Math.max(0, exp - Date.now()) || PII_REVEAL_DURATION_MS;
      window.setTimeout(() => {
        setRevealed(null);
        setExpiresAt(null);
      }, ttl);
    } catch (err) {
      setError('Reveal denied');
      console.error(err);
    } finally {
      setPending(false);
    }
  };

  if (!canReveal) {
    return (
      <span className="inline-flex items-center gap-1 text-fg-muted" aria-label={ariaLabel}>
        <IconLock className="h-3 w-3" /> {masked}
      </span>
    );
  }

  return (
    <span className="inline-flex items-center gap-2" aria-label={ariaLabel}>
      <span
        className={cn(
          'font-mono text-sm',
          revealed
            ? 'text-fg animate-[reveal-mask_var(--duration-slow)_var(--ease-baseflo)]'
            : 'text-fg-muted',
        )}
      >
        {revealed ?? masked}
      </span>
      <button
        type="button"
        onClick={() => (revealed ? (setRevealed(null), setExpiresAt(null)) : handleReveal())}
        disabled={pending}
        className="relative inline-flex h-6 w-6 items-center justify-center rounded text-fg-muted hover:text-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-border-focus"
        aria-label={revealed ? 'Hide value' : 'Reveal value (audit-logged)'}
        title={revealed ? 'Hide' : 'Reveal (audit-logged for 30s)'}
      >
        {revealed && (
          <svg
            aria-hidden="true"
            viewBox="0 0 24 24"
            className="absolute inset-0 -rotate-90"
          >
            <circle
              cx="12"
              cy="12"
              r="10"
              fill="none"
              stroke="hsl(var(--color-border) / 0.6)"
              strokeWidth="2"
            />
            <circle
              cx="12"
              cy="12"
              r="10"
              fill="none"
              stroke="hsl(var(--color-accent))"
              strokeWidth="2"
              strokeDasharray={`${(remainingPct / 100) * 62.83} 62.83`}
              strokeLinecap="round"
              style={{ transition: 'stroke-dasharray 1s linear' }}
            />
          </svg>
        )}
        <span className="relative">
          {revealed ? <IconEyeOff className="h-3.5 w-3.5" /> : <IconEye className="h-3.5 w-3.5" />}
        </span>
      </button>
      {error && <span className="text-xs text-danger">{error}</span>}
    </span>
  );
}

// ── AttributionBadge — multi-source provenance, always visible ───────────────
const CONNECTOR_TONE: Record<
  string,
  { label: string; bg: string; text: string; abbr: string }
> = {
  postgres: { label: 'Postgres', bg: 'bg-info/10', text: 'text-info', abbr: 'PG' },
  csv: { label: 'CSV', bg: 'bg-accent-soft', text: 'text-accent', abbr: 'CSV' },
  excel: { label: 'Excel', bg: 'bg-success/10', text: 'text-success', abbr: 'XLS' },
  google_sheets: { label: 'Google Sheets', bg: 'bg-success/10', text: 'text-success', abbr: 'GS' },
  sheets: { label: 'Google Sheets', bg: 'bg-success/10', text: 'text-success', abbr: 'GS' },
  shopify: { label: 'Shopify', bg: 'bg-success/10', text: 'text-success', abbr: 'SH' },
  stripe: { label: 'Stripe', bg: 'bg-private/10', text: 'text-private', abbr: '$' },
  mailchimp: { label: 'Mailchimp', bg: 'bg-warning/10', text: 'text-warning', abbr: 'MC' },
  notion: { label: 'Notion', bg: 'bg-fg-muted/10', text: 'text-fg-muted', abbr: 'N' },
};

/**
 * Multi-source attribution chip stack. Always visible (the moat is visible by
 * default, not on hover). Each connector renders as a pill with its own tone;
 * the tooltip lists which fields each source contributed.
 */
export function AttributionBadge({
  contributions,
}: {
  contributions: Array<{ connectorKind: string; fields: string[] }>;
}) {
  if (contributions.length === 0) return null;

  const single = contributions.length === 1;

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span className="inline-flex items-center -space-x-1" aria-label="Source attribution">
          {contributions.map((c) => {
            const tone = CONNECTOR_TONE[c.connectorKind] ?? {
              label: c.connectorKind,
              bg: 'bg-surface-2',
              text: 'text-fg-muted',
              abbr: c.connectorKind.slice(0, 2).toUpperCase(),
            };
            return (
              <span
                key={c.connectorKind}
                className={cn(
                  'inline-flex h-5 items-center justify-center rounded-full border border-surface px-1.5 text-[10px] font-mono font-medium uppercase',
                  tone.bg,
                  tone.text,
                  single ? 'min-w-[28px]' : 'min-w-[22px]',
                )}
              >
                {tone.abbr}
              </span>
            );
          })}
        </span>
      </TooltipTrigger>
      <TooltipContent className="max-w-md">
        <div className="flex flex-col gap-1">
          {contributions.map((c) => {
            const tone = CONNECTOR_TONE[c.connectorKind] ?? { label: c.connectorKind };
            return (
              <div key={c.connectorKind} className="text-xs">
                <span className="font-medium">{tone.label}: </span>
                <span className="text-fg-muted">{c.fields.join(', ')}</span>
              </div>
            );
          })}
        </div>
      </TooltipContent>
    </Tooltip>
  );
}
