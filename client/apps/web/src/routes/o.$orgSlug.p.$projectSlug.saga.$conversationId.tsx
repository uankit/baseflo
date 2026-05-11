import { createFileRoute, useParams } from '@tanstack/react-router';
import { useQuery } from '@tanstack/react-query';
import { useGateway } from '../providers/GatewayProvider.js';
import { SagaShell } from '../layouts/SagaShell.js';
import { SagaViewerView } from '../features/saga-viewer/SagaViewerView.js';

export const Route = createFileRoute(
  '/o/$orgSlug/p/$projectSlug/saga/$conversationId',
)({
  component: SagaPage,
});

function SagaPage() {
  const { orgSlug, projectSlug } = useParams({
    from: '/o/$orgSlug/p/$projectSlug/saga/$conversationId',
  });
  const gateway = useGateway();
  const orgQuery = useQuery({
    queryKey: ['org', orgSlug],
    queryFn: () => gateway.orgs.get(orgSlug),
  });
  const projectQuery = useQuery({
    queryKey: ['project', orgSlug, projectSlug],
    queryFn: () => gateway.projects.get(orgSlug, projectSlug),
  });

  return (
    <SagaShell
      orgSlug={orgSlug}
      orgName={orgQuery.data?.name ?? 'Loading…'}
      projectSlug={projectSlug}
      projectName={projectQuery.data?.name ?? 'Building workspace…'}
    >
      <SagaViewerView />
    </SagaShell>
  );
}
