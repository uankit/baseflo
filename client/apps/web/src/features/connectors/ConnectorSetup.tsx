import { useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { useGateway } from '../../providers/GatewayProvider.js';

interface ConnectorSetupProps {
  projectId: string;
}

export function ConnectorSetup({ projectId }: ConnectorSetupProps) {
  const gateway = useGateway();
  const [spreadsheetId, setSpreadsheetId] = useState('');
  const [lastSyncResult, setLastSyncResult] = useState<{ status: string; rows_synced: number; error_message: string | null } | null>(null);

  const connectorsQuery = useQuery({
    queryKey: ['connectors', projectId],
    queryFn: () => gateway.connectors.list(projectId),
    enabled: !!projectId,
  });

  const createConnector = useMutation({
    mutationFn: () =>
      gateway.connectors.create({
        project_id: projectId,
        kind: 'google_sheets',
        name: 'Google Sheets',
        config: { spreadsheet_id: spreadsheetId },
      }),
  });

  const syncConnector = useMutation({
    mutationFn: (sourceId: string) => gateway.connectors.sync(sourceId),
    onSuccess: (data) => {
      setLastSyncResult(data);
      connectorsQuery.refetch();
    },
  });

  const handleOAuth = async () => {
    const resp = await gateway.connectors.getAuthUrl(
      projectId,
      spreadsheetId || undefined,
      window.location.href,
    );
    window.location.href = resp.auth_url;
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold text-white">Connectors</h2>
        <p className="text-xs text-gray-500">Connect your data sources to start generating insights.</p>
      </div>

      {/* Google Sheets */}
      <div className="rounded-lg border border-gray-800 bg-gray-900/50 p-4 space-y-4">
        <div className="flex items-center gap-3">
          <div className="flex h-8 w-8 items-center justify-center rounded bg-green-950 text-green-400">
            <svg className="h-4 w-4" fill="currentColor" viewBox="0 0 24 24"><path d="M4 4h16v16H4z" /></svg>
          </div>
          <div>
            <h3 className="text-sm font-medium text-gray-200">Google Sheets</h3>
            <p className="text-xs text-gray-500">Sync data from a Google Spreadsheet</p>
          </div>
        </div>

        <div className="space-y-2">
          <input
            type="text"
            placeholder="Spreadsheet ID (from URL)"
            value={spreadsheetId}
            onChange={(e) => setSpreadsheetId(e.target.value)}
            className="w-full rounded-lg border border-gray-800 bg-gray-950 px-3 py-2 text-xs text-white placeholder-gray-600 outline-none focus:border-gray-600"
          />
          <div className="flex gap-2">
            <button
              onClick={handleOAuth}
              className="rounded-lg bg-white px-3 py-2 text-xs font-medium text-gray-950 hover:bg-gray-100"
            >
              Connect via OAuth
            </button>
            <button
              onClick={() => createConnector.mutate()}
              disabled={!spreadsheetId || createConnector.isPending}
              className="rounded-lg border border-gray-700 px-3 py-2 text-xs text-gray-300 hover:bg-gray-800 disabled:opacity-50"
            >
              {createConnector.isPending ? 'Creating…' : 'Save Connector'}
            </button>
          </div>
        </div>
      </div>

      {/* Existing connectors */}
      {connectorsQuery.data && connectorsQuery.data.length > 0 && (
        <div className="space-y-2">
          <h3 className="text-xs font-medium text-gray-400 uppercase tracking-wider">Connected sources</h3>
          {connectorsQuery.data.map((c) => (
            <div key={c.id} className="flex items-center justify-between rounded-lg border border-gray-800 bg-gray-900/30 px-3 py-2">
              <div>
                <div className="text-sm text-gray-200">{c.name}</div>
                <div className="text-[10px] text-gray-500">{c.kind} · {c.status}</div>
              </div>
              <button
                onClick={() => syncConnector.mutate(c.id)}
                disabled={syncConnector.isPending}
                className="rounded bg-gray-800 px-2 py-1 text-[10px] text-gray-300 hover:bg-gray-700 disabled:opacity-50"
              >
                {syncConnector.isPending ? 'Syncing…' : 'Sync'}
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Sync result */}
      {lastSyncResult && (
        <div className={`rounded-lg p-3 text-xs ${lastSyncResult.status === 'success' ? 'bg-green-950/30 text-green-300 border border-green-900/50' : 'bg-red-950/30 text-red-300 border border-red-900/50'}`}>
          <div className="font-medium">Sync {lastSyncResult.status}</div>
          <div className="mt-1">Rows synced: {lastSyncResult.rows_synced}</div>
          {lastSyncResult.error_message && (
            <div className="mt-1 text-[10px] opacity-80">{lastSyncResult.error_message}</div>
          )}
        </div>
      )}
    </div>
  );
}
