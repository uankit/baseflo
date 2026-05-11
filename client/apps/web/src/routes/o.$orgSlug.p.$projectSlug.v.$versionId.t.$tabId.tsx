import { createFileRoute, useParams } from '@tanstack/react-router';
import { useQuery } from '@tanstack/react-query';
import { ErrorCallout, LoadingSkeletonRow } from '@baseflo/ui';
import { useGateway } from '../providers/GatewayProvider.js';
import { AdminTabView } from '../features/admin-tabs/AdminTabView.js';

export const Route = createFileRoute(
  '/o/$orgSlug/p/$projectSlug/v/$versionId/t/$tabId',
)({
  component: AdminTabPage,
});

function AdminTabPage() {
  const { versionId, tabId } = useParams({
    from: '/o/$orgSlug/p/$projectSlug/v/$versionId/t/$tabId',
  });
  const gateway = useGateway();
  const specQuery = useQuery({
    queryKey: ['admin-ui-spec', versionId],
    queryFn: () => gateway.workspace.getAdminUISpec(versionId),
  });

  if (specQuery.isPending) return <LoadingSkeletonRow />;
  if (specQuery.isError)
    return <ErrorCallout title="Couldn't load workspace" message="Try again." />;

  const tab = specQuery.data.tabs.find((t) => t.id === tabId);
  if (!tab) {
    return <ErrorCallout title="Tab not found" message="That tab no longer exists." />;
  }

  return <AdminTabView tab={tab} versionId={versionId} />;
}
