import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useGateway } from '../../providers/GatewayProvider.js';

const insightsKey = (projectId: string) => ['insights', projectId] as const;
const statsKey = (projectId: string) => ['insights', 'stats', projectId] as const;

export function useInsights(projectId: string) {
  const gateway = useGateway();
  const queryClient = useQueryClient();

  const listQuery = useQuery({
    queryKey: insightsKey(projectId),
    queryFn: () => gateway.insights.list({ project_id: projectId, limit: 50 }),
    enabled: !!projectId,
    refetchInterval: 30_000,
  });

  const statsQuery = useQuery({
    queryKey: statsKey(projectId),
    queryFn: () => gateway.insights.stats(projectId),
    enabled: !!projectId,
    refetchInterval: 30_000,
  });

  const markRead = useMutation({
    mutationFn: (insightId: string) => gateway.insights.markRead(insightId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: insightsKey(projectId) });
      queryClient.invalidateQueries({ queryKey: statsKey(projectId) });
    },
  });

  const dismiss = useMutation({
    mutationFn: (insightId: string) => gateway.insights.dismiss(insightId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: insightsKey(projectId) });
      queryClient.invalidateQueries({ queryKey: statsKey(projectId) });
    },
  });

  return {
    insights: listQuery.data?.items ?? [],
    total: listQuery.data?.total ?? 0,
    unreadCount: listQuery.data?.unread_count ?? 0,
    stats: statsQuery.data,
    isLoading: listQuery.isLoading,
    markRead,
    dismiss,
  };
}
