import { createFileRoute } from '@tanstack/react-router';
import { ConnectorSetup } from '../features/connectors/ConnectorSetup.js';

export const Route = createFileRoute('/connectors')({
  component: ConnectorsPage,
});

function ConnectorsPage() {
  // For MVP, hardcode a project ID or get it from URL/state
  // In a real app, this would come from route params or context
  const projectId = localStorage.getItem('baseflo_active_project') ?? '';

  if (!projectId) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-gray-500">
        No active project. <a href="/welcome" className="ml-1 text-gray-300 underline">Create one</a>
      </div>
    );
  }

  return (
    <div className="p-6">
      <ConnectorSetup projectId={projectId} />
    </div>
  );
}
