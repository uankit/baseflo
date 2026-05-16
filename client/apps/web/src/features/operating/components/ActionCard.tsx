import type { ActionRecord } from '@baseflo/api-client';
import { labelize } from '../../common/model/format.js';
import { PrimaryButton, SecondaryButton } from '../../common/components/StatePanels.js';

export function ActionCard({
  action,
  onPrepare,
  onComplete,
  onDismiss,
  isBusy,
}: {
  action: ActionRecord;
  onPrepare: () => void;
  onComplete: () => void;
  onDismiss: () => void;
  isBusy?: boolean;
}) {
  return (
    <article className="border border-ink/25 bg-paper-soft p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-ink/45">
            {labelize(action.action_type)} · {labelize(action.status)}
          </p>
          <h3 className="mt-1 text-base font-bold text-ink">{action.title}</h3>
        </div>
      </div>
      <p className="mt-2 text-sm leading-6 text-ink/65">{action.summary || action.why}</p>
      <div className="mt-3 border-l-2 border-flame/70 pl-3 text-xs leading-5 text-ink/60">
        {action.why}
      </div>
      {action.status === 'prepared' && Object.keys(action.prepared_payload).length ? (
        <PreparedPayload payload={action.prepared_payload} />
      ) : null}
      <div className="mt-4 flex flex-wrap gap-2">
        {action.status === 'proposed' ? (
          <PrimaryButton onClick={onPrepare} disabled={isBusy}>
            prepare
          </PrimaryButton>
        ) : null}
        {action.status === 'prepared' ? (
          <PrimaryButton onClick={onComplete} disabled={isBusy}>
            complete
          </PrimaryButton>
        ) : null}
        {action.status !== 'dismissed' && action.status !== 'completed' ? (
          <SecondaryButton onClick={onDismiss} disabled={isBusy}>
            dismiss
          </SecondaryButton>
        ) : null}
      </div>
    </article>
  );
}

function PreparedPayload({ payload }: { payload: Record<string, unknown> }) {
  const kind = typeof payload.kind === 'string' ? payload.kind : 'prepared';
  return (
    <div className="mt-4 border border-ink/15 bg-paper p-3">
      <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-ink/45">
        {labelize(kind)}
      </p>
      {'subject' in payload ? (
        <p className="mt-2 text-sm font-semibold text-ink">{String(payload.subject)}</p>
      ) : null}
      {'body' in payload ? (
        <pre className="mt-2 max-h-44 overflow-auto whitespace-pre-wrap text-xs leading-5 text-ink/65">
          {String(payload.body)}
        </pre>
      ) : null}
      {'row_count' in payload ? (
        <p className="mt-2 text-xs text-ink/55">{String(payload.row_count)} rows prepared.</p>
      ) : null}
    </div>
  );
}
