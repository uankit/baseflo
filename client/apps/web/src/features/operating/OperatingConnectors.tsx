import { useMutation, useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { IconArrowRight, IconConnectors, IconDatabase, IconGitMerge, IconRefresh } from '@baseflo/ui/icons';
import { useGateway } from '../../providers/GatewayProvider.js';
import {
  asNumber,
  asRecord,
  asRecordArray,
  asString,
  businessBrief,
  businessModel,
  useOperatingBrief,
  useOperatingScan,
} from './operatingData.js';
import {
  EmptyPaper,
  LoadingPaper,
  MetricChip,
  PageKicker,
  PrimaryButton,
  SectionTitle,
  TagPill,
  titleCase,
} from './OperatingUI.js';

export function OperatingConnectors() {
  const gateway = useGateway();
  const [shopifyDomain, setShopifyDomain] = useState('');
  const briefQuery = useOperatingBrief();
  const scan = useOperatingScan();
  const brief = briefQuery.data;
  const business = businessBrief(brief);
  const model = businessModel(brief);
  const graph = asRecord(asRecord(brief?.business).graph);
  const sourceHealth = asRecordArray(business.source_health);
  const nodes = asRecordArray(graph.nodes);
  const edges = asRecordArray(graph.edges);

  const connectorsQuery = useQuery({
    queryKey: ['connectors'],
    queryFn: () => gateway.connectors.list(),
  });
  const dataSourcesQuery = useQuery({
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

  if (briefQuery.isLoading || connectorsQuery.isLoading || dataSourcesQuery.isLoading) {
    return <LoadingPaper label="Reading sources…" />;
  }

  return (
    <div className="min-h-[calc(100vh-53px)] bg-paper px-4 py-6 text-ink md:px-8">
      <div className="mx-auto max-w-[1320px]">
        <header className="border-b-2 border-ink pb-6">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <PageKicker>Sources · business graph</PageKicker>
              <h1 className="mt-3 font-serif text-[48px] font-bold italic leading-none md:text-[64px]">
                What Baseflo understands
              </h1>
              <p className="mt-4 max-w-[760px] font-sans text-[15px] leading-7 text-ink/68">
                {asString(model.paragraph, 'Connected data will appear here after the first sync.')}
              </p>
            </div>
            <PrimaryButton
              onClick={() => scan.mutate()}
              disabled={scan.isPending}
              variant="outline"
              icon={<IconRefresh className={`h-3.5 w-3.5 ${scan.isPending ? 'animate-spin' : ''}`} />}
            >
              re-read
            </PrimaryButton>
          </div>
        </header>

        <section className="grid gap-3 py-5 md:grid-cols-4">
          <MetricChip label="assets" value={`${brief?.summary.assets ?? 0}`} />
          <MetricChip label="columns" value={`${brief?.summary.columns ?? 0}`} />
          <MetricChip label="relationships" value={`${brief?.summary.relationships ?? 0}`} />
          <MetricChip label="memories" value={`${brief?.summary.memories ?? 0}`} />
        </section>

        <div className="grid gap-7 lg:grid-cols-[minmax(0,1fr)_390px]">
          <main className="space-y-7">
            <section>
              <SectionTitle>Connected assets</SectionTitle>
              <div className="grid gap-3 md:grid-cols-2">
                {(dataSourcesQuery.data ?? []).length ? (
                  (dataSourcesQuery.data ?? []).map((source) => (
                    <article key={source.id} className="border border-ink/45 bg-paper-soft p-4 shadow-[2px_2px_0_rgba(28,25,20,0.12)]">
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <div className="flex items-center gap-2">
                            <IconDatabase className="h-4 w-4 text-flame" />
                            <h2 className="font-serif text-2xl font-bold italic leading-none">{source.name}</h2>
                          </div>
                          <div className="mt-2 font-mono text-[10px] uppercase tracking-[0.14em] text-ink/42">
                            {titleCase(source.kind)} · {titleCase(source.status)}
                          </div>
                        </div>
                        <TagPill active={source.status === 'active'}>{source.last_synced_at ? 'synced' : 'new'}</TagPill>
                      </div>
                      {source.last_error ? (
                        <p className="mt-3 border-l-2 border-flame pl-3 font-sans text-xs leading-5 text-flame">
                          {source.last_error}
                        </p>
                      ) : null}
                    </article>
                  ))
                ) : (
                  <EmptyPaper title="No sources connected" body="Connect Shopify to start the first operating read." />
                )}
              </div>
            </section>

            <section>
              <SectionTitle>Business entities</SectionTitle>
              {nodes.length ? (
                <div className="grid gap-3 md:grid-cols-3">
                  {nodes.map((node, index) => (
                    <article key={`${asString(node.entity)}-${index}`} className="border border-ink/35 bg-white/55 p-4">
                      <div className="font-serif text-2xl font-bold italic">{titleCase(asString(node.entity, 'entity'))}</div>
                      <p className="mt-2 font-sans text-[12px] leading-5 text-ink/62">
                        {asString(node.why, asString(node.label))}
                      </p>
                      <div className="mt-3 font-mono text-[10px] text-ink/35">{asString(node.asset_qualified_name)}</div>
                    </article>
                  ))}
                </div>
              ) : (
                <EmptyPaper title="Entity graph pending" body="The next scan will turn source tables into business nouns." />
              )}
            </section>

            <section>
              <SectionTitle>Trusted joins</SectionTitle>
              {edges.length ? (
                <div className="space-y-2">
                  {edges.slice(0, 10).map((edge, index) => (
                    <article key={index} className="grid gap-3 border border-ink/30 bg-paper-soft p-4 md:grid-cols-[190px_minmax(0,1fr)_110px]">
                      <div className="flex items-center gap-2 font-serif text-xl font-bold italic">
                        {titleCase(asString(edge.left_entity))}
                        <IconGitMerge className="h-4 w-4 text-flame" />
                        {titleCase(asString(edge.right_entity))}
                      </div>
                      <div className="font-sans text-[13px] leading-5 text-ink/68">{asString(edge.meaning, asString(edge.label))}</div>
                      <div className="font-mono text-[10px] uppercase tracking-[0.12em] text-ink/42">
                        {Math.round(asNumber(edge.confidence) * 100) || '—'}% conf
                      </div>
                    </article>
                  ))}
                </div>
              ) : (
                <EmptyPaper title="No trusted joins yet" body="More relationships appear as connected assets overlap." />
              )}
            </section>
          </main>

          <aside className="space-y-6">
            <section className="border border-ink/35 bg-paper-soft p-4">
              <SectionTitle>Connect another source</SectionTitle>
              <div className="space-y-3">
                {(connectorsQuery.data ?? []).map((connector) => {
                  const isShopify = connector.kind === 'shopify';
                  const shopDomain = shopifyDomain.trim();
                  const canConnect =
                    connector.auth_method === 'oauth2' && (!isShopify || shopDomain.length > 0);
                  return (
                    <article key={connector.kind} className="border border-ink/30 bg-paper p-4">
                      <div className="flex items-center gap-2">
                        <IconConnectors className="h-4 w-4 text-flame" />
                        <div className="font-sans text-sm font-bold">{connector.display_name}</div>
                      </div>
                      <p className="mt-2 font-sans text-[12px] leading-5 text-ink/58">{connector.description}</p>
                      {isShopify ? (
                        <input
                          value={shopifyDomain}
                          onChange={(event) => setShopifyDomain(event.target.value)}
                          placeholder="your-store.myshopify.com"
                          className="mt-3 h-9 w-full border border-ink/45 bg-white px-3 font-sans text-sm outline-none focus:border-flame"
                        />
                      ) : null}
                      <PrimaryButton
                        disabled={startConnect.isPending || !canConnect}
                        onClick={() =>
                          startConnect.mutate({
                            kind: connector.kind,
                            shop_domain: isShopify ? shopDomain : undefined,
                          })
                        }
                        icon={<IconArrowRight className="h-3.5 w-3.5" />}
                      >
                        {connector.auth_method === 'oauth2' ? 'connect' : 'soon'}
                      </PrimaryButton>
                    </article>
                  );
                })}
              </div>
            </section>

            <section className="border border-ink/35 bg-white/45 p-4">
              <SectionTitle>Source health</SectionTitle>
              <div className="space-y-2">
                {sourceHealth.length ? (
                  sourceHealth.slice(0, 8).map((source, index) => (
                    <div key={index} className="border-l-2 border-moss pl-3">
                      <div className="font-sans text-sm font-bold">{asString(source.label, asString(source.source))}</div>
                      <div className="mt-1 font-mono text-[10px] text-ink/42">
                        {asNumber(source.rows).toLocaleString()} rows
                      </div>
                    </div>
                  ))
                ) : (
                  <div className="font-sans text-sm text-ink/50">No health notes yet.</div>
                )}
              </div>
            </section>
          </aside>
        </div>
      </div>
    </div>
  );
}
