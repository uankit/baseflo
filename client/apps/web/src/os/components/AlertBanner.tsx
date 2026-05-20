import type { AlertItem } from '../api/workbenchClient';

interface AlertBannerProps {
  alerts: AlertItem[];
  maxShow?: number;
}

const severityStyles = {
  critical: 'bg-flame/10 border-flame text-flame',
  high: 'bg-amber-50 border-amber-400 text-amber-700',
  medium: 'bg-yellow-50 border-yellow-400 text-yellow-700',
  low: 'bg-moss/10 border-moss text-moss',
};

const severityDot = {
  critical: 'bg-flame',
  high: 'bg-amber-500',
  medium: 'bg-yellow-500',
  low: 'bg-moss',
};

export function AlertBanner({ alerts, maxShow = 5 }: AlertBannerProps) {
  if (alerts.length === 0) return null;

  const shown = alerts.slice(0, maxShow);
  const remaining = alerts.length - maxShow;

  return (
    <div className="space-y-2">
      {shown.map((alert) => (
        <div
          key={alert.alert_id}
          className={`flex items-start gap-3 p-3 rounded-lg border-2 ${severityStyles[alert.severity]}`}
        >
          <div className={`mt-1.5 h-2 w-2 rounded-full ${severityDot[alert.severity]}`} />
          <div className="flex-1 min-w-0">
            <div className="font-semibold text-sm">{alert.title}</div>
            <div className="text-sm opacity-90">{alert.message}</div>
          </div>
          {alert.proposed_action && (
            <button className="px-3 py-1 text-xs font-semibold bg-white border-2 border-current rounded hover:opacity-80 transition-opacity">
              {alert.proposed_action.replace(/_/g, ' ')}
            </button>
          )}
        </div>
      ))}
      {remaining > 0 && (
        <div className="text-sm text-ink/60 font-medium pl-2">
          +{remaining} more alerts
        </div>
      )}
    </div>
  );
}
