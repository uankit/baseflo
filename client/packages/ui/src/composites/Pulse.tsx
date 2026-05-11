import type { HTMLAttributes } from 'react';
import { cn } from '../lib/utils.js';

export interface PulseDotProps extends HTMLAttributes<HTMLSpanElement> {
  /** Color slot from the token palette. Default: 'accent'. */
  tone?: 'accent' | 'success' | 'warning' | 'danger' | 'info';
  /** Visible dot size in pixels. Default: 8. */
  size?: number;
  /** Whether to render the pulse ring. Default: true. */
  active?: boolean;
}

const TONE_BG: Record<NonNullable<PulseDotProps['tone']>, string> = {
  accent: 'bg-accent',
  success: 'bg-success',
  warning: 'bg-warning',
  danger: 'bg-danger',
  info: 'bg-info',
};

/**
 * A live-state indicator: a solid dot wrapped in a pulsing ring. Use this
 * wherever the UI needs to communicate "this is currently happening" — active
 * agent stage, syncing connector, live SSE connection. Forbidden for static
 * decoration; the ring must correspond to a real state.
 */
export function PulseDot({
  tone = 'accent',
  size = 8,
  active = true,
  className,
  style,
  ...props
}: PulseDotProps) {
  return (
    <span
      role="status"
      aria-label={active ? 'Active' : 'Idle'}
      className={cn(
        'relative inline-flex items-center justify-center',
        active && 'animate-[pulse-ring_2s_var(--ease-baseflo)_infinite] rounded-full',
        className,
      )}
      style={{ width: size, height: size, ...style }}
      {...props}
    >
      <span className={cn('block h-full w-full rounded-full', TONE_BG[tone])} />
    </span>
  );
}

/**
 * A gentle scale+fade pulse for syncing connectors. Subtler than PulseDot —
 * intended for icons in the connectors strip.
 */
export function SyncPulse({
  className,
  ...props
}: HTMLAttributes<HTMLSpanElement>) {
  return (
    <span
      role="status"
      aria-label="Syncing"
      className={cn(
        'inline-block h-1.5 w-1.5 rounded-full bg-info',
        'animate-[sync-pulse_1.6s_var(--ease-baseflo)_infinite]',
        className,
      )}
      {...props}
    />
  );
}
