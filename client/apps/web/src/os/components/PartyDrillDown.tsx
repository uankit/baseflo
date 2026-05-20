import { useParams, useNavigate } from '@tanstack/react-router';
import { useWorkbenchParty } from '../api/workbenchClient';
import { MetricStrip } from './MetricStrip';
import { RankedTable } from './RankedTable';

export function PartyDrillDown() {
  const { partyId } = useParams({ from: '/os/party/$partyId' });
  const navigate = useNavigate();
  const decodedName = decodeURIComponent(partyId);

  const { data, isLoading, error } = useWorkbenchParty(decodedName);

  if (isLoading) {
    return (
      <div className="p-8 text-center">
        <div className="animate-pulse text-ink/60">Loading party details...</div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="p-8 text-center">
        <div className="text-flame font-medium">
          {error?.message || `Party "${decodedName}" not found.`}
        </div>
      </div>
    );
  }

  const tableCards = data.tables || [];

  return (
    <div className="space-y-6 p-4 md:p-6 max-w-7xl mx-auto">
      {/* Back + Header */}
      <div className="flex items-center gap-4">
        <button
          onClick={() => navigate({ to: '/os/overview' })}
          className="px-3 py-1.5 text-sm font-semibold border-2 border-ink rounded-lg hover:bg-paper transition-colors"
        >
          ← Back
        </button>
        <div>
          <h1 className="text-2xl font-bold text-ink">{decodedName}</h1>
          <p className="text-sm text-ink/60">
            {data.metrics?.[0]?.value ? `Total business: ${data.metrics[0].formatted_value}` : ''}
            {data.metrics?.[3]?.value ? ` • ${data.metrics[3].value} orders` : ''}
          </p>
        </div>
      </div>

      {/* Metrics */}
      {data.metrics && data.metrics.length > 0 && <MetricStrip metrics={data.metrics} />}

      {/* Actions */}
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

      {/* Tables */}
      {tableCards.length > 0 && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {tableCards.map((table, idx) => (
            <RankedTable key={idx} table={table} />
          ))}
        </div>
      )}
    </div>
  );
}
