import { createFileRoute, useNavigate } from '@tanstack/react-router';
import { useMutation, useQuery } from '@tanstack/react-query';
import { useMemo, useState } from 'react';
import type { AvailableResource } from '@baseflo/api-client';
import { useGateway } from '../providers/GatewayProvider.js';
import { AppShell } from '../layouts/AppShell.js';

export const Route = createFileRoute('/connections/$connectionId/pick')({
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
      await gateway.operating.rebuild();
      navigate({ to: '/welcome', replace: true });
    },
  });

  return (
    <AppShell>
      <div className="min-h-screen bg-gray-950 p-6 text-gray-100">
        <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-xs font-medium uppercase tracking-[0.18em] text-gray-500">
              Source Picker
            </p>
            <h1 className="mt-2 text-2xl font-semibold tracking-tight text-white">
              Choose what Baseflo should learn from
            </h1>
            <p className="mt-2 max-w-2xl text-sm text-gray-400">
              Pick the resources to mirror into the operating model. Baseflo will profile,
              map, and build the first brief after selection.
            </p>
          </div>
          <button
            onClick={() => createSources.mutate(selectedResources)}
            disabled={selectedResources.length === 0 || createSources.isPending}
            className="border border-gray-700 bg-gray-900 px-3 py-2 text-xs font-medium text-gray-200 hover:bg-gray-800 disabled:opacity-50"
          >
            {createSources.isPending ? 'Building...' : `Use ${selectedResources.length} selected`}
          </button>
        </div>

        <section className="border border-gray-800 bg-gray-900/25">
          <div className="border-b border-gray-800 px-4 py-3">
            <h2 className="text-sm font-semibold text-white">Available resources</h2>
          </div>
          <div className="divide-y divide-gray-800">
            {resourcesQuery.isLoading ? (
              <div className="px-4 py-8 text-sm text-gray-500">Loading resources...</div>
            ) : resourcesQuery.isError ? (
              <div className="px-4 py-8">
                <div className="text-sm font-medium text-red-200">
                  Baseflo could not list resources for this connection.
                </div>
                <p className="mt-2 max-w-2xl text-sm leading-6 text-gray-500">
                  {resourcesQuery.error instanceof Error
                    ? resourcesQuery.error.message
                    : 'Check that the provider APIs are enabled and try again.'}
                </p>
              </div>
            ) : resources.length === 0 ? (
              <div className="px-4 py-8 text-sm text-gray-500">
                No resources were returned for this connection.
              </div>
            ) : (
              resources.map((resource) => {
                const isSelected = selected.has(resource.external_id);
                return (
                  <div
                    key={resource.external_id}
                    className="flex items-center justify-between gap-4 px-4 py-4 hover:bg-gray-900"
                  >
                    <div>
                      <div className="text-sm font-medium text-white">{resource.name}</div>
                      <div className="mt-1 text-xs text-gray-500">{resource.external_id}</div>
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
                      className="h-4 w-4 accent-white"
                    />
                  </div>
                );
              })
            )}
          </div>
        </section>
      </div>
    </AppShell>
  );
}
