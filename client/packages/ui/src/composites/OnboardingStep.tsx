import { IconCheck } from '../icons/index.js';
import { cn } from '../lib/utils.js';

export interface OnboardingStepProps {
  index: number;
  total: number;
  label: string;
  status: 'pending' | 'active' | 'done';
}

export function OnboardingStep({ index, total, label, status }: OnboardingStepProps) {
  return (
    <div className="flex items-center gap-3">
      <div
        className={cn(
          'flex h-7 w-7 items-center justify-center rounded-full border text-xs font-medium tabular-nums',
          status === 'active' && 'border-accent bg-accent-soft text-accent',
          status === 'done' && 'border-success bg-success/10 text-success',
          status === 'pending' && 'border-border bg-surface text-fg-muted',
        )}
        aria-current={status === 'active' ? 'step' : undefined}
      >
        {status === 'done' ? <IconCheck className="h-4 w-4" /> : index}
      </div>
      <span
        className={cn(
          'text-sm',
          status === 'pending' && 'text-fg-muted',
          status === 'done' && 'text-fg-muted line-through',
          status === 'active' && 'font-medium text-fg',
        )}
      >
        {label}
      </span>
      {index < total && (
        <span className="hidden h-px flex-1 bg-border md:block" aria-hidden="true" />
      )}
    </div>
  );
}

export function OnboardingChecklist({
  items,
}: {
  items: Array<{ id: string; label: string; done: boolean }>;
}) {
  return (
    <ul className="flex flex-col gap-2" aria-label="Onboarding checklist">
      {items.map((item) => (
        <li key={item.id} className="flex items-center gap-2 text-sm">
          <span
            className={cn(
              'flex h-5 w-5 items-center justify-center rounded-full border',
              item.done
                ? 'border-success bg-success/10 text-success'
                : 'border-border bg-surface text-fg-subtle',
            )}
          >
            {item.done && <IconCheck className="h-3 w-3" />}
          </span>
          <span className={cn(item.done ? 'text-fg-muted line-through' : 'text-fg')}>
            {item.label}
          </span>
        </li>
      ))}
    </ul>
  );
}
