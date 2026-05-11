import { createFileRoute, useParams } from '@tanstack/react-router';
import { useQuery } from '@tanstack/react-query';
import { useGateway } from '../providers/GatewayProvider.js';
import { AppShell } from '../layouts/AppShell.js';
import { ProjectCreateView } from '../features/project-create/ProjectCreateView.js';

export const Route = createFileRoute('/o/$orgSlug/projects/new')({
  component: NewProjectPage,
});

function NewProjectPage() {
  const { orgSlug } = useParams({ from: '/o/$orgSlug/projects/new' });
  const gateway = useGateway();
  const orgQuery = useQuery({
    queryKey: ['org', orgSlug],
    queryFn: () => gateway.orgs.get(orgSlug),
  });
  return (
    <AppShell orgSlug={orgSlug} orgName={orgQuery.data?.name}>
      <ProjectCreateView />
    </AppShell>
  );
}
