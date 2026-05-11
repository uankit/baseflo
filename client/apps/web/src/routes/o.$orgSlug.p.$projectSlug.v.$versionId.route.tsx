import { createFileRoute, Outlet, useParams } from '@tanstack/react-router';
import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { useGateway } from '../providers/GatewayProvider.js';
import { SpatialWorkspace, type ZoneId } from '../features/spatial/SpatialWorkspace.js';
import { SpatialZoneRouter } from '../features/spatial/SpatialZoneRouter.js';

export const Route = createFileRoute('/o/$orgSlug/p/$projectSlug/v/$versionId')({
  component: WorkspaceLayout,
});

function WorkspaceLayout() {
  const { orgSlug, projectSlug, versionId } = useParams({
    from: '/o/$orgSlug/p/$projectSlug/v/$versionId',
  });
  const gateway = useGateway();
  const [activeZone, setActiveZone] = useState<ZoneId>('command-center');

  const orgQuery = useQuery({
    queryKey: ['org', orgSlug],
    queryFn: () => gateway.orgs.get(orgSlug),
  });
  const projectQuery = useQuery({
    queryKey: ['project', orgSlug, projectSlug],
    queryFn: () => gateway.projects.get(orgSlug, projectSlug),
  });

  return (
    <SpatialWorkspace
      orgSlug={orgSlug}
      orgName={orgQuery.data?.name ?? 'Loading…'}
      projectSlug={projectSlug}
      projectId={projectQuery.data?.id ?? null}
      versionId={versionId}
      activeZone={activeZone}
      onZoneChange={setActiveZone}
    >
      <SpatialZoneRouter
        zone={activeZone}
        orgSlug={orgSlug}
        projectSlug={projectSlug}
        versionId={versionId}
      />
      <Outlet />
    </SpatialWorkspace>
  );
}
