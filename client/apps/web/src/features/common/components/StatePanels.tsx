import type { ReactNode } from 'react';
import { IconRefresh, IconWarning } from '@baseflo/ui/icons';

export function ScreenFrame({
  eyebrow,
  title,
  summary,
  children,
  action,
}: {
  eyebrow: string;
  title: string;
  summary?: string;
  children: ReactNode;
  action?: ReactNode;
}) {
  return (
    <section className="mx-auto w-full max-w-[1480px] px-5 py-8">
      <div className="mb-8 flex flex-wrap items-start justify-between gap-5">
        <div>
          <p className="font-sans text-[11px] font-semibold uppercase tracking-[0.24em] text-ink/45">
            {eyebrow}
          </p>
          <h1 className="mt-3 max-w-5xl font-serif text-4xl font-bold italic leading-[1.05] tracking-normal text-ink md:text-6xl">
            {title}
          </h1>
          {summary ? <p className="mt-4 max-w-4xl text-base leading-7 text-ink/70">{summary}</p> : null}
        </div>
        {action ? <div className="shrink-0">{action}</div> : null}
      </div>
      {children}
    </section>
  );
}

export function LoadingPanel({ label = 'Baseflo is reading the latest artifacts.' }: { label?: string }) {
  return (
    <div className="border border-ink/20 bg-paper-soft p-8 text-sm text-ink/60 shadow-[3px_3px_0_rgba(28,25,20,0.12)]">
      {label}
    </div>
  );
}

export function EmptyPanel({
  title,
  summary,
  action,
}: {
  title: string;
  summary: string;
  action?: ReactNode;
}) {
  return (
    <div className="border border-dashed border-ink/35 bg-paper-soft p-8">
      <h2 className="font-serif text-3xl font-bold italic text-ink">{title}</h2>
      <p className="mt-3 max-w-3xl text-sm leading-6 text-ink/65">{summary}</p>
      {action ? <div className="mt-5">{action}</div> : null}
    </div>
  );
}

export function ErrorPanel({
  error,
  onRetry,
}: {
  error: unknown;
  onRetry?: () => void;
}) {
  const isContract = error instanceof Error && error.name === 'ContractMismatchError';
  return (
    <div className="border border-flame/50 bg-paper-soft p-6 shadow-[3px_3px_0_rgba(220,84,37,0.25)]">
      <div className="flex items-start gap-3">
        <IconWarning className="mt-0.5 h-5 w-5 shrink-0 text-flame" />
        <div>
          <h2 className="font-serif text-2xl font-bold italic text-ink">
            {isContract ? 'Backend contract changed' : 'Could not load this screen'}
          </h2>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-ink/65">
            {error instanceof Error ? error.message : 'Baseflo received an unknown error.'}
          </p>
          {onRetry ? (
            <button
              type="button"
              onClick={onRetry}
              className="mt-4 inline-flex items-center gap-2 border border-ink bg-ink px-3 py-2 text-xs font-semibold uppercase tracking-[0.16em] text-paper"
            >
              <IconRefresh className="h-3.5 w-3.5" />
              retry
            </button>
          ) : null}
        </div>
      </div>
    </div>
  );
}

export function PrimaryButton({
  children,
  onClick,
  disabled,
  type = 'button',
}: {
  children: ReactNode;
  onClick?: () => void;
  disabled?: boolean;
  type?: 'button' | 'submit';
}) {
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      className="inline-flex items-center justify-center border border-flame bg-flame px-4 py-2 text-sm font-semibold text-white shadow-[2px_2px_0_rgba(28,25,20,0.85)] transition hover:-translate-y-px disabled:cursor-wait disabled:opacity-55 disabled:hover:translate-y-0"
    >
      {children}
    </button>
  );
}

export function SecondaryButton({
  children,
  onClick,
  disabled,
  type = 'button',
}: {
  children: ReactNode;
  onClick?: () => void;
  disabled?: boolean;
  type?: 'button' | 'submit';
}) {
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      className="inline-flex items-center justify-center border border-ink/70 bg-paper-soft px-3 py-2 text-sm font-semibold text-ink transition hover:border-flame hover:text-flame disabled:cursor-wait disabled:opacity-55"
    >
      {children}
    </button>
  );
}
