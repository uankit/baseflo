import type { HTMLAttributes } from 'react';
import { cn } from '../lib/utils.js';
import { useCountUp } from '../lib/useCountUp.js';

export interface CounterProps extends HTMLAttributes<HTMLSpanElement> {
  /** Final value. */
  value: number;
  /** Starting value (default 0). */
  from?: number;
  /** Animation duration in ms. */
  durationMs?: number;
  /** Animate or not. Default true. Disable on data tables / lists. */
  animate?: boolean;
  /** Format function. Default: `Intl.NumberFormat('en-US')`. */
  format?: (value: number) => string;
  /** Optional prefix (e.g. "$"). */
  prefix?: string;
  /** Optional suffix (e.g. "%"). */
  suffix?: string;
}

const DEFAULT_FORMAT = (v: number) =>
  Math.round(v).toLocaleString('en-US');

/**
 * Animated count-up text. Use on trust counters: unique entities, duplicates
 * resolved, KPI values on first reveal, refinement plan numbers. Use `animate={false}`
 * when the same metric appears in dense lists / tables — animations there are noise.
 */
export function Counter({
  value,
  from = 0,
  durationMs = 800,
  animate = true,
  format = DEFAULT_FORMAT,
  prefix,
  suffix,
  className,
  ...props
}: CounterProps) {
  const current = useCountUp({ to: value, from, durationMs, enabled: animate });
  return (
    <span className={cn('tabular-nums', className)} {...props}>
      {prefix}
      {format(current)}
      {suffix}
    </span>
  );
}
