import { createFileRoute, useParams, useNavigate } from '@tanstack/react-router';
import { useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Spinner, ErrorCallout } from '@baseflo/ui';
import { useGateway } from '../providers/GatewayProvider.js';

export const Route = createFileRoute('/o/$orgSlug/p/$projectSlug/')({
  component: ProjectRedirect,
});

function ProjectRedirect() {
  const { orgSlug, projectSlug } = useParams({ from: '/o/$orgSlug/p/$projectSlug/' });
  const gateway = useGateway();
  const navigate = useNavigate();
  const projectQuery = useQuery({
    queryKey: ['project', orgSlug, projectSlug],
    queryFn: () => gateway.projects.get(orgSlug, projectSlug),
  });

  useEffect(() => {
    const project = projectQuery.data;
    if (project) {
      const versionId = project.currentVersionId ?? 'pending';
      navigate({
        to: '/o/$orgSlug/p/$projectSlug/v/$versionId',
        params: { orgSlug, projectSlug, versionId },
        replace: true,
      });
    }
  }, [projectQuery.data, orgSlug, projectSlug, navigate]);

  if (projectQuery.isError) {
    return (
      <div className="flex min-h-full items-center justify-center p-6">
        <ErrorCallout title="Couldn't load project" message="Try again." />
      </div>
    );
  }
  return (
    <div className="flex min-h-full items-center justify-center p-6">
      <Spinner />
    </div>
  );
}
