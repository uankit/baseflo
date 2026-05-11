import { createFileRoute, useParams } from '@tanstack/react-router';
import { useQuery } from '@tanstack/react-query';
import { useGateway } from '../providers/GatewayProvider.js';
import { AppShell } from '../layouts/AppShell.js';
import { StartLaneView } from '../features/project-create/StartLaneView.js';

export const Route = createFileRoute('/o/$orgSlug/start')({
  component: StartPage,
});

function StartPage() {
  const { orgSlug } = useParams({ from: '/o/$orgSlug/start' });
  const gateway = useGateway();
  const orgQuery = useQuery({
    queryKey: ['org', orgSlug],
    queryFn: () => gateway.orgs.get(orgSlug),
  });
  return (
    <AppShell orgSlug={orgSlug} orgName={orgQuery.data?.name}>
      <StartLaneView />
    </AppShell>
  );
}
