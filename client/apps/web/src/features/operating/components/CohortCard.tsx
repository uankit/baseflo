import { Link } from '@tanstack/react-router';
import { IconWarning, IconUsers } from '@baseflo/ui/icons';
import type { SurfaceCohort } from '../model/schemas.js';

export function CohortCard({ cohort }: { cohort: SurfaceCohort }) {
  const hasAlert = cohort.actionability > 0.65;
  return (
    <div
      className={`flex flex-col border p-4 ${
        hasAlert
          ? 'border-flame/40 bg-flame/[0.03] shadow-[2px_2px_0_rgba(220,84,37,0.12)]'
          : 'border-ink/15 bg-white/40'
      }`}
    >
      <div className="flex items-center gap-2">
        {hasAlert ? (
          <IconWarning className="h-3.5 w-3.5 shrink-0 text-flame" />
        ) : (
          <IconUsers className="h-3.5 w-3.5 shrink-0 text-ink/40" />
        )}
        <p className="text-xs font-semibold text-ink">{cohort.label}</p>
      </div>
      <p className="mt-1 text-xs leading-5 text-ink/55">{cohort.description}</p>
      <div className="mt-2 flex items-baseline gap-2">
        {cohort.size_hint ? (
          <span className="font-serif text-2xl font-bold italic text-ink">{cohort.size_hint}</span>
        ) : null}
        {cohort.value_hint ? (
          <span className="text-xs text-ink/45">{cohort.value_hint}</span>
        ) : null}
      </div>
      <div className="mt-2 flex items-center justify-between">
        <p className="text-[10px] uppercase tracking-[0.14em] text-ink/40">
          {cohort.entity ? `${cohort.entity}` : 'segment'}
        </p>
        <Link
          to="/workspace/ask"
          search={{
            q: `Show me ${cohort.label} details`,
          }}
          className="text-[11px] font-semibold text-flame hover:underline"
        >
          explore
        </Link>
      </div>
    </div>
  );
}
