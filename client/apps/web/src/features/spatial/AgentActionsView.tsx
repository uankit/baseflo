import { useQuery } from '@tanstack/react-query';
import { motion } from 'framer-motion';
import { formatDistance } from 'date-fns';
import { Card, CardContent, EmptyState } from '@baseflo/ui';
import { IconSparkles, IconDatabase, IconShieldCheck, IconZap, IconLightbulb } from '@baseflo/ui/icons';
import { useGateway } from '../../providers/GatewayProvider.js';

interface AgentActionsViewProps {
  projectId: string | null;
}

const AGENT_META: Record<string, { name: string; icon: typeof IconDatabase; color: string; bg: string }> = {
  source_map: { name: 'Source', icon: IconDatabase, color: 'text-accent', bg: 'bg-accent-soft' },
  entity_graph: { name: 'Recon', icon: IconShieldCheck, color: 'text-purple-600', bg: 'bg-purple-50' },
  schema_ir: { name: 'Schema', icon: IconZap, color: 'text-emerald-600', bg: 'bg-emerald-50' },
  insight_board: { name: 'Insight', icon: IconLightbulb, color: 'text-amber-600', bg: 'bg-amber-50' },
};

export function AgentActionsView({ projectId }: AgentActionsViewProps) {
  const gateway = useGateway();

  const artifactsQuery = useQuery({
    queryKey: ['agent-actions', projectId],
    queryFn: async () => {
      if (!projectId) return [];
      const resp = (await gateway.artifacts.list(projectId)) as {
        artifacts: Array<{
          artifactId: string;
          artifactType: string;
          producedBy: string;
          createdAt: string;
          version: number;
        }>;
      };
      return resp.artifacts;
    },
    enabled: !!projectId,
  });

  const artifacts = artifactsQuery.data ?? [];

  if (artifacts.length === 0) {
    return (
      <Card>
        <CardContent className="py-8">
          <EmptyState
            icon={<IconSparkles className="h-8 w-8 text-fg-subtle" />}
            title="No agent actions yet"
            description="Agents will log their work here once they start building your workspace."
          />
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="flex flex-col gap-3">
      {artifacts.slice(0, 10).map((artifact, i) => {
        const meta = AGENT_META[artifact.artifactType] ?? {
          name: artifact.producedBy,
          icon: IconSparkles,
          color: 'text-fg-muted',
          bg: 'bg-surface-2',
        };
        const Icon = meta.icon;
        return (
          <motion.div
            key={artifact.artifactId}
            initial={{ opacity: 0, x: -8 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: i * 0.04 }}
            className="flex items-center gap-3 rounded-lg border border-border bg-surface px-4 py-3 transition-all hover:border-border-focus"
          >
            <div className={`flex h-8 w-8 items-center justify-center rounded-full ${meta.bg}`}>
              <Icon size={14} className={meta.color} />
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm text-fg">
                <span className="font-medium">{meta.name}</span>{' '}
                produced{' '}
                <span className="font-mono text-xs">{artifact.artifactType.replace('_', ' ')}</span>
                {artifact.version > 1 && (
                  <span className="text-fg-subtle"> v{artifact.version}</span>
                )}
              </p>
              <p className="text-xs text-fg-muted">
                {formatDistance(new Date(artifact.createdAt), new Date())} ago
              </p>
            </div>
          </motion.div>
        );
      })}
    </div>
  );
}
