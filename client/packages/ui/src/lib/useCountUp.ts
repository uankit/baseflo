import { useEffect, useRef, useState } from 'react';

export interface CountUpOptions {
  /** Final value to animate to. */
  to: number;
  /** Starting value (default: 0). */
  from?: number;
  /** Total animation duration in ms (default: 800). */
  durationMs?: number;
  /** When false, the animation does not run; the hook returns `to` immediately. */
  enabled?: boolean;
  /** When true, restart the animation if `to` changes. Default true. */
  restartOnChange?: boolean;
}

/**
 * Animates a numeric value from `from` to `to` over `durationMs` using
 * requestAnimationFrame. Used on trust counters (unique customers, duplicates
 * resolved, KPIs). Honors `prefers-reduced-motion` automatically — the hook
 * returns `to` immediately if reduced motion is requested.
 */
export function useCountUp({
  to,
  from = 0,
  durationMs = 800,
  enabled = true,
  restartOnChange = true,
}: CountUpOptions): number {
  const [value, setValue] = useState(enabled ? from : to);
  const rafRef = useRef<number | null>(null);
  const startRef = useRef<number | null>(null);
  const fromRef = useRef(from);

  useEffect(() => {
    if (!enabled) {
      setValue(to);
      return;
    }
    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (reduced) {
      setValue(to);
      return;
    }

    if (restartOnChange) {
      fromRef.current = value;
      startRef.current = null;
    }

    const tick = (now: number) => {
      if (startRef.current == null) startRef.current = now;
      const elapsed = now - startRef.current;
      const t = Math.min(1, elapsed / durationMs);
      // ease-out cubic for natural counter feel
      const eased = 1 - Math.pow(1 - t, 3);
      const next = fromRef.current + (to - fromRef.current) * eased;
      setValue(next);
      if (t < 1) {
        rafRef.current = window.requestAnimationFrame(tick);
      }
    };

    rafRef.current = window.requestAnimationFrame(tick);
    return () => {
      if (rafRef.current != null) window.cancelAnimationFrame(rafRef.current);
    };
    // We deliberately re-run only on `to` and `enabled` changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [to, enabled, durationMs]);

  return value;
}
