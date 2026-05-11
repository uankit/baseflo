import type { HTMLAttributes, Ref } from 'react';
import { cva, type VariantProps } from 'class-variance-authority';
import { cn } from '../lib/utils.js';

const badgeVariants = cva(
  'inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-medium',
  {
    variants: {
      variant: {
        neutral: 'border-border bg-surface-2 text-fg-muted',
        accent: 'border-accent/40 bg-accent-soft text-accent',
        success: 'border-success/40 bg-success/10 text-success',
        warning: 'border-warning/40 bg-warning/10 text-warning',
        danger: 'border-danger/40 bg-danger/10 text-danger',
        info: 'border-info/40 bg-info/10 text-info',
        private: 'border-private/40 bg-private/10 text-private',
      },
    },
    defaultVariants: { variant: 'neutral' },
  },
);

export interface BadgeProps
  extends HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {
  ref?: Ref<HTMLSpanElement>;
}

export function Badge({ ref, className, variant, ...props }: BadgeProps) {
  return <span ref={ref} className={cn(badgeVariants({ variant }), className)} {...props} />;
}

// ── StatusPill — for SaaS-style health indicators ────────────────────────────
export type StatusKind = 'nominal' | 'degraded' | 'down';

const STATUS_PILL_CONFIG: Record<
  StatusKind,
  { label: string; variant: BadgeProps['variant']; dot: string }
> = {
  nominal: { label: 'All systems normal', variant: 'success', dot: 'bg-success' },
  degraded: { label: 'Degraded', variant: 'warning', dot: 'bg-warning' },
  down: { label: 'Incident in progress', variant: 'danger', dot: 'bg-danger' },
};

export function StatusPill({ status }: { status: StatusKind }) {
  const c = STATUS_PILL_CONFIG[status];
  return (
    <Badge variant={c.variant} aria-live="polite">
      <span aria-hidden="true" className={cn('h-1.5 w-1.5 rounded-full', c.dot)} />
      {c.label}
    </Badge>
  );
}

// ── ValidationBadge — for project_versions.validation_status ─────────────────
export type ValidationStatus = 'passed' | 'warning' | 'failed' | 'pending';

const VALIDATION_BADGE_CONFIG: Record<
  ValidationStatus,
  { label: string; variant: BadgeProps['variant'] }
> = {
  passed: { label: 'Validated', variant: 'success' },
  warning: { label: 'With warnings', variant: 'warning' },
  failed: { label: 'Failed', variant: 'danger' },
  pending: { label: 'Pending', variant: 'neutral' },
};

export function ValidationBadge({ status }: { status: ValidationStatus }) {
  const c = VALIDATION_BADGE_CONFIG[status];
  return <Badge variant={c.variant}>{c.label}</Badge>;
}

// ── RoleBadge ────────────────────────────────────────────────────────────────
const ROLE_VARIANT: Record<string, BadgeProps['variant']> = {
  owner: 'accent',
  admin: 'info',
  editor: 'neutral',
  viewer: 'neutral',
};

export function RoleBadge({ role }: { role: 'owner' | 'admin' | 'editor' | 'viewer' }) {
  return (
    <Badge variant={ROLE_VARIANT[role] ?? 'neutral'} className="capitalize">
      {role}
    </Badge>
  );
}

// ── PlanBadge ────────────────────────────────────────────────────────────────
export function PlanBadge({
  plan,
}: {
  plan: 'free' | 'hobby' | 'pro' | 'business' | 'enterprise';
}) {
  return (
    <Badge
      variant={plan === 'free' || plan === 'hobby' ? 'neutral' : 'accent'}
      className="capitalize"
    >
      {plan}
    </Badge>
  );
}

// ── DeploymentModeBadge ──────────────────────────────────────────────────────
const DEPLOYMENT_MODE_CONFIG: Record<
  'hosted' | 'byo_db' | 'self_host' | 'local_dev',
  { label: string; variant: BadgeProps['variant'] }
> = {
  hosted: { label: 'Hosted Cloud', variant: 'neutral' },
  byo_db: { label: 'BYO Database', variant: 'info' },
  self_host: { label: 'Self-Host', variant: 'success' },
  local_dev: { label: 'Local Dev', variant: 'warning' },
};

export function DeploymentModeBadge({
  mode,
}: {
  mode: 'hosted' | 'byo_db' | 'self_host' | 'local_dev';
}) {
  const c = DEPLOYMENT_MODE_CONFIG[mode];
  return <Badge variant={c.variant}>{c.label}</Badge>;
}
