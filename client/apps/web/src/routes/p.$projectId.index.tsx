import { createFileRoute } from '@tanstack/react-router';
import { InsightFeed } from '../features/insights/InsightFeed.js';
import { ChatPanel } from '../features/chat/ChatPanel.js';

export const Route = createFileRoute('/p/$projectId/')({
  component: ProjectDashboard,
});

function ProjectDashboard() {
  const { projectId } = Route.useParams();

  return (
    <div className="flex h-full">
      <div className="flex-1 overflow-auto p-6">
        <InsightFeed projectId={projectId} />
      </div>
      <div className="w-80 shrink-0">
        <ChatPanel projectId={projectId} />
      </div>
    </div>
  );
}
