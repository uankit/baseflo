import type { Gateway, OperatingRunResult, RunEvent } from '@baseflo/api-client';

export interface OperatingRunStreamRequest {
  mode: 'scan' | 'ask';
  question?: string;
}

export interface OperatingRunStreamState {
  runId: string | null;
  status: 'idle' | 'starting' | 'running' | 'completed' | 'partial' | 'failed';
  events: RunEvent[];
  result: OperatingRunResult | null;
  error: Error | null;
}

const eventTypes = [
  'run.queued',
  'run.started',
  'run.heartbeat',
  'run.completed',
  'run.failed',
  'operating.started',
  'profiler.started',
  'profiler.completed',
  'profiler.failed',
  'data_plane.no_canonical_data',
  'agent_plane.planning_started',
  'agent_plane.planning_completed',
  'agent_plane.planning_failed',
  'agent_plane.no_analysis_plans',
  'memory.started',
  'memory.completed',
  'memory.failed',
  'execution.started',
  'execution.plan_started',
  'execution.plan_completed',
  'execution.plan_failed',
  'execution.completed',
  'agent_plane.materialization_started',
  'agent_plane.materialization_completed',
  'agent_plane.materialization_failed',
  'business_view.started',
  'business_view.completed',
  'business_view.failed',
  'business_surfaces.started',
  'business_surfaces.completed',
  'business_surfaces.failed',
  'semantic_layer.started',
  'semantic_layer.completed',
  'semantic_layer.failed',
  'chart_grammar.started',
  'chart_grammar.completed',
  'chart_grammar.failed',
  'insight_ranking.started',
  'insight_ranking.completed',
  'insight_ranking.failed',
  'entity_resolution.started',
  'entity_resolution.completed',
  'entity_resolution.failed',
  'knowledge_graph.started',
  'knowledge_graph.completed',
  'knowledge_graph.failed',
  'lineage.started',
  'lineage.completed',
  'lineage.failed',
  'artifact_plane.started',
  'artifact_plane.completed',
  'artifact_plane.failed',
  'action_plane.started',
  'action_plane.completed',
  'action_plane.failed',
  'operating.completed',
  'operating.partial',
  'operating.failed',
] as const;

export async function startOperatingRunWithEvents(
  gateway: Gateway,
  request: OperatingRunStreamRequest,
  onEvent?: (event: RunEvent) => void,
): Promise<OperatingRunResult> {
  const accepted = await gateway.operating.start(request);
  return await new Promise((resolve, reject) => {
    const source = new EventSource(resolveEventSourceUrl(accepted.events_url), {
      withCredentials: true,
    });

    const close = () => source.close();
    const finish = async (fallbackError?: Error) => {
      try {
        const result = await gateway.operating.result(accepted.run_id);
        close();
        resolve(result);
      } catch (error) {
        close();
        reject(fallbackError ?? (error instanceof Error ? error : new Error(String(error))));
      }
    };

    for (const type of eventTypes) {
      source.addEventListener(type, (message) => {
        const event = parseRunEvent(message);
        onEvent?.(event);
        if (type === 'run.completed') {
          void finish();
        }
        if (type === 'run.failed') {
          void finish(new Error(event.message || 'Operating run failed.'));
        }
      });
    }

    source.onerror = () => {
      close();
      reject(new Error('The operating run event stream closed unexpectedly.'));
    };
  });
}

function parseRunEvent(message: MessageEvent): RunEvent {
  const parsed = JSON.parse(String(message.data)) as RunEvent;
  return parsed;
}

function resolveEventSourceUrl(path: string): string {
  const base = import.meta.env.VITE_API_BASE_URL as string | undefined;
  if (!base) return path;
  return `${base.replace(/\/+$/, '')}${path}`;
}
