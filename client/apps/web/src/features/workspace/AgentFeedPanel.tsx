import type { ComponentType } from 'react';
import { useQuery } from '@tanstack/react-query';
import { formatDistance } from 'date-fns';
import { motion, AnimatePresence } from 'framer-motion';
import { cn } from '@baseflo/ui/lib/utils';
import { Card, CardContent, Badge } from '@baseflo/ui';
import {
  IconSparkles,
  IconEye,
  IconLightbulb,
  IconZap,
  IconWarning,
} from '@baseflo/ui/icons';
import { useGateway } from '../../providers/GatewayProvider.js';
import { getAgent, TONE_STYLE_MAP } from '../../config/agents.js';

type FeedEntryType = 'thought' | 'observation' | 'suggestion' | 'action' | 'warning';

interface FeedEntry {
  id: string;
  agentId: string;
  entryType: FeedEntryType;
  content: string;
  createdAt: string;
}

const ENTRY_TYPE_CONFIG: Record<
  FeedEntryType,
  {
    label: string;
    icon: ComponentType<{ size?: number; className?: string }>;
    variant: 'neutral' | 'accent' | 'success' | 'warning' | 'info' | 'danger';
  }
> = {
  thought: { label: 'Thought', icon: IconSparkles, variant: 'neutral' },
  observation: { label: 'Observation', icon: IconEye, variant: 'info' },
  suggestion: { label: 'Suggestion', icon: IconLightbulb, variant: 'accent' },
  action: { label: 'Action', icon: IconZap, variant: 'success' },
  warning: { label: 'Warning', icon: IconWarning, variant: 'warning' },
};

interface AgentFeedPanelProps {
  projectId: string;
  agentId?: string;
}

export function AgentFeedPanel({ projectId, agentId }: AgentFeedPanelProps) {
  const gateway = useGateway();

  const feedQuery = useQuery({
    queryKey: ['agent-feed', projectId, agentId],
    queryFn: async () => {
      const data = await gateway.agents.getFeed(projectId, agentId);
      return ((data as unknown as { entries?: FeedEntry[] }).entries) ?? [];
    },
    enabled: !!projectId,
    refetchInterval: 10000,
  });

  return (
    <Card className="h-full border-border">
      <CardContent className="flex h-full flex-col gap-3 p-4">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-fg">Agent Feed</h3>
          {feedQuery.isFetching && (
            <span className="animate-pulse text-[10px] text-fg-subtle">
              Updating…
            </span>
          )}
        </div>

        <div className="flex-1 overflow-auto">
          <AnimatePresence initial={false}>
            {feedQuery.data && feedQuery.data.length > 0 ? (
              <div className="flex flex-col gap-2">
                {feedQuery.data.map((entry, i) => {
                  const agent = getAgent(entry.agentId);
                  const tone = agent ? TONE_STYLE_MAP[agent.tone] : null;
                  const typeConfig =
                    ENTRY_TYPE_CONFIG[entry.entryType] ?? ENTRY_TYPE_CONFIG.thought;
                  const TypeIcon = typeConfig.icon;

                  return (
                    <motion.div
                      key={entry.id}
                      initial={{ opacity: 0, x: -8 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ delay: i * 0.03 }}
                      className="rounded-lg border border-border bg-surface/80 p-3 backdrop-blur"
                    >
                      <div className="flex items-start gap-2">
                        <div
                          className={cn(
                            'flex h-6 w-6 shrink-0 items-center justify-center rounded-full border text-[10px] font-bold',
                            tone
                              ? `${tone.border} ${tone.bg} ${tone.text}`
                              : 'border-border bg-surface-2 text-fg-subtle',
                          )}
                        >
                          {agent?.name.charAt(0) ?? '?'}
                        </div>
                        <div className="min-w-0 flex-1">
                          <div className="flex flex-wrap items-center gap-1.5">
                            <span className="text-xs font-medium text-fg">
                              {agent?.name ?? entry.agentId}
                            </span>
                            <Badge
                              variant={typeConfig.variant}
                              className="px-1.5 py-0 text-[10px]"
                            >
                              <TypeIcon size={10} className="mr-0.5" />
                              {typeConfig.label}
                            </Badge>
                          </div>
                          <p className="mt-1 text-xs leading-relaxed text-fg-muted">
                            {entry.content}
                          </p>
                          <p className="mt-1 text-[10px] text-fg-subtle">
                            {formatDistance(
                              new Date(entry.createdAt),
                              new Date(),
                            )}{' '}
                            ago
                          </p>
                        </div>
                      </div>
                    </motion.div>
                  );
                })}
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center py-8 text-center">
                <IconSparkles
                  size={20}
                  className="mb-2 text-fg-subtle"
                />
                <p className="text-sm text-fg-muted">
                  No agent activity yet
                </p>
                <p className="mt-1 text-[10px] text-fg-subtle">
                  Agents will post thoughts and observations here
                </p>
              </div>
            )}
          </AnimatePresence>
        </div>
      </CardContent>
    </Card>
  );
}
