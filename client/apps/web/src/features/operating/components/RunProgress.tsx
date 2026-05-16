import type { RunEvent } from '@baseflo/api-client';
import { percent } from '../../common/model/format.js';

export function RunProgress({
  events,
  isRunning,
  error,
}: {
  events: RunEvent[];
  isRunning: boolean;
  error?: Error | null;
}) {
  if (!isRunning && events.length === 0 && !error) return null;
  const latest = events.at(-1);
  const progress = latest?.progress ?? (isRunning ? 0.08 : 1);
  return (
    <section className="mb-6 border border-ink/25 bg-paper-soft p-4">
      <div className="flex items-center justify-between gap-4">
        <div>
          <p className="font-sans text-[11px] font-semibold uppercase tracking-[0.2em] text-ink/45">
            operating run
          </p>
          <p className="mt-1 text-sm font-semibold text-ink">
            {error ? error.message : latest?.message ?? 'Starting Baseflo operating run'}
          </p>
        </div>
        <span className="font-mono text-xs text-ink/55">{percent(progress)}</span>
      </div>
      <div className="mt-3 h-2 border border-ink/20 bg-paper">
        <div className="h-full bg-flame transition-all" style={{ width: `${Math.round(progress * 100)}%` }} />
      </div>
      {events.length ? (
        <div className="mt-3 grid gap-2 md:grid-cols-3">
          {events.slice(-6).map((event) => (
            <div key={event.event_id} className="border border-ink/10 bg-white/35 px-3 py-2">
              <p className="font-mono text-[10px] uppercase tracking-[0.14em] text-ink/45">{event.stage}</p>
              <p className="mt-1 truncate text-xs text-ink/70">{event.message}</p>
            </div>
          ))}
        </div>
      ) : null}
    </section>
  );
}
