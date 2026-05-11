import { useEffect, useMemo, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { cn } from '@baseflo/ui/lib/utils';
import { useGateway } from '../../providers/GatewayProvider.js';
import type { SagaEvent } from '@baseflo/contracts';
import { IconSparkles, IconCheck, IconWarning } from '@baseflo/ui/icons';
import { useQuery } from '@tanstack/react-query';
import { formatDistance } from 'date-fns';
import { AGENTS, getAgentForArtifact, TONE_STYLE_MAP } from '../../config/agents.js';

type AgentStatus = 'idle' | 'thinking' | 'done' | 'error';

interface Agent {
  id: string;
  name: string;
  role: string;
  status: AgentStatus;
  personality: string;
  lastArtifact?: string;
}

interface AgentDockProps {
  conversationId?: string | null;
  projectId?: string | null;
}

export function AgentDock({ conversationId, projectId }: AgentDockProps) {
  const gateway = useGateway();
  const [hovered, setHovered] = useState<string | null>(null);
  const [agents, setAgents] = useState<Agent[]>(
    AGENTS.map((a) => ({ ...a, status: 'idle' as AgentStatus })),
  );

  const systemStatus = useMemo(() => {
    const thinking = agents.filter((a) => a.status === 'thinking').length;
    const errors = agents.filter((a) => a.status === 'error').length;
    const done = agents.filter((a) => a.status === 'done').length;

    if (errors > 0) return { label: 'Degraded', tone: 'danger' as const };
    if (thinking > 0) return { label: 'Processing', tone: 'accent' as const };
    if (done === agents.length) return { label: 'All Systems Nominal', tone: 'success' as const };
    return { label: 'Standby', tone: 'muted' as const };
  }, [agents]);

  // Poll artifact list for status + last-seen when no active conversation
  const artifactsQuery = useQuery({
    queryKey: ['dock-artifacts', projectId],
    queryFn: async () => {
      if (!projectId) return [];
      const resp = (await gateway.artifacts.list(projectId)) as {
        artifacts: Array<{
          artifactId: string;
          artifactType: string;
          producedBy: string;
          createdAt: string;
          provenance?: {
            latencyMs?: number;
            tokensPrompt?: number;
            tokensCompletion?: number;
          };
        }>;
      };
      return resp.artifacts;
    },
    enabled: !!projectId && !conversationId,
    refetchInterval: 15000,
  });

  useEffect(() => {
    if (!projectId || conversationId) return;
    const artifacts = artifactsQuery.data ?? [];
    const latestByAgent = new Map<string, (typeof artifacts)[0]>();
    for (const a of artifacts) {
      const agentConfig = getAgentForArtifact(a.artifactType);
      if (!agentConfig) continue;
      const existing = latestByAgent.get(agentConfig.id);
      if (!existing || new Date(a.createdAt) > new Date(existing.createdAt)) {
        latestByAgent.set(agentConfig.id, a);
      }
    }
    setAgents((prev) =>
      prev.map((a) => {
        const latest = latestByAgent.get(a.id);
        if (!latest) return { ...a, status: 'idle' as AgentStatus, lastArtifact: undefined };
        return {
          ...a,
          status: 'done' as AgentStatus,
          lastArtifact: `${latest.artifactType.replace('_', ' ')} · ${formatDistance(new Date(latest.createdAt), new Date())} ago`,
        };
      }),
    );
  }, [artifactsQuery.data, projectId, conversationId]);

  // Subscribe to SSE when actively building
  useEffect(() => {
    if (!conversationId) return;
    setAgents(AGENTS.map((a) => ({ ...a, status: 'idle' as AgentStatus })));
    const subscription = gateway.sagas.subscribe(conversationId, {
      onEvent: (event: SagaEvent) => {
        setAgents((prev) => {
          const next = [...prev];
          switch (event.kind) {
            case 'agent.start': {
              const payload = event.payload as { agentName?: string };
              const name = payload.agentName ?? '';
              const idx = next.findIndex((a) => a.id === name);
              if (idx >= 0) {
                const agent = next[idx]!;
                next[idx] = { ...agent, status: 'thinking' };
              }
              break;
            }
            case 'agent.complete': {
              const payload = event.payload as { agentName?: string };
              const name = payload.agentName ?? '';
              const idx = next.findIndex((a) => a.id === name);
              if (idx >= 0) {
                const agent = next[idx]!;
                next[idx] = { ...agent, status: 'done' };
              }
              break;
            }
            case 'artifact.ready': {
              const payload = event.payload as { artifactKind?: string };
              const agentConfig = getAgentForArtifact(payload.artifactKind ?? '');
              const idx = agentConfig ? next.findIndex((a) => a.id === agentConfig.id) : -1;
              if (idx >= 0) {
                const agent = next[idx]!;
                next[idx] = { ...agent, status: 'done' };
              }
              break;
            }
            case 'error.terminal':
              next.forEach((a, i) => {
                if (a.status === 'thinking') next[i] = { ...a, status: 'error' };
              });
              break;
          }
          return next;
        });
      },
    });
    return () => subscription.close();
  }, [conversationId, gateway]);

  return (
    <div className="absolute bottom-4 left-1/2 z-50 flex -translate-x-1/2 items-center gap-3 rounded-2xl border border-border bg-surface/95 px-4 py-2.5 shadow-[0_8px_32px_hsl(var(--color-fg)/0.08)] backdrop-blur">
      {/* System Status */}
      <div className="flex items-center gap-2 border-r border-border pr-3">
        <div className="relative flex h-2 w-2 items-center justify-center">
          <span
            className={cn(
              'absolute inline-flex h-full w-full animate-ping rounded-full opacity-40',
              systemStatus.tone === 'accent' && 'bg-accent',
              systemStatus.tone === 'success' && 'bg-success',
              systemStatus.tone === 'danger' && 'bg-danger',
              systemStatus.tone === 'muted' && 'bg-fg-subtle',
            )}
          />
          <span
            className={cn(
              'relative inline-flex h-2 w-2 rounded-full',
              systemStatus.tone === 'accent' && 'bg-accent',
              systemStatus.tone === 'success' && 'bg-success',
              systemStatus.tone === 'danger' && 'bg-danger',
              systemStatus.tone === 'muted' && 'bg-fg-subtle',
            )}
          />
        </div>
        <span className="text-[10px] font-semibold uppercase tracking-wider text-fg-subtle">
          {systemStatus.label}
        </span>
      </div>

      {/* Agent Avatars */}
      {agents.map((agent) => {
        const tone =
          TONE_STYLE_MAP[AGENTS.find((a) => a.id === agent.id)?.tone ?? 'accent'];
        return (
          <div
            key={agent.id}
            className="relative"
          >
            <button
              type="button"
              aria-label={`${agent.name} status`}
              onFocus={() => setHovered(agent.id)}
              onBlur={() => setHovered(null)}
              onMouseEnter={() => setHovered(agent.id)}
              onMouseLeave={() => setHovered(null)}
              className={cn(
                'relative flex h-9 w-9 items-center justify-center rounded-full border transition-all duration-300',
                agent.status === 'thinking'
                  ? `${tone.border} ${tone.bg} ${tone.glowShadow} animate-pulse`
                  : agent.status === 'done'
                    ? 'border-success bg-success/10 shadow-[0_0_8px_hsl(var(--color-success)/0.25)]'
                    : agent.status === 'error'
                      ? 'border-danger bg-danger/10 shadow-[0_0_8px_hsl(var(--color-danger)/0.25)]'
                      : 'border-border bg-surface-2 hover:border-border-focus hover:shadow-sm',
              )}
            >
              <span className="text-xs font-bold text-fg">
                {agent.name.charAt(0)}
              </span>

              {/* Status dot */}
              <span
                className={cn(
                  'absolute -bottom-0.5 -right-0.5 h-2.5 w-2.5 rounded-full border-2 border-surface',
                  agent.status === 'thinking' && tone.dot,
                  agent.status === 'done' && 'bg-success',
                  agent.status === 'error' && 'bg-danger',
                  agent.status === 'idle' && 'bg-fg-subtle',
                )}
              />
            </button>

            <AnimatePresence>
              {hovered === agent.id && (
                <motion.div
                  initial={{ opacity: 0, y: 6, scale: 0.96 }}
                  animate={{ opacity: 1, y: 0, scale: 1 }}
                  exit={{ opacity: 0, y: 6, scale: 0.96 }}
                  transition={{ duration: 0.15 }}
                  className="absolute bottom-full left-1/2 mb-3 w-52 -translate-x-1/2 rounded-xl border border-border bg-surface p-3.5 shadow-[0_12px_40px_hsl(var(--color-fg)/0.12)]"
                >
                  <div className="flex items-center gap-2">
                    <div
                      className={cn(
                        'flex h-7 w-7 items-center justify-center rounded-full border text-[10px] font-bold',
                        agent.status === 'thinking'
                          ? `${tone.border} ${tone.bg} ${tone.text}`
                          : agent.status === 'done'
                            ? 'border-success bg-success/10 text-success'
                            : agent.status === 'error'
                              ? 'border-danger bg-danger/10 text-danger'
                              : 'border-border bg-surface-2 text-fg-subtle',
                      )}
                    >
                      {agent.name.charAt(0)}
                    </div>
                    <div>
                      <p className="text-sm font-semibold text-fg">{agent.name}</p>
                      <p className="text-[11px] text-fg-muted">{agent.role}</p>
                    </div>
                  </div>
                  <p className="mt-2 text-[11px] leading-relaxed text-fg-subtle">
                    {agent.personality}
                  </p>
                  <div className="mt-2 flex items-center gap-1.5">
                    {agent.status === 'thinking' && (
                      <>
                        <IconSparkles size={12} className={tone.text} />
                        <span
                          className={cn(
                            'text-[10px] font-medium uppercase tracking-wider',
                            tone.text,
                          )}
                        >
                          Working
                        </span>
                      </>
                    )}
                    {agent.status === 'done' && (
                      <>
                        <IconCheck size={12} className="text-success" />
                        <span className="text-[10px] font-medium uppercase tracking-wider text-success">
                          Complete
                        </span>
                      </>
                    )}
                    {agent.status === 'error' && (
                      <>
                        <IconWarning size={12} className="text-danger" />
                        <span className="text-[10px] font-medium uppercase tracking-wider text-danger">
                          Error
                        </span>
                      </>
                    )}
                    {agent.status === 'idle' && (
                      <span className="text-[10px] font-medium uppercase tracking-wider text-fg-subtle">
                        Standby
                      </span>
                    )}
                  </div>
                  {agent.lastArtifact && (
                    <div className="mt-2 border-t border-border pt-2">
                      <p className="text-[10px] uppercase tracking-wider text-fg-subtle">Last delivery</p>
                      <p className="text-xs text-accent">{agent.lastArtifact}</p>
                    </div>
                  )}
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        );
      })}
    </div>
  );
}
