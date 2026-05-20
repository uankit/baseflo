import type { MetricValue } from '../api/workbenchClient';

interface MetricStripProps {
  metrics: MetricValue[];
}

export function MetricStrip({ metrics }: MetricStripProps) {
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
      {metrics.map((m) => (
        <div
          key={m.key}
          className="bg-white border-2 border-ink rounded-lg p-4 shadow-[4px_4px_0px_0px_rgba(0,0,0,1)]"
        >
          <div className="text-sm text-ink/60 font-medium uppercase tracking-wide">
            {m.title}
          </div>
          <div className="text-2xl font-bold text-ink mt-1">
            {m.formatted_value}
          </div>
          {m.change_percent !== undefined && (
            <div
              className={`text-xs font-semibold mt-1 ${
                m.change_direction === 'up'
                  ? 'text-moss'
                  : m.change_direction === 'down'
                    ? 'text-flame'
                    : 'text-ink/40'
              }`}
            >
              {m.change_direction === 'up' ? '↑' : m.change_direction === 'down' ? '↓' : '→'}{' '}
              {Math.abs(m.change_percent).toFixed(1)}%
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
