import type { ReactNode } from 'react';
import { cn } from '../lib/utils.js';
import { Skeleton } from '../primitives/Misc.js';
import { Button } from '../primitives/Button.js';

// ── EmptyState — direct verb headlines, primary action ───────────────────────
export interface EmptyStateProps {
  title: string;
  description?: string;
  icon?: ReactNode;
  action?: {
    label: string;
    onClick: () => void;
  };
  secondaryAction?: {
    label: string;
    onClick: () => void;
  };
  className?: string;
}

export function EmptyState({
  title,
  description,
  icon,
  action,
  secondaryAction,
  className,
}: EmptyStateProps) {
  return (
    <div
      className={cn(
        'flex flex-col items-center justify-center gap-3 rounded-lg border border-dashed border-border bg-surface px-8 py-16 text-center',
        className,
      )}
    >
      {icon && (
        <div className="text-fg-subtle" aria-hidden="true">
          {icon}
        </div>
      )}
      <h2 className="text-lg font-semibold text-fg">{title}</h2>
      {description && (
        <p className="max-w-md text-sm text-fg-muted">{description}</p>
      )}
      {(action || secondaryAction) && (
        <div className="mt-2 flex items-center gap-2">
          {action && <Button onClick={action.onClick}>{action.label}</Button>}
          {secondaryAction && (
            <Button variant="secondary" onClick={secondaryAction.onClick}>
              {secondaryAction.label}
            </Button>
          )}
        </div>
      )}
    </div>
  );
}

// ── ErrorCallout — inline error with optional retry ──────────────────────────
export interface ErrorCalloutProps {
  title: string;
  message?: string;
  action?: {
    label: string;
    onClick: () => void;
  };
  className?: string;
  /** ARIA role for the wrapper. Default: 'alert' for errors, 'status' for warnings. */
  severity?: 'error' | 'warning' | 'info';
}

export function ErrorCallout({
  title,
  message,
  action,
  className,
  severity = 'error',
}: ErrorCalloutProps) {
  const styles = {
    error: 'border-danger/40 bg-danger/10 text-fg',
    warning: 'border-warning/40 bg-warning/10 text-fg',
    info: 'border-info/40 bg-info/10 text-fg',
  }[severity];
  const role = severity === 'error' ? 'alert' : 'status';
  return (
    <div
      role={role}
      aria-live={severity === 'error' ? 'assertive' : 'polite'}
      className={cn(
        'flex flex-col gap-2 rounded-md border p-4 text-sm',
        styles,
        className,
      )}
    >
      <div className="font-medium">{title}</div>
      {message && <div className="text-fg-muted">{message}</div>}
      {action && (
        <Button
          size="sm"
          variant={severity === 'error' ? 'secondary' : 'ghost'}
          onClick={action.onClick}
          className="self-start"
        >
          {action.label}
        </Button>
      )}
    </div>
  );
}

// ── LoadingSkeletonRow — generic skeleton block for tables/lists ─────────────
export function LoadingSkeletonRow() {
  return (
    <div className="flex items-center gap-4 border-b border-border p-3">
      <Skeleton className="h-4 w-32" />
      <Skeleton className="h-4 w-48" />
      <Skeleton className="h-4 w-24" />
      <Skeleton className="h-4 w-20" />
    </div>
  );
}

export function LoadingSkeletonCard() {
  return (
    <div className="flex flex-col gap-3 rounded-lg border border-border bg-surface p-6">
      <Skeleton className="h-4 w-1/3" />
      <Skeleton className="h-8 w-1/2" />
      <Skeleton className="h-4 w-2/3" />
    </div>
  );
}
