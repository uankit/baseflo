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
  EntityRegisterPackageSchema,
  InsightRankingPackageSchema,
  KnowledgeGraphPackageSchema,
  LineagePackageSchema,
  SemanticLayerPackageSchema,
  EntityResolutionPackageSchema,
  SourceStructurePackageSchema,
  safeParseArtifactPayload,
} from '../model/schemas.js';

export function useLatestArtifact(kind: ArtifactKind) {
  const gateway = useGateway();
  return useQuery({
    queryKey: operatingKeys.artifactLatest(kind),
    queryFn: async (): Promise<ArtifactRecord | null> => {
      const artifacts = await gateway.artifacts.list({ kind, limit: 1 });
      return artifacts[0] ?? null;
    },
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
  const sourceStructure = useLatestArtifact('source_structure');
  return {
    businessViewArtifact: businessView.data ?? null,
    businessSurfaceArtifact: businessSurfaces.data ?? null,
    sourceStructureArtifact: sourceStructure.data ?? null,
    businessView: useMemo(
      () => safeParseArtifactPayload(businessView.data, 'business_view', BusinessViewPackageSchema),
      [businessView.data],
    ),
    businessSurfaces: useMemo(
      () =>
        safeParseArtifactPayload(businessSurfaces.data, 'business_surfaces', BusinessSurfacePackageSchema),
      [businessSurfaces.data],
    ),
    sourceStructure: useMemo(
      () =>
        safeParseArtifactPayload(sourceStructure.data, 'source_structure', SourceStructurePackageSchema),
      [sourceStructure.data],
    ),
    isPending: businessView.isPending || businessSurfaces.isPending || sourceStructure.isPending,
    isError: businessView.isError || businessSurfaces.isError || sourceStructure.isError,
    error: businessView.error ?? businessSurfaces.error ?? sourceStructure.error,
    refetch: () => {
      void businessView.refetch();
      void businessSurfaces.refetch();
      void sourceStructure.refetch();
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

export function useEntityRegister() {
  const query = useLatestArtifact('entity_register');
  return {
    ...query,
    parsed: useMemo(
      () => safeParseArtifactPayload(query.data, 'entity_register', EntityRegisterPackageSchema),
      [query.data],
    ),
  };
}

export function useEntityResolutionArtifact() {
  const query = useLatestArtifact('entity_resolution');
  return {
    ...query,
    parsed: useMemo(
      () => safeParseArtifactPayload(query.data, 'entity_resolution', EntityResolutionPackageSchema),
      [query.data],
    ),
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
