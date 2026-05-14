import { createFileRoute } from '@tanstack/react-router';
import { ConnectorSetup } from '../features/connectors/ConnectorSetup.js';
import { AppShell } from '../layouts/AppShell.js';

export const Route = createFileRoute('/connectors')({
  component: ConnectorsPage,
});

function ConnectorsPage() {
  return (
    <AppShell>
      <div className="min-h-screen bg-gray-950 p-6">
        <ConnectorSetup />
      </div>
    </AppShell>
  );
}
