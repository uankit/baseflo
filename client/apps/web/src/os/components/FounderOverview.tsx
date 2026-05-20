import { useWorkbenchOverview } from '../api/workbenchClient';
import { MetricStrip } from './MetricStrip';
import { AlertBanner } from './AlertBanner';
import { RankedTable } from './RankedTable';

export function FounderOverview() {
  const { data, isLoading, error } = useWorkbenchOverview();

  if (isLoading) {
    return (
      <div className="p-8 text-center">
        <div className="animate-pulse text-ink/60">Loading your business...</div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="p-8 text-center">
        <div className="text-flame font-medium">
          {error?.message || 'Unable to load business overview.'}
        </div>
        <div className="text-sm text-ink/60 mt-2">
          Connect a data source to see your business live.
        </div>
      </div>
    );
  }

  const alertCards = data.alerts || [];
  const tableCards = data.tables || [];
  const chartCards = data.charts || [];

  return (
    <div className="space-y-6 p-4 md:p-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-ink">Business Overview</h1>
          <p className="text-sm text-ink/60 mt-1">
            Live snapshot • {new Date(data.generated_at).toLocaleString()}
          </p>
        </div>
        <div className="flex gap-2">
          {data.actions?.map((action) => (
            <button
              key={action.type}
              className="px-4 py-2 bg-ink text-paper text-sm font-semibold rounded-lg border-2 border-ink hover:bg-ink/90 transition-colors"
            >
              {action.label}
            </button>
          ))}
        </div>
      </div>

      {/* Metrics */}
      {data.metrics && data.metrics.length > 0 && <MetricStrip metrics={data.metrics} />}

      {/* Alerts */}
      {alertCards.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {alertCards.slice(0, 4).map((alert, idx) => (
            <AlertBanner key={idx} alerts={[alert]} maxShow={1} />
          ))}
        </div>
      )}

      {/* Tables */}
      {tableCards.length > 0 && (
        <div className="space-y-4">
          {tableCards.map((table, idx) => (
            <RankedTable key={idx} table={table} />
          ))}
        </div>
      )}

      {/* Charts placeholder */}
      {chartCards.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {chartCards.map((chart, idx) => (
            <div
              key={idx}
              className="bg-white border-2 border-ink rounded-lg p-4 shadow-[4px_4px_0px_0px_rgba(0,0,0,1)]"
            >
              <h3 className="font-bold text-ink mb-3">{chart.title}</h3>
              <div className="h-48 flex items-end gap-2">
                {chart.datasets[0]?.data.map((val, i) => (
                  <div
                    key={i}
                    className="flex-1 bg-ink/80 rounded-t hover:bg-ink transition-colors relative group"
                    style={{ height: `${Math.min((val / Math.max(...chart.datasets[0].data)) * 100, 100)}%` }}
                  >
                    <div className="absolute -top-8 left-1/2 -translate-x-1/2 bg-ink text-paper text-xs px-2 py-1 rounded opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap">
                      {chart.labels[i]}: {val}
                    </div>
                  </div>
                ))}
              </div>
              <div className="flex justify-between mt-2 text-xs text-ink/60">
                {chart.labels.slice(0, 6).map((l, i) => (
                  <span key={i}>{String(l).slice(0, 8)}</span>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
