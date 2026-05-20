import { Counter } from '@baseflo/ui/composites';
import { IconTrendingUp, IconTrendingDown, IconMinus } from '@baseflo/ui/icons';
import { cn } from '@baseflo/ui/lib/utils';
import type { BusinessViewMetric } from '../model/schemas.js';

export function MetricCard({
  metric,
  sparklineData,
  trend,
}: {
  metric: BusinessViewMetric;
  sparklineData?: number[];
  trend?: 'up' | 'down' | 'flat';
}) {
  const numericValue = parseNumeric(metric.value);
  return (
    <div className="flex flex-col border border-ink/20 bg-paper-soft p-4 shadow-[2px_2px_0_rgba(28,25,20,0.08)]">
      <p className="font-sans text-[11px] font-semibold uppercase tracking-[0.18em] text-ink/45">
        {metric.label}
      </p>
      <div className="mt-2 flex items-baseline gap-2">
        {numericValue !== null ? (
          <Counter
            value={numericValue}
            animate
            className="font-serif text-3xl font-bold italic text-ink"
          />
        ) : (
          <strong className="font-serif text-3xl font-bold italic text-ink">{metric.value}</strong>
        )}
        {metric.unit ? <span className="text-sm text-ink/45">{metric.unit}</span> : null}
      </div>

      <div className="mt-2 flex items-center justify-between">
        <p className="text-xs leading-5 text-ink/55">{metric.why}</p>
        {trend ? (
          <TrendBadge trend={trend} />
        ) : null}
      </div>

      {sparklineData && sparklineData.length > 1 ? (
        <div className="mt-3">
          <SparklineSVG data={sparklineData} />
        </div>
      ) : null}
    </div>
  );
}

function TrendBadge({ trend }: { trend: 'up' | 'down' | 'flat' }) {
  const icon =
    trend === 'up' ? <IconTrendingUp className="h-3 w-3" />
    : trend === 'down' ? <IconTrendingDown className="h-3 w-3" />
    : <IconMinus className="h-3 w-3" />;
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 text-[11px] font-semibold',
        trend === 'up' && 'text-moss',
        trend === 'down' && 'text-flame',
        trend === 'flat' && 'text-ink/40',
      )}
    >
      {icon}
    </span>
  );
}

function SparklineSVG({ data, width = 120, height = 24 }: { data: number[]; width?: number; height?: number }) {
  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;
  const padding = 2;
  const plotW = width - padding * 2;
  const plotH = height - padding * 2;

  const points = data.map((v, i) => {
    const x = padding + (i / (data.length - 1 || 1)) * plotW;
    const y = padding + plotH - ((v - min) / range) * plotH;
    return `${x},${y}`;
  });

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="w-full" style={{ height }} aria-hidden>
      <path
        d={`M${points.join(' L')}`}
        fill="none"
        stroke="rgba(28,25,20,0.2)"
        strokeWidth={1.5}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function parseNumeric(value: string): number | null {
  const cleaned = value.replace(/[$,£€\s%]/g, '');
  const num = Number(cleaned);
  return Number.isFinite(num) ? num : null;
}
