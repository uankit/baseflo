import { createFileRoute, useParams } from '@tanstack/react-router';
import { useQuery } from '@tanstack/react-query';
import { useGateway } from '../providers/GatewayProvider.js';
import { AppShell } from '../layouts/AppShell.js';
import { OrgDashboardView } from '../features/org-dashboard/OrgDashboardView.js';

export const Route = createFileRoute('/o/$orgSlug/')({
  component: OrgIndexPage,
});

function OrgIndexPage() {
  const { orgSlug } = useParams({ from: '/o/$orgSlug/' });
  const gateway = useGateway();
  const orgQuery = useQuery({
    queryKey: ['org', orgSlug],
    queryFn: () => gateway.orgs.get(orgSlug),
  });
  return (
    <AppShell orgSlug={orgSlug} orgName={orgQuery.data?.name}>
      <div className="mx-auto w-full max-w-6xl px-6 py-8">
        <OrgDashboardView />
      </div>
    </AppShell>
  );
}
