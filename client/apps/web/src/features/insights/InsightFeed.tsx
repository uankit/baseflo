import { useInsights } from './useInsights.js';
import { useInsightWebSocket } from './useInsightWebSocket.js';
import { InsightCard } from './InsightCard.js';

interface InsightFeedProps {
  projectId: string;
}

export function InsightFeed({ projectId }: InsightFeedProps) {
  const { insights, total, unreadCount, stats, isLoading, markRead, dismiss } = useInsights(projectId);
  useInsightWebSocket(projectId);

  if (isLoading) {
    return (
      <div className="flex h-64 items-center justify-center text-sm text-gray-500">
        Loading insights…
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Stats header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-white">Insight Feed</h2>
          <p className="text-xs text-gray-500">
            {total} total · {unreadCount} unread
          </p>
        </div>
        {stats && (
          <div className="flex gap-2">
            {Object.entries(stats.by_severity).map(([sev, count]) => (
              <span key={sev} className="rounded bg-gray-900 px-2 py-1 text-[10px] text-gray-400">
                {sev}: {count as number}
              </span>
            ))}
          </div>
        )}
      </div>

      {/* Feed */}
      {insights.length === 0 ? (
        <div className="rounded-lg border border-dashed border-gray-800 p-8 text-center">
          <p className="text-sm text-gray-500">No insights yet.</p>
          <p className="mt-1 text-xs text-gray-600">Connect a data source and run a sync to get started.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {insights.map((insight) => (
            <InsightCard
              key={insight.id}
              insight={insight}
              onRead={(id) => markRead.mutate(id)}
              onDismiss={(id) => dismiss.mutate(id)}
            />
          ))}
        </div>
      )}
    </div>
  );
}
