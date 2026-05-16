import type { ActionStatus, ActionType, ArtifactKind, ArtifactStatus } from '@baseflo/api-client';

export const operatingKeys = {
  all: ['operating'] as const,
  runs: () => [...operatingKeys.all, 'runs'] as const,
  run: (runId: string) => [...operatingKeys.runs(), runId] as const,
  runResult: (runId: string) => [...operatingKeys.run(runId), 'result'] as const,
  artifacts: () => [...operatingKeys.all, 'artifacts'] as const,
  artifactList: (query?: {
    kind?: ArtifactKind;
    status?: ArtifactStatus;
    include_terminal?: boolean;
    limit?: number;
  }) => [...operatingKeys.artifacts(), query ?? {}] as const,
  artifactLatest: (kind: ArtifactKind) => [...operatingKeys.artifacts(), 'latest', kind] as const,
  inbox: (limit: number) => [...operatingKeys.artifacts(), 'inbox', limit] as const,
  sources: () => [...operatingKeys.all, 'sources'] as const,
  actions: (query?: {
    action_type?: ActionType;
    status?: ActionStatus;
    include_terminal?: boolean;
    limit?: number;
  }) => [...operatingKeys.all, 'actions', query ?? {}] as const,
  cohorts: (limit: number) => [...operatingKeys.all, 'cohorts', limit] as const,
};
