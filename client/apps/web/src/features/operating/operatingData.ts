import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { OperatingBrief } from '@baseflo/api-client';
import { useGateway } from '../../providers/GatewayProvider.js';

export type AnyRecord = Record<string, unknown>;

export function isRecord(value: unknown): value is AnyRecord {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

export function asRecord(value: unknown): AnyRecord {
  return isRecord(value) ? value : {};
}

export function asRecordArray(value: unknown): AnyRecord[] {
  return Array.isArray(value) ? value.filter(isRecord) : [];
}

export function asString(value: unknown, fallback = ''): string {
  return typeof value === 'string' && value.trim() ? value : fallback;
}

export function asNumber(value: unknown, fallback = 0): number {
  return typeof value === 'number' && Number.isFinite(value) ? value : fallback;
}

export function asStringArray(value: unknown): string[] {
  return Array.isArray(value)
    ? value.filter((item): item is string => typeof item === 'string')
    : [];
}

export function useOperatingBrief() {
  const gateway = useGateway();
  return useQuery({
    queryKey: ['operating', 'brief'],
    queryFn: () => gateway.operating.brief(),
  });
}

export function useOperatingScan() {
  const gateway = useGateway();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => gateway.operating.scan(),
    onSuccess: (brief: OperatingBrief) => {
      queryClient.setQueryData(['operating', 'brief'], brief);
    },
  });
}

export function businessBrief(brief: OperatingBrief | undefined): AnyRecord {
  return asRecord(asRecord(brief?.business).brief);
}

export function businessModel(brief: OperatingBrief | undefined): AnyRecord {
  return asRecord(businessBrief(brief).business_model);
}

export function crossTeamReport(brief: OperatingBrief | undefined): AnyRecord {
  return asRecord(businessBrief(brief).cross_team);
}

export function topInsights(brief: OperatingBrief | undefined): AnyRecord[] {
  const top = asRecordArray(businessBrief(brief).top_insights);
  return top.length ? top : asRecordArray(brief?.insights);
}

export function teamBylines(brief: OperatingBrief | undefined): AnyRecord[] {
  return asRecordArray(businessBrief(brief).team_bylines);
}

export function actionBacklog(brief: OperatingBrief | undefined): AnyRecord[] {
  const backlog = asRecordArray(businessBrief(brief).action_backlog);
  return backlog.length ? backlog : asRecordArray(brief?.actions);
}

export function insightActions(insight: AnyRecord | undefined, brief: OperatingBrief | undefined): AnyRecord[] {
  const embedded = asRecordArray(insight?.actions);
  if (embedded.length) return embedded;
  const insightId = asString(insight?.id);
  if (!insightId) return [];
  return actionBacklog(brief).filter((action) => asString(action.insight_id) === insightId);
}

export function lastSyncedAt(brief: OperatingBrief | undefined): string | undefined {
  return brief?.summary?.last_built_at ?? undefined;
}

export function lastSyncedLabel(brief: OperatingBrief | undefined): string | undefined {
  const iso = lastSyncedAt(brief);
  if (!iso) return undefined;
  const then = new Date(iso);
  const diffMs = Date.now() - then.getTime();
  const minutes = Math.round(diffMs / 60_000);
  if (minutes < 1) return 'just now';
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.round(hours / 24);
  return `${days}d ago`;
}
