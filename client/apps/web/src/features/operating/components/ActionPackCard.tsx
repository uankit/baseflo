import type { ElementType } from 'react';
import { IconMail, IconExport, IconUsers, IconArrowRight } from '@baseflo/ui/icons';
import type { BulkActionPack } from '../model/schemas.js';

const ACTION_ICONS: Record<string, ElementType> = {
  email_draft: IconMail,
  export_list: IconExport,
  save_cohort: IconUsers,
};

export function ActionPackCard({
  action,
  onPrepare,
}: {
  action: BulkActionPack;
  onPrepare?: () => void;
}) {
  const Icon = ACTION_ICONS[action.action_type] ?? IconArrowRight;
  return (
    <div className="flex flex-col border border-ink/20 bg-paper-soft p-4 shadow-[2px_2px_0_rgba(28,25,20,0.08)]">
      <div className="flex items-center gap-2">
        <Icon className="h-4 w-4 shrink-0 text-ink/50" />
        <p className="text-xs font-semibold text-ink">{action.title}</p>
      </div>
      <p className="mt-1 text-xs leading-5 text-ink/55">{action.why}</p>
      {action.risk && action.risk !== 'low' ? (
        <p className="mt-2 border-l-2 border-flame/60 pl-2 text-[11px] leading-4 text-flame/80">
          {action.approval_required || `Requires approval — ${action.risk} risk`}
        </p>
      ) : null}
      <div className="mt-3 flex items-center justify-between">
        <span className="text-[10px] uppercase tracking-[0.14em] text-ink/40">
          {action.target_entity || 'business'}
        </span>
        <button
          type="button"
          onClick={onPrepare}
          className="inline-flex items-center gap-1 border border-ink/30 bg-paper px-2 py-1 text-[11px] font-semibold text-ink transition hover:border-flame hover:text-flame"
        >
          prepare
          <IconArrowRight className="h-3 w-3" />
        </button>
      </div>
    </div>
  );
}
