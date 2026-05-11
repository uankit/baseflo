import type { SagaEvent, ClarificationQuestion } from '@baseflo/contracts';

/**
 * Reducer that translates the SSE event stream into a renderable saga state.
 * Every event kind from docs/04-database-schema.md §4.13 is handled here.
 */

export type StageStatus = 'pending' | 'running' | 'passed' | 'warning' | 'failed' | 'repairing';

export interface StageState {
  id: string;
  agentName: string;
  label: string;
  status: StageStatus;
  startedAt: string | null;
  completedAt: string | null;
  durationMs: number | null;
  inputTokens: number | null;
  outputTokens: number | null;
  warnings: string[];
}

export interface ArtifactPreview {
  id: string;
  kind: string;
  label: string;
  preview: string;
  receivedAt: string;
}

export type ConnectionState = 'connecting' | 'live' | 'reconnecting' | 'closed' | 'terminal';

export interface SagaState {
  events: SagaEvent[];
  stages: StageState[];
  artifacts: ArtifactPreview[];
  clarification: {
    questions: ClarificationQuestion[];
    requestedAt: string | null;
  } | null;
  ready: { versionId: string | null; projectId: string | null } | null;
  error: { code: string; message: string } | null;
  connection: ConnectionState;
  lastSequence: number;
  lastHeartbeat: string | null;
}

export const initialSagaState: SagaState = {
  events: [],
  stages: [],
  artifacts: [],
  clarification: null,
  ready: null,
  error: null,
  connection: 'connecting',
  lastSequence: 0,
  lastHeartbeat: null,
};

const AGENT_TO_LABEL: Record<string, string> = {
  ClarificationAgent: 'Asking clarifying questions',
  ColumnClassifier: 'Understanding columns',
  EntityReconciler: 'Reconciling customers',
  CardinalityResolver: 'Resolving relationships',
  ConstraintProposer: 'Proposing constraints',
  PhysicalSchemaArchitect: 'Designing schema',
  KPIPlanner: 'Setting up analytics',
  CoherenceGate: 'Final coherence check',
  IntentInterpreter: 'Reading refinement intent',
  ImpactAnalyzer: 'Analyzing impact',
  ChangePlanner: 'Planning changes',
};

function stageLabelFor(agentName: string): string {
  return AGENT_TO_LABEL[agentName] ?? agentName;
}

export function reduceSaga(state: SagaState, event: SagaEvent): SagaState {
  // Always append + bump sequence
  const events = [...state.events, event];
  const lastSequence = Math.max(state.lastSequence, event.sequence);
  const next: SagaState = { ...state, events, lastSequence };

  switch (event.kind) {
    case 'heartbeat':
      return { ...next, lastHeartbeat: event.createdAt, connection: 'live' };

    case 'conversation.message':
      // nothing structural; surfaced via events tail in UI
      return next;

    case 'clarification.required': {
      const payload = event.payload as { questions?: ClarificationQuestion[] };
      const questions = payload.questions ?? [];
      return {
        ...next,
        clarification: { questions, requestedAt: event.createdAt },
      };
    }

    case 'clarification.answered':
      return { ...next, clarification: null };

    case 'agent.start': {
      const payload = event.payload as { agentName: string; label?: string };
      const stageId = payload.agentName;
      const exists = next.stages.find((s) => s.id === stageId);
      const stage: StageState = exists ?? {
        id: stageId,
        agentName: payload.agentName,
        label: payload.label ?? stageLabelFor(payload.agentName),
        status: 'running',
        startedAt: event.createdAt,
        completedAt: null,
        durationMs: null,
        inputTokens: null,
        outputTokens: null,
        warnings: [],
      };
      const stages = exists
        ? next.stages.map((s) =>
            s.id === stageId
              ? { ...s, label: payload.label ?? s.label, status: 'running' as const }
              : s,
          )
        : [...next.stages, stage];
      return { ...next, stages };
    }

    case 'agent.complete': {
      const payload = event.payload as {
        agentName: string;
        durationMs?: number;
        inputTokens?: number;
        outputTokens?: number;
      };
      const stages = next.stages.map((s) =>
        s.id === payload.agentName
          ? {
              ...s,
              status: 'passed' as const,
              completedAt: event.createdAt,
              durationMs: payload.durationMs ?? null,
              inputTokens: payload.inputTokens ?? null,
              outputTokens: payload.outputTokens ?? null,
            }
          : s,
      );
      return { ...next, stages };
    }

    case 'validation.passed':
      return next;

    case 'validation.warning': {
      const payload = event.payload as {
        agentName?: string;
        target?: string;
        issues?: string[];
        message?: string;
      };
      const stageId = payload.agentName ?? (payload.target === 'workspace' ? 'CoherenceGate' : null);
      if (!stageId) return next;
      const warnings = validationMessages(payload, 'A validation warning was raised');
      const stages = next.stages.map((s) =>
        s.id === stageId
          ? {
              ...s,
              status: s.status === 'passed' ? ('warning' as const) : s.status,
              warnings: [...s.warnings, ...warnings],
            }
          : s,
      );
      return { ...next, stages };
    }

    case 'validation.failed': {
      const payload = event.payload as {
        agentName?: string;
        target?: string;
        issues?: string[];
        message?: string;
      };
      const stageId = payload.agentName ?? (payload.target === 'workspace' ? 'CoherenceGate' : null);
      if (!stageId) return next;
      const warnings = validationMessages(payload, 'Validation failed');
      const stages = next.stages.map((s) =>
        s.id === stageId
          ? {
              ...s,
              status: 'failed' as const,
              warnings: [...s.warnings, ...warnings],
            }
          : s,
      );
      return { ...next, stages };
    }

    case 'artifact.ready': {
      const payload = event.payload as {
        artifactId?: string;
        artifactKind?: string;
        label?: string;
        preview?: string;
      };
      if (!payload.artifactId) return next;
      const artifact: ArtifactPreview = {
        id: payload.artifactId,
        kind: payload.artifactKind ?? 'artifact',
        label: payload.label ?? payload.artifactId,
        preview: payload.preview ?? '',
        receivedAt: event.createdAt,
      };
      return { ...next, artifacts: [...next.artifacts, artifact] };
    }

    case 'workspace.ready': {
      const payload = event.payload as {
        versionId?: string;
        projectVersionId?: string;
        projectId?: string;
      };
      return {
        ...next,
        ready: {
          versionId: payload.versionId ?? payload.projectVersionId ?? null,
          projectId: payload.projectId ?? null,
        },
        connection: 'closed',
      };
    }

    case 'error.recoverable': {
      const payload = event.payload as { agentName?: string; message?: string };
      if (!payload.agentName) return next;
      const stages = next.stages.map((s) =>
        s.id === payload.agentName ? { ...s, status: 'repairing' as const } : s,
      );
      return { ...next, stages };
    }

    case 'error.terminal': {
      const payload = event.payload as { code?: string; errorCode?: string; message?: string };
      return {
        ...next,
        error: {
          code: payload.code ?? payload.errorCode ?? 'BF-WEB-021',
          message: payload.message ?? 'The build hit a hard error.',
        },
        connection: 'terminal',
      };
    }

    case 'refinement.start':
      return next;

    case 'refinement.complete':
      return next;

    default:
      return next;
  }
}

function validationMessages(payload: {
  issues?: string[];
  message?: string;
}, fallback: string): string[] {
  if (payload.message) return [payload.message];
  if (payload.issues && payload.issues.length > 0) return payload.issues;
  return [fallback];
}
