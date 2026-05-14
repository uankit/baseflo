import { useMutation, useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { useGateway } from '../../providers/GatewayProvider.js';

export function ConnectorSetup() {
  const gateway = useGateway();
  const [shopifyDomain, setShopifyDomain] = useState('');

  const connectorsQuery = useQuery({
    queryKey: ['connectors'],
    queryFn: () => gateway.connectors.list(),
  });

  const sourcesQuery = useQuery({
    queryKey: ['data-sources'],
    queryFn: () => gateway.data.listSources(),
  });

  const startConnect = useMutation({
    mutationFn: (request: { kind: string; shop_domain?: string }) =>
      gateway.connectors.start(
        request.kind,
        request.shop_domain ? { shop_domain: request.shop_domain } : undefined,
      ),
    onSuccess: (data) => {
      window.location.href = data.authorize_url;
    },
  });

  return (
    <div className="space-y-6">
      <div>
        <p className="text-xs font-medium uppercase tracking-[0.18em] text-gray-500">
          Sources
        </p>
        <h1 className="mt-2 text-2xl font-semibold tracking-tight text-white">
          Connect Business Data
        </h1>
        <p className="mt-2 max-w-2xl text-sm text-gray-400">
          Baseflo learns from real connected data. No templates, no fake business categories.
        </p>
      </div>

      <section className="border border-gray-800 bg-gray-900/25">
        <div className="border-b border-gray-800 px-4 py-3">
          <h2 className="text-sm font-semibold text-white">Available connectors</h2>
        </div>
        <div className="divide-y divide-gray-800">
          {connectorsQuery.isLoading ? (
            <div className="px-4 py-6 text-sm text-gray-500">Loading connectors...</div>
          ) : (
            connectorsQuery.data?.map((connector) => {
              const isShopify = connector.kind === 'shopify';
              const shopDomain = shopifyDomain.trim();
              const canConnect =
                connector.auth_method === 'oauth2' && (!isShopify || shopDomain.length > 0);
              return (
                <div key={connector.kind} className="px-4 py-4">
                  <div className="flex items-start justify-between gap-4">
                    <div>
                      <div className="text-sm font-medium text-white">{connector.display_name}</div>
                      <p className="mt-1 text-sm text-gray-500">{connector.description}</p>
                      <div className="mt-2 flex flex-wrap gap-2">
                        {connector.capabilities.map((capability) => (
                          <span
                            key={capability}
                            className="border border-gray-800 bg-gray-950 px-2 py-1 text-[10px] uppercase tracking-[0.12em] text-gray-500"
                          >
                            {capability}
                          </span>
                        ))}
                      </div>
                    </div>
                    <button
                      onClick={() =>
                        startConnect.mutate({
                          kind: connector.kind,
                          shop_domain: isShopify ? shopDomain : undefined,
                        })
                      }
                      disabled={startConnect.isPending || !canConnect}
                      className="border border-gray-700 bg-gray-900 px-3 py-2 text-xs font-medium text-gray-200 hover:bg-gray-800 disabled:opacity-50"
                    >
                      {connector.auth_method === 'oauth2' ? 'Connect' : 'Coming soon'}
                    </button>
                  </div>
                  {isShopify && (
                    <div className="mt-4 max-w-sm">
                      <label className="text-xs font-medium text-gray-400" htmlFor="shopify-domain">
                        Shop domain
                      </label>
                      <input
                        id="shopify-domain"
                        value={shopifyDomain}
                        onChange={(event) => setShopifyDomain(event.target.value)}
                        placeholder="your-store.myshopify.com"
                        className="mt-2 w-full border border-gray-800 bg-gray-950 px-3 py-2 text-sm text-white outline-none placeholder:text-gray-700 focus:border-gray-600"
                      />
                    </div>
                  )}
                </div>
              );
            })
          )}
        </div>
        {startConnect.isError && (
          <div className="border-t border-gray-800 px-4 py-3 text-sm text-red-300">
            {startConnect.error instanceof Error
              ? startConnect.error.message
              : 'Unable to start connector authorization.'}
          </div>
        )}
      </section>

      <section className="border border-gray-800 bg-gray-900/25">
        <div className="border-b border-gray-800 px-4 py-3">
          <h2 className="text-sm font-semibold text-white">Connected sources</h2>
        </div>
        <div className="divide-y divide-gray-800">
          {sourcesQuery.isLoading ? (
            <div className="px-4 py-6 text-sm text-gray-500">Loading sources...</div>
          ) : sourcesQuery.data && sourcesQuery.data.length > 0 ? (
            sourcesQuery.data.map((source) => (
              <div key={source.id} className="flex items-center justify-between gap-4 px-4 py-4">
                <div>
                  <div className="text-sm font-medium text-white">{source.name}</div>
                  <div className="mt-1 text-xs text-gray-500">
                    {source.kind} / {source.status}
                  </div>
                  {source.last_error && (
                    <p className="mt-2 text-xs text-red-300">{source.last_error}</p>
                  )}
                </div>
                <div className="text-right text-xs text-gray-500">
                  {source.last_synced_at ? `Synced ${source.last_synced_at}` : 'Not synced'}
                </div>
              </div>
            ))
          ) : (
            <div className="px-4 py-8 text-sm text-gray-500">
              No sources connected yet.
            </div>
          )}
        </div>
      </section>
    </div>
  );
}
