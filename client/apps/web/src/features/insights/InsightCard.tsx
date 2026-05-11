import type { Insight } from '@baseflo/contracts';

interface InsightCardProps {
  insight: Insight;
  onRead: (id: string) => void;
  onDismiss: (id: string) => void;
}

const severityStyles: Record<string, string> = {
  info: 'border-l-blue-500 bg-blue-950/20',
  low: 'border-l-green-500 bg-green-950/20',
  medium: 'border-l-yellow-500 bg-yellow-950/20',
  high: 'border-l-orange-500 bg-orange-950/20',
  critical: 'border-l-red-500 bg-red-950/20',
};

const severityBadge: Record<string, string> = {
  info: 'bg-blue-900/50 text-blue-300',
  low: 'bg-green-900/50 text-green-300',
  medium: 'bg-yellow-900/50 text-yellow-300',
  high: 'bg-orange-900/50 text-orange-300',
  critical: 'bg-red-900/50 text-red-300',
};

export function InsightCard({ insight, onRead, onDismiss }: InsightCardProps) {
  const borderClass = severityStyles[insight.severity] ?? severityStyles.info;
  const badgeClass = severityBadge[insight.severity] ?? severityBadge.info;

  return (
    <div className={`relative rounded-lg border border-gray-800 border-l-4 ${borderClass} p-4 transition-opacity ${insight.is_read ? 'opacity-60' : 'opacity-100'}`}>
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className={`inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider ${badgeClass}`}>
              {insight.severity}
            </span>
            <span className="text-[10px] text-gray-500 uppercase tracking-wider">{insight.kind}</span>
          </div>
          <h3 className="text-sm font-medium text-gray-100">{insight.title}</h3>
          <p className="mt-1 text-xs text-gray-400 leading-relaxed">{insight.description}</p>
          {insight.sql && (
            <details className="mt-2">
              <summary className="cursor-pointer text-[10px] text-gray-500 hover:text-gray-300">SQL</summary>
              <pre className="mt-1 overflow-x-auto rounded bg-gray-950 p-2 text-[10px] text-gray-400">{insight.sql}</pre>
            </details>
          )}
        </div>

        <div className="flex flex-col gap-1">
          {!insight.is_read && (
            <button
              onClick={() => onRead(insight.id)}
              className="rounded px-2 py-1 text-[10px] text-gray-400 hover:bg-gray-800 hover:text-gray-200"
            >
              Mark read
            </button>
          )}
          <button
            onClick={() => onDismiss(insight.id)}
            className="rounded px-2 py-1 text-[10px] text-gray-500 hover:bg-gray-800 hover:text-gray-300"
          >
            Dismiss
          </button>
        </div>
      </div>
    </div>
  );
}
