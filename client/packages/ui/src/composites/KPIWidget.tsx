import type { ReactNode } from 'react';
import { IconTrendingUp, IconTrendingDown, IconMinus } from '../icons/index.js';
import { cn } from '../lib/utils.js';
import { Card, CardContent } from '../primitives/Card.js';

export interface KPIWidgetProps {
  label: string;
  value: string;
  delta?: string | null;
  trend?: 'up' | 'down' | 'flat' | null;
  unit?: string | null;
  caption?: string | null;
  className?: string;
}

export function KPIWidget({
  label,
  value,
  delta,
  trend,
  unit,
  caption,
  className,
}: KPIWidgetProps) {
  return (
    <Card className={cn('flex-1', className)}>
      <CardContent className="flex flex-col gap-2 p-4">
        <span className="text-xs font-medium uppercase tracking-wide text-fg-subtle">
          {label}
        </span>
        <div className="flex items-baseline gap-2">
          <span className="text-2xl font-semibold tabular-nums text-fg">{value}</span>
          {unit && <span className="text-sm text-fg-muted">{unit}</span>}
        </div>
        {(delta || caption) && (
          <div className="flex items-center gap-2 text-xs text-fg-muted">
            {delta && trend && (
              <span
                className={cn(
                  'inline-flex items-center gap-1 font-medium',
                  trend === 'up' && 'text-success',
                  trend === 'down' && 'text-danger',
                  trend === 'flat' && 'text-fg-muted',
                )}
              >
                {trend === 'up' && <IconTrendingUp className="h-3 w-3" />}
                {trend === 'down' && <IconTrendingDown className="h-3 w-3" />}
                {trend === 'flat' && <IconMinus className="h-3 w-3" />}
                {delta}
              </span>
            )}
            {caption && <span>{caption}</span>}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export function MetricStrip({ children }: { children: ReactNode }) {
  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4" role="list">
      {children}
    </div>
  );
}
