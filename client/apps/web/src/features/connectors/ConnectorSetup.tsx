import { useMutation, useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { useGateway } from '../../providers/GatewayProvider.js';
import { labelize } from '../common/model/format.js';

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
        <p className="text-xs font-medium uppercase tracking-[0.18em] text-ink/45">
          Sources
        </p>
        <h1 className="mt-2 font-serif text-3xl font-bold italic tracking-tight text-ink">
          Connect Business Data
        </h1>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-ink/65">
          Baseflo learns from real connected data. No templates, no fake business categories.
        </p>
      </div>

      <section className="border border-ink/25 bg-paper-soft">
        <div className="border-b border-ink/20 px-4 py-3">
          <h2 className="text-sm font-semibold text-ink">Available connectors</h2>
        </div>
        <div className="divide-y divide-ink/10">
          {connectorsQuery.isLoading ? (
            <div className="px-4 py-6 text-sm text-ink/55">Loading connectors...</div>
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
                      <div className="text-sm font-semibold text-ink">{connector.display_name}</div>
                      <p className="mt-1 text-sm leading-6 text-ink/60">{connector.description}</p>
                      <div className="mt-2 flex flex-wrap gap-2">
                        {connector.capabilities.map((capability) => (
                          <span
                            key={capability}
                            className="border border-ink/20 bg-paper px-2 py-1 text-[10px] uppercase tracking-[0.12em] text-ink/50"
                          >
                            {labelize(capability)}
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
                      className="border border-ink bg-ink px-3 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-paper hover:border-flame hover:bg-flame disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      {connector.auth_method === 'oauth2' ? 'connect' : 'coming soon'}
                    </button>
                  </div>
                  {isShopify && (
                    <div className="mt-4 max-w-sm">
                      <label className="text-xs font-medium text-ink/55" htmlFor="shopify-domain">
                        Shop domain
                      </label>
                      <input
                        id="shopify-domain"
                        value={shopifyDomain}
                        onChange={(event) => setShopifyDomain(event.target.value)}
                        placeholder="your-store.myshopify.com"
                        className="mt-2 w-full border border-ink/30 bg-paper px-3 py-2 text-sm text-ink outline-none placeholder:text-ink/35 focus:border-flame"
                      />
                    </div>
                  )}
                </div>
              );
            })
          )}
        </div>
        {startConnect.isError && (
          <div className="border-t border-flame/30 px-4 py-3 text-sm text-flame">
            {startConnect.error instanceof Error
              ? startConnect.error.message
              : 'Unable to start connector authorization.'}
          </div>
        )}
      </section>

      <section className="border border-ink/25 bg-paper-soft">
        <div className="border-b border-ink/20 px-4 py-3">
          <h2 className="text-sm font-semibold text-ink">Connected sources</h2>
        </div>
        <div className="divide-y divide-ink/10">
          {sourcesQuery.isLoading ? (
            <div className="px-4 py-6 text-sm text-ink/55">Loading sources...</div>
          ) : sourcesQuery.data && sourcesQuery.data.length > 0 ? (
            sourcesQuery.data.map((source) => (
              <div key={source.id} className="flex items-center justify-between gap-4 px-4 py-4">
                <div>
                  <div className="text-sm font-semibold text-ink">{source.name}</div>
                  <div className="mt-1 text-xs text-ink/50">
                    {source.kind} / {source.status}
                  </div>
                  {source.last_error && (
                    <p className="mt-2 text-xs text-flame">{source.last_error}</p>
                  )}
                </div>
                <div className="text-right text-xs text-ink/50">
                  {source.last_synced_at ? `Synced ${source.last_synced_at}` : 'Not synced'}
                </div>
              </div>
            ))
          ) : (
            <div className="px-4 py-8 text-sm text-ink/55">
              No sources connected yet.
            </div>
          )}
        </div>
      </section>
    </div>
  );
}
