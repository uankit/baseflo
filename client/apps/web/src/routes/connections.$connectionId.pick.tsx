import { Link, createFileRoute, redirect, useNavigate } from '@tanstack/react-router';
import { useMutation, useQuery } from '@tanstack/react-query';
import { useMemo, useState } from 'react';
import type { AvailableResource } from '@baseflo/api-client';
import { useGateway } from '../providers/GatewayProvider.js';
import { startOperatingRunWithEvents } from '../features/operating/api/runStream.js';
import { ScreenFrame, SecondaryButton } from '../features/common/components/StatePanels.js';

export const Route = createFileRoute('/connections/$connectionId/pick')({
  beforeLoad: async ({ context, location }) => {
    try {
      await context.gateway.auth.me();
    } catch {
      throw redirect({
        to: '/sign-in',
        search: { redirect: location.href },
      });
    }
  },
  component: PickConnectionResourcesPage,
});

function PickConnectionResourcesPage() {
  const { connectionId } = Route.useParams();
  const gateway = useGateway();
  const navigate = useNavigate();
  const [selected, setSelected] = useState<Set<string>>(new Set());

  const resourcesQuery = useQuery({
    queryKey: ['connection-resources', connectionId],
    queryFn: () => gateway.data.listConnectionResources(connectionId),
  });

  const resources = useMemo(
    () => resourcesQuery.data?.resources ?? [],
    [resourcesQuery.data],
  );
  const selectedResources = useMemo(
    () => resources.filter((resource) => selected.has(resource.external_id)),
    [resources, selected],
  );

  const createSources = useMutation({
    mutationFn: (items: AvailableResource[]) => gateway.data.createSources(connectionId, items),
    onSuccess: async () => {
      await startOperatingRunWithEvents(gateway, { mode: 'scan' });
      navigate({ to: '/workspace/business', replace: true });
    },
  });

  return (
    <div className="min-h-screen bg-paper text-ink">
      <ScreenFrame
        eyebrow="source picker"
        title="Choose what Baseflo should learn from"
        summary="Pick the resources to mirror into the canonical data plane. Baseflo will profile, map, and build Business Live after selection."
        action={
          <Link to="/workspace/sources">
            <SecondaryButton>back to sources</SecondaryButton>
          </Link>
        }
      >
        <div className="mb-6 flex justify-end">
          <button
            onClick={() => createSources.mutate(selectedResources)}
            disabled={selectedResources.length === 0 || createSources.isPending}
            className="border border-flame bg-flame px-4 py-2 text-sm font-semibold text-white shadow-[2px_2px_0_rgba(28,25,20,0.85)] disabled:cursor-wait disabled:opacity-50"
          >
            {createSources.isPending ? 'Building Business Live...' : `Use ${selectedResources.length} selected`}
          </button>
        </div>

        <section className="border border-ink/25 bg-paper-soft">
          <div className="border-b border-ink/20 px-4 py-3">
            <h2 className="text-sm font-semibold text-ink">Available resources</h2>
          </div>
          <div className="divide-y divide-ink/10">
            {resourcesQuery.isLoading ? (
              <div className="px-4 py-8 text-sm text-ink/50">Loading resources...</div>
            ) : resourcesQuery.isError ? (
              <div className="px-4 py-8">
                <div className="text-sm font-medium text-flame">
                  Baseflo could not list resources for this connection.
                </div>
                <p className="mt-2 max-w-2xl text-sm leading-6 text-ink/55">
                  {resourcesQuery.error instanceof Error
                    ? resourcesQuery.error.message
                    : 'Check that the provider APIs are enabled and try again.'}
                </p>
              </div>
            ) : resources.length === 0 ? (
              <div className="px-4 py-8 text-sm text-ink/55">
                No resources were returned for this connection.
              </div>
            ) : (
              resources.map((resource) => {
                const isSelected = selected.has(resource.external_id);
                return (
                  <div
                    key={resource.external_id}
                    className="flex items-center justify-between gap-4 px-4 py-4 hover:bg-white/45"
                  >
                    <div>
                      <div className="text-sm font-medium text-ink">{resource.name}</div>
                      <div className="mt-1 text-xs text-ink/45">{resource.external_id}</div>
                    </div>
                    <input
                      type="checkbox"
                      aria-label={`Select ${resource.name}`}
                      checked={isSelected}
                      onChange={() => {
                        setSelected((current) => {
                          const next = new Set(current);
                          if (next.has(resource.external_id)) {
                            next.delete(resource.external_id);
                          } else {
                            next.add(resource.external_id);
                          }
                          return next;
                        });
                      }}
                      className="h-4 w-4 accent-flame"
                    />
                  </div>
                );
              })
            )}
          </div>
        </section>
      </ScreenFrame>
    </div>
  );
}
