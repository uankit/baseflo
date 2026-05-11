import { useQuery } from '@tanstack/react-query';
import { IconSparkles, IconCommand } from '@baseflo/ui/icons';
import { useGateway } from '../../providers/GatewayProvider.js';
import { OverviewView } from '../workspace/OverviewView.js';
import { ConnectorHubView } from '../connectors/ConnectorHubView.js';
import { AnalyticsView } from '../analytics/AnalyticsView.js';
import { ExportsView } from '../exports/ExportsView.js';
import { VersionsView } from '../versions/VersionsView.js';
import { AuditLogView } from '../audit/AuditLogView.js';
import { ShareLinksView } from '../share-links/ShareLinksView.js';
import { EntityGraphView } from './EntityGraphView.js';
import { SchemaERDView } from './SchemaERDView.js';
import { AgentActionsView } from './AgentActionsView.js';
import type { ZoneId } from './SpatialWorkspace.js';

interface SpatialZoneRouterProps {
  zone: ZoneId;
  orgSlug: string;
  projectSlug: string;
  versionId: string;
}

export function SpatialZoneRouter({ zone, orgSlug, projectSlug, versionId }: SpatialZoneRouterProps) {
  const gateway = useGateway();

  const projectQuery = useQuery({
    queryKey: ['project', orgSlug, projectSlug],
    queryFn: () => gateway.projects.get(orgSlug, projectSlug),
  });

  const projectId = projectQuery.data?.id;

  const entityGraphQuery = useQuery({
    queryKey: ['artifact', projectId, 'entity_graph'],
    queryFn: async () => {
      if (!projectId) return null;
      const artifact = (await gateway.artifacts.latest(projectId, 'entity_graph')) as {
        payload: {
          canonicalEntities?: Array<{
            canonicalId: string;
            entityKind: string;
            displayName: string;
            sources: Array<{ source: string; confidence: number }>;
          }>;
        };
      };
      return artifact.payload;
    },
    enabled: !!projectId,
  });

  const schemaIrQuery = useQuery({
    queryKey: ['artifact', projectId, 'schema_ir'],
    queryFn: async () => {
      if (!projectId) return null;
      const artifact = (await gateway.artifacts.latest(projectId, 'schema_ir')) as {
        payload: {
          tables?: Array<{
            name: string;
            label: string;
            columns: Array<{
              name: string;
              semanticType: string;
              physicalType: string;
              nullable: boolean;
            }>;
            primaryKey: string[];
          }>;
          relationships?: Array<{
            fromTable: string;
            fromColumn: string;
            toTable: string;
            toColumn: string;
            cardinality: string;
          }>;
        };
      };
      return artifact.payload;
    },
    enabled: !!projectId,
  });

  switch (zone) {
    case 'command-center':
      return (
        <OverviewView
          orgSlug={orgSlug}
          projectSlug={projectSlug}
          versionId={versionId}
        />
      );

    case 'sources':
      return (
        <div className="flex flex-col gap-6">
          <h1 className="text-2xl font-semibold text-fg">Data Sources</h1>
          <ConnectorHubView />
        </div>
      );

    case 'entities':
      return (
        <div className="flex flex-col gap-6">
          <h1 className="text-2xl font-semibold text-fg">Entities</h1>
          <p className="text-sm text-fg-muted">
            Reconciled entities across all connected sources. This view shows how
            your agents unified customers, orders, and products.
          </p>
          <EntityGraphView
            entities={entityGraphQuery.data?.canonicalEntities ?? []}
          />
        </div>
      );

    case 'schema':
      return (
        <div className="flex flex-col gap-6">
          <h1 className="text-2xl font-semibold text-fg">Unified Schema</h1>
          <p className="text-sm text-fg-muted">
            The schema your agents designed from all connected sources.
          </p>
          <SchemaERDView
            tables={schemaIrQuery.data?.tables ?? []}
            relationships={schemaIrQuery.data?.relationships ?? []}
          />
        </div>
      );

    case 'insights':
      return (
        <div className="flex flex-col gap-6">
          <h1 className="text-2xl font-semibold text-fg">Insights</h1>
          <AnalyticsView />
        </div>
      );

    case 'actions':
      return (
        <div className="flex flex-col gap-8">
          {/* Agent Actions */}
          <section>
            <div className="mb-4 flex items-center gap-2">
              <IconSparkles size={14} className="text-accent" />
              <h2 className="text-xs font-semibold uppercase tracking-wider text-fg-subtle">
                Agent Actions
              </h2>
            </div>
            {projectId && <AgentActionsView projectId={projectId} />}
          </section>

          {/* User Actions */}
          <section>
            <div className="mb-4 flex items-center gap-2">
              <IconCommand size={14} className="text-fg-subtle" />
              <h2 className="text-xs font-semibold uppercase tracking-wider text-fg-subtle">
                Your Actions
              </h2>
            </div>
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
              <ExportsView />
              <ShareLinksView />
            </div>
          </section>

          {projectId && (
            <>
              <VersionsView />
              <AuditLogView orgSlug={orgSlug} projectId={projectId} />
            </>
          )}
        </div>
      );

    case 'connect':
      return (
        <div className="flex flex-col gap-6">
          <h1 className="text-2xl font-semibold text-fg">Connect</h1>
          <ConnectorHubView />
        </div>
      );

    default:
      return null;
  }
}
