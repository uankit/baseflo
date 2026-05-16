import { useMemo } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type {
  ActionRecord,
  ActionStatus,
  ActionType,
  ArtifactKind,
  ArtifactRecord,
  ArtifactStatus,
} from '@baseflo/api-client';
import { useGateway } from '../../../providers/GatewayProvider.js';
import { operatingKeys } from './queryKeys.js';
import {
  BriefPackageSchema,
  BusinessSurfacePackageSchema,
  BusinessViewPackageSchema,
  ChartGrammarPackageSchema,
  InsightRankingPackageSchema,
  KnowledgeGraphPackageSchema,
  LineagePackageSchema,
  SemanticLayerPackageSchema,
  safeParseArtifactPayload,
} from '../model/schemas.js';

const latestLoaders = {
  brief: (gateway: ReturnType<typeof useGateway>) => gateway.artifacts.brief(),
  business_view: (gateway: ReturnType<typeof useGateway>) => gateway.artifacts.businessView(),
  business_surfaces: (gateway: ReturnType<typeof useGateway>) => gateway.artifacts.businessSurfaces(),
  semantic_layer: (gateway: ReturnType<typeof useGateway>) => gateway.artifacts.semanticLayer(),
  chart_grammar: (gateway: ReturnType<typeof useGateway>) => gateway.artifacts.chartGrammar(),
  insight_ranking: (gateway: ReturnType<typeof useGateway>) => gateway.artifacts.insightRanking(),
  knowledge_graph: (gateway: ReturnType<typeof useGateway>) => gateway.artifacts.knowledgeGraph(),
  lineage: (gateway: ReturnType<typeof useGateway>) => gateway.artifacts.lineage(),
} satisfies Partial<Record<ArtifactKind, (gateway: ReturnType<typeof useGateway>) => Promise<ArtifactRecord>>>;

export function useLatestArtifact(kind: keyof typeof latestLoaders) {
  const gateway = useGateway();
  return useQuery({
    queryKey: operatingKeys.artifactLatest(kind),
    queryFn: () => latestLoaders[kind](gateway),
    retry: false,
  });
}

export function useBriefArtifact() {
  const query = useLatestArtifact('brief');
  return {
    ...query,
    parsed: useMemo(
      () => safeParseArtifactPayload(query.data, 'brief', BriefPackageSchema),
      [query.data],
    ),
  };
}

export function useBusinessLiveArtifacts() {
  const businessView = useLatestArtifact('business_view');
  const businessSurfaces = useLatestArtifact('business_surfaces');
  return {
    businessViewArtifact: businessView.data ?? null,
    businessSurfaceArtifact: businessSurfaces.data ?? null,
    businessView: useMemo(
      () => safeParseArtifactPayload(businessView.data, 'business_view', BusinessViewPackageSchema),
      [businessView.data],
    ),
    businessSurfaces: useMemo(
      () =>
        safeParseArtifactPayload(businessSurfaces.data, 'business_surfaces', BusinessSurfacePackageSchema),
      [businessSurfaces.data],
    ),
    isPending: businessView.isPending || businessSurfaces.isPending,
    isError: businessView.isError || businessSurfaces.isError,
    error: businessView.error ?? businessSurfaces.error,
    refetch: () => {
      void businessView.refetch();
      void businessSurfaces.refetch();
    },
  };
}

export function useInsightRanking() {
  const query = useLatestArtifact('insight_ranking');
  return {
    ...query,
    parsed: useMemo(
      () => safeParseArtifactPayload(query.data, 'insight_ranking', InsightRankingPackageSchema),
      [query.data],
    ),
  };
}

export function useSourceIntelligenceArtifacts() {
  const semanticLayer = useLatestArtifact('semantic_layer');
  const chartGrammar = useLatestArtifact('chart_grammar');
  const knowledgeGraph = useLatestArtifact('knowledge_graph');
  const lineage = useLatestArtifact('lineage');
  return {
    semanticLayer: safeParseArtifactPayload(semanticLayer.data, 'semantic_layer', SemanticLayerPackageSchema),
    chartGrammar: safeParseArtifactPayload(chartGrammar.data, 'chart_grammar', ChartGrammarPackageSchema),
    knowledgeGraph: safeParseArtifactPayload(knowledgeGraph.data, 'knowledge_graph', KnowledgeGraphPackageSchema),
    lineage: safeParseArtifactPayload(lineage.data, 'lineage', LineagePackageSchema),
    isPending: semanticLayer.isPending || chartGrammar.isPending || knowledgeGraph.isPending || lineage.isPending,
    error: semanticLayer.error ?? chartGrammar.error ?? knowledgeGraph.error ?? lineage.error,
  };
}

export function useInboxArtifacts(limit = 100) {
  const gateway = useGateway();
  return useQuery({
    queryKey: operatingKeys.inbox(limit),
    queryFn: () => gateway.artifacts.inbox(limit),
  });
}

export function useArtifactList(query?: {
  kind?: ArtifactKind;
  status?: ArtifactStatus;
  include_terminal?: boolean;
  limit?: number;
}) {
  const gateway = useGateway();
  return useQuery({
    queryKey: operatingKeys.artifactList(query),
    queryFn: () => gateway.artifacts.list(query),
  });
}

export function useActions(query?: {
  action_type?: ActionType;
  status?: ActionStatus;
  include_terminal?: boolean;
  limit?: number;
}) {
  const gateway = useGateway();
  return useQuery({
    queryKey: operatingKeys.actions(query),
    queryFn: () => gateway.actions.list(query),
  });
}

export function useActionMutations() {
  const gateway = useGateway();
  const queryClient = useQueryClient();
  const invalidate = async () => {
    await queryClient.invalidateQueries({ queryKey: operatingKeys.all });
  };

  return {
    prepare: useMutation({
      mutationFn: (actionId: string) => gateway.actions.prepare(actionId),
      onSuccess: invalidate,
    }),
    complete: useMutation({
      mutationFn: (actionId: string) => gateway.actions.complete(actionId),
      onSuccess: invalidate,
    }),
    dismiss: useMutation({
      mutationFn: (actionId: string) => gateway.actions.dismiss(actionId),
      onSuccess: invalidate,
    }),
  };
}

export function useDataSources() {
  const gateway = useGateway();
  return useQuery({
    queryKey: operatingKeys.sources(),
    queryFn: () => gateway.data.listSources(),
  });
}

export function actionForArtifact(actions: ActionRecord[], artifact: ArtifactRecord): ActionRecord | null {
  return (
    actions.find((action) => action.artifact_id === artifact.id) ??
    actions.find((action) => action.source_refs.artifact_key === artifact.artifact_key) ??
    null
  );
}
