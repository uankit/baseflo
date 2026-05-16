import { z } from 'zod';
import type { Transport } from './transports/base.js';

export interface GatewayConfig {
  transport: Transport;
}

export interface AuthUser {
  id: string;
  email: string;
  status: string;
}

export interface AuthOrganization {
  id: string;
  name: string;
  slug: string;
  plan?: string;
}

export interface AuthSession {
  access_token: string;
  refresh_token?: string;
  token_type: string;
  user: AuthUser;
  current_organization: AuthOrganization;
}

export interface MeResponse {
  user: AuthUser;
  current_organization: AuthOrganization;
}

export interface ConnectorInfo {
  kind: string;
  display_name: string;
  description: string;
  auth_method: string;
  capabilities: string[];
}

export interface DataSourceInfo {
  id: string;
  kind: string;
  name: string;
  status: string;
  discovered_schema?: Record<string, unknown> | null;
  last_synced_at?: string | null;
  last_error?: string | null;
  created_at: string;
}

export interface AvailableResource {
  external_id: string;
  name: string;
  metadata: Record<string, unknown>;
}

export interface OperatingRunResult {
  run_id: string;
  mode: 'scan' | 'ask';
  organization_id: string;
  question?: string | null;
  status: 'completed' | 'partial' | 'failed';
  started_at: string;
  completed_at?: string | null;
  profile?: Record<string, unknown> | null;
  context_summary: {
    snapshot_count: number;
    asset_count: number;
    field_count: number;
    graph_edge_count: number;
    row_count: number;
  };
  business_model?: Record<string, unknown> | null;
  asset_roles: Array<Record<string, unknown>>;
  field_roles: Array<Record<string, unknown>>;
  business_graph?: Record<string, unknown> | null;
  patterns?: Record<string, unknown> | null;
  analysis_plans: Array<Record<string, unknown>>;
  executions: Array<Record<string, unknown>>;
  memory_writes: Array<Record<string, unknown>>;
  interpretations: Array<Record<string, unknown>>;
  chart_specs: Array<Record<string, unknown>>;
  action_batches: Array<Record<string, unknown>>;
  narratives: Array<Record<string, unknown>>;
  brief?: Record<string, unknown> | null;
  business_view?: BusinessViewPackage | null;
  business_surfaces?: BusinessSurfacePackage | null;
  semantic_layer?: SemanticLayerPackage | null;
  chart_grammar?: ChartGrammarPackage | null;
  insight_ranking?: InsightRankingPackage | null;
  entity_resolution?: EntityResolutionRunResult | null;
  knowledge_graph?: KnowledgeGraphMaterialization | null;
  lineage?: LineagePackage | null;
  artifacts?: ArtifactPlaneRunResult | null;
  action_plane?: ActionPlaneRunResult | null;
  errors: Array<Record<string, unknown>>;
}

export type RunKind = 'operating' | 'source_sync' | 'action' | 'export';
export type RunStatus = 'queued' | 'running' | 'completed' | 'partial' | 'failed' | 'cancelled';
export type ArtifactKind =
  | 'brief'
  | 'business_view'
  | 'business_surfaces'
  | 'semantic_layer'
  | 'chart_grammar'
  | 'insight_ranking'
  | 'entity_resolution'
  | 'knowledge_graph'
  | 'insight'
  | 'inbox_item'
  | 'ask_answer'
  | 'chart'
  | 'table'
  | 'narrative'
  | 'audience'
  | 'lineage'
  | 'action'
  | 'run_summary';
export type ArtifactStatus = 'new' | 'seen' | 'snoozed' | 'dismissed' | 'resolved';
export type ActionType = 'email_draft' | 'export_list' | 'save_cohort';
export type ActionStatus = 'proposed' | 'prepared' | 'completed' | 'dismissed';

export interface RunEvent {
  event_id: string;
  run_id: string;
  organization_id: string;
  type: string;
  stage: string;
  message: string;
  progress?: number | null;
  payload: Record<string, unknown>;
  created_at: string;
}

export interface RunRecord {
  run_id: string;
  organization_id: string;
  kind: RunKind;
  status: RunStatus;
  request: Record<string, unknown>;
  result?: Record<string, unknown> | null;
  error?: Record<string, unknown> | null;
  created_at: string;
  started_at?: string | null;
  completed_at?: string | null;
}

export interface RunAccepted {
  run_id: string;
  kind: RunKind;
  status: RunStatus;
  result_url: string;
  events_url: string;
}

export interface RunState {
  run: RunRecord;
  events: RunEvent[];
}

export interface ArtifactRecord {
  id: string;
  organization_id: string;
  run_id?: string | null;
  artifact_key: string;
  kind: ArtifactKind;
  status: ArtifactStatus;
  title: string;
  summary: string;
  why: string;
  tags: string[];
  priority: number;
  source_refs: Record<string, unknown>;
  payload: Record<string, unknown>;
  fingerprint: string;
  first_seen_at: string;
  last_seen_at: string;
  snoozed_until?: string | null;
  dismissed_at?: string | null;
  resolved_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface ArtifactPlaneRunResult {
  organization_id: string;
  run_id: string;
  artifacts: ArtifactRecord[];
  brief_artifact_id?: string | null;
  business_view_artifact_id?: string | null;
  business_surfaces_artifact_id?: string | null;
  semantic_layer_artifact_id?: string | null;
  chart_grammar_artifact_id?: string | null;
  insight_ranking_artifact_id?: string | null;
  entity_resolution_artifact_id?: string | null;
  knowledge_graph_artifact_id?: string | null;
  lineage_artifact_id?: string | null;
  inbox_item_ids: string[];
  ask_artifact_ids: string[];
  action_artifact_ids: string[];
  created_count: number;
  updated_count: number;
  unchanged_count: number;
}

export interface BusinessViewSection {
  section_id: string;
  kind: string;
  title: string;
  description: string;
  why_built: string;
  confidence: number;
  tags: string[];
  metrics: Array<Record<string, unknown>>;
  source_asset_ids: string[];
  field_refs: string[];
  graph_refs: string[];
  insight_refs: string[];
  table_refs: string[];
  chart_refs: string[];
  action_refs: string[];
  suggested_questions: string[];
  drilldowns: Array<Record<string, unknown>>;
}

export interface BusinessViewPackage {
  headline: string;
  summary: string;
  why: string;
  sections: BusinessViewSection[];
  entity_views: Array<Record<string, unknown>>;
  generated_from: Record<string, unknown>;
  confidence: number;
}

export interface BusinessSurfacePackage {
  headline: string;
  summary: string;
  why: string;
  algorithms: string[];
  surfaces: Array<Record<string, unknown>>;
  insight_graph: Record<string, unknown>;
  generated_from: Record<string, unknown>;
  confidence: number;
}

export interface SemanticLayerPackage {
  entities: Array<Record<string, unknown>>;
  dimensions: Array<Record<string, unknown>>;
  measures: Array<Record<string, unknown>>;
  metrics: Array<Record<string, unknown>>;
  surfaces: Array<Record<string, unknown>>;
  generated_from: Record<string, unknown>;
  confidence: number;
}

export interface ChartGrammarPackage {
  charts: Array<Record<string, unknown>>;
  generated_from: Record<string, unknown>;
}

export interface InsightRankingPackage {
  ranked: Array<Record<string, unknown>>;
  generated_from: Record<string, unknown>;
  scoring_version: string;
}

export interface EntityResolutionRunResult {
  plans: Array<Record<string, unknown>>;
  executions: Array<Record<string, unknown>>;
  generated_from: Record<string, unknown>;
}

export interface LineagePackage {
  runs: Array<Record<string, unknown>>;
  datasets: Array<Record<string, unknown>>;
  generated_from: Record<string, unknown>;
}

export interface KnowledgeGraphMaterialization {
  status: 'completed' | 'failed';
  backend: 'kuzu';
  graph_path: string;
  node_count: number;
  edge_count: number;
  query_examples: string[];
  error?: string | null;
}

export interface ActionRecord {
  id: string;
  organization_id: string;
  artifact_id?: string | null;
  run_id?: string | null;
  action_key: string;
  action_type: ActionType;
  status: ActionStatus;
  title: string;
  summary: string;
  why: string;
  source_refs: Record<string, unknown>;
  payload: Record<string, unknown>;
  prepared_payload: Record<string, unknown>;
  prepared_at?: string | null;
  completed_at?: string | null;
  dismissed_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface ActionPlaneRunResult {
  organization_id: string;
  run_id: string;
  actions: ActionRecord[];
  created_count: number;
  updated_count: number;
  skipped_count: number;
}

export interface SavedCohortRecord {
  id: string;
  organization_id: string;
  action_id?: string | null;
  cohort_key: string;
  name: string;
  description: string;
  audience: Record<string, unknown>;
  rows: Array<Record<string, unknown>>;
  source_refs: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

const VoidSchema = z.looseObject({});

const AuthUserSchema = z.object({
  id: z.string(),
  email: z.string(),
  status: z.string(),
});

const AuthOrganizationSchema = z.object({
  id: z.string(),
  name: z.string(),
  slug: z.string(),
  plan: z.string().optional(),
});

const AuthSessionSchema = z.object({
  access_token: z.string(),
  refresh_token: z.string().optional(),
  token_type: z.string(),
  user: AuthUserSchema,
  current_organization: AuthOrganizationSchema,
});

const MeSchema = z.object({
  user: AuthUserSchema,
  current_organization: AuthOrganizationSchema,
});

const OperatingRunResultSchema = z.object({
  run_id: z.string(),
  mode: z.enum(['scan', 'ask']),
  organization_id: z.string(),
  question: z.string().nullable().optional(),
  status: z.enum(['completed', 'partial', 'failed']),
  started_at: z.string(),
  completed_at: z.string().nullable().optional(),
  profile: z.record(z.string(), z.unknown()).nullable().optional(),
  context_summary: z.object({
    snapshot_count: z.number(),
    asset_count: z.number(),
    field_count: z.number(),
    graph_edge_count: z.number(),
    row_count: z.number(),
  }),
  business_model: z.record(z.string(), z.unknown()).nullable().optional(),
  asset_roles: z.array(z.record(z.string(), z.unknown())),
  field_roles: z.array(z.record(z.string(), z.unknown())),
  business_graph: z.record(z.string(), z.unknown()).nullable().optional(),
  patterns: z.record(z.string(), z.unknown()).nullable().optional(),
  analysis_plans: z.array(z.record(z.string(), z.unknown())),
  executions: z.array(z.record(z.string(), z.unknown())),
  memory_writes: z.array(z.record(z.string(), z.unknown())).optional().default([]),
  interpretations: z.array(z.record(z.string(), z.unknown())),
  chart_specs: z.array(z.record(z.string(), z.unknown())),
  action_batches: z.array(z.record(z.string(), z.unknown())),
  narratives: z.array(z.record(z.string(), z.unknown())),
  brief: z.record(z.string(), z.unknown()).nullable().optional(),
  business_view: z.lazy(() => BusinessViewPackageSchema).nullable().optional(),
  business_surfaces: z.lazy(() => BusinessSurfacePackageSchema).nullable().optional(),
  semantic_layer: z.lazy(() => SemanticLayerPackageSchema).nullable().optional(),
  chart_grammar: z.lazy(() => ChartGrammarPackageSchema).nullable().optional(),
  insight_ranking: z.lazy(() => InsightRankingPackageSchema).nullable().optional(),
  entity_resolution: z.lazy(() => EntityResolutionRunResultSchema).nullable().optional(),
  knowledge_graph: z.lazy(() => KnowledgeGraphMaterializationSchema).nullable().optional(),
  lineage: z.lazy(() => LineagePackageSchema).nullable().optional(),
  errors: z.array(z.record(z.string(), z.unknown())),
});

const RunKindSchema = z.enum(['operating', 'source_sync', 'action', 'export']);
const RunStatusSchema = z.enum(['queued', 'running', 'completed', 'partial', 'failed', 'cancelled']);

const RunEventSchema = z.object({
  event_id: z.string(),
  run_id: z.string(),
  organization_id: z.string(),
  type: z.string(),
  stage: z.string(),
  message: z.string(),
  progress: z.number().nullable().optional(),
  payload: z.record(z.string(), z.unknown()).default({}),
  created_at: z.string(),
});

const RunRecordSchema = z.object({
  run_id: z.string(),
  organization_id: z.string(),
  kind: RunKindSchema,
  status: RunStatusSchema,
  request: z.record(z.string(), z.unknown()).default({}),
  result: z.record(z.string(), z.unknown()).nullable().optional(),
  error: z.record(z.string(), z.unknown()).nullable().optional(),
  created_at: z.string(),
  started_at: z.string().nullable().optional(),
  completed_at: z.string().nullable().optional(),
});

const RunAcceptedSchema = z.object({
  run_id: z.string(),
  kind: RunKindSchema,
  status: RunStatusSchema,
  result_url: z.string(),
  events_url: z.string(),
});

const RunStateSchema = z.object({
  run: RunRecordSchema,
  events: z.array(RunEventSchema).default([]),
});

const ArtifactKindSchema = z.enum([
  'brief',
  'business_view',
  'business_surfaces',
  'semantic_layer',
  'chart_grammar',
  'insight_ranking',
  'entity_resolution',
  'knowledge_graph',
  'insight',
  'inbox_item',
  'ask_answer',
  'chart',
  'table',
  'narrative',
  'audience',
  'lineage',
  'action',
  'run_summary',
]);
const ArtifactStatusSchema = z.enum(['new', 'seen', 'snoozed', 'dismissed', 'resolved']);

const ArtifactRecordSchema = z.object({
  id: z.string(),
  organization_id: z.string(),
  run_id: z.string().nullable().optional(),
  artifact_key: z.string(),
  kind: ArtifactKindSchema,
  status: ArtifactStatusSchema,
  title: z.string(),
  summary: z.string(),
  why: z.string(),
  tags: z.array(z.string()).default([]),
  priority: z.number(),
  source_refs: z.record(z.string(), z.unknown()).default({}),
  payload: z.record(z.string(), z.unknown()).default({}),
  fingerprint: z.string(),
  first_seen_at: z.string(),
  last_seen_at: z.string(),
  snoozed_until: z.string().nullable().optional(),
  dismissed_at: z.string().nullable().optional(),
  resolved_at: z.string().nullable().optional(),
  created_at: z.string(),
  updated_at: z.string(),
});

const ArtifactListSchema = z.object({
  artifacts: z.array(ArtifactRecordSchema).default([]),
});

const ArtifactPlaneRunResultSchema = z.object({
  organization_id: z.string(),
  run_id: z.string(),
  artifacts: z.array(ArtifactRecordSchema).default([]),
  brief_artifact_id: z.string().nullable().optional(),
  business_view_artifact_id: z.string().nullable().optional(),
  business_surfaces_artifact_id: z.string().nullable().optional(),
  semantic_layer_artifact_id: z.string().nullable().optional(),
  chart_grammar_artifact_id: z.string().nullable().optional(),
  insight_ranking_artifact_id: z.string().nullable().optional(),
  entity_resolution_artifact_id: z.string().nullable().optional(),
  knowledge_graph_artifact_id: z.string().nullable().optional(),
  lineage_artifact_id: z.string().nullable().optional(),
  inbox_item_ids: z.array(z.string()).default([]),
  ask_artifact_ids: z.array(z.string()).default([]),
  action_artifact_ids: z.array(z.string()).default([]),
  created_count: z.number(),
  updated_count: z.number(),
  unchanged_count: z.number(),
});

const BusinessViewSectionSchema = z.object({
  section_id: z.string(),
  kind: z.string(),
  title: z.string(),
  description: z.string(),
  why_built: z.string(),
  confidence: z.number(),
  tags: z.array(z.string()).default([]),
  metrics: z.array(z.record(z.string(), z.unknown())).default([]),
  source_asset_ids: z.array(z.string()).default([]),
  field_refs: z.array(z.string()).default([]),
  graph_refs: z.array(z.string()).default([]),
  insight_refs: z.array(z.string()).default([]),
  table_refs: z.array(z.string()).default([]),
  chart_refs: z.array(z.string()).default([]),
  action_refs: z.array(z.string()).default([]),
  suggested_questions: z.array(z.string()).default([]),
  drilldowns: z.array(z.record(z.string(), z.unknown())).default([]),
});

const BusinessViewPackageSchema = z.object({
  headline: z.string(),
  summary: z.string(),
  why: z.string(),
  sections: z.array(BusinessViewSectionSchema).default([]),
  entity_views: z.array(z.record(z.string(), z.unknown())).default([]),
  generated_from: z.record(z.string(), z.unknown()).default({}),
  confidence: z.number(),
});

const BusinessSurfacePackageSchema = z.object({
  headline: z.string(),
  summary: z.string(),
  why: z.string(),
  algorithms: z.array(z.string()).default([]),
  surfaces: z.array(z.record(z.string(), z.unknown())).default([]),
  insight_graph: z.record(z.string(), z.unknown()).default({}),
  generated_from: z.record(z.string(), z.unknown()).default({}),
  confidence: z.number(),
});

const SemanticLayerPackageSchema = z.object({
  entities: z.array(z.record(z.string(), z.unknown())).default([]),
  dimensions: z.array(z.record(z.string(), z.unknown())).default([]),
  measures: z.array(z.record(z.string(), z.unknown())).default([]),
  metrics: z.array(z.record(z.string(), z.unknown())).default([]),
  surfaces: z.array(z.record(z.string(), z.unknown())).default([]),
  generated_from: z.record(z.string(), z.unknown()).default({}),
  confidence: z.number(),
});

const ChartGrammarPackageSchema = z.object({
  charts: z.array(z.record(z.string(), z.unknown())).default([]),
  generated_from: z.record(z.string(), z.unknown()).default({}),
});

const InsightRankingPackageSchema = z.object({
  ranked: z.array(z.record(z.string(), z.unknown())).default([]),
  generated_from: z.record(z.string(), z.unknown()).default({}),
  scoring_version: z.string(),
});

const EntityResolutionRunResultSchema = z.object({
  plans: z.array(z.record(z.string(), z.unknown())).default([]),
  executions: z.array(z.record(z.string(), z.unknown())).default([]),
  generated_from: z.record(z.string(), z.unknown()).default({}),
});

const LineagePackageSchema = z.object({
  runs: z.array(z.record(z.string(), z.unknown())).default([]),
  datasets: z.array(z.record(z.string(), z.unknown())).default([]),
  generated_from: z.record(z.string(), z.unknown()).default({}),
});

const KnowledgeGraphMaterializationSchema = z.object({
  status: z.enum(['completed', 'failed']),
  backend: z.literal('kuzu'),
  graph_path: z.string(),
  node_count: z.number().default(0),
  edge_count: z.number().default(0),
  query_examples: z.array(z.string()).default([]),
  error: z.string().nullable().optional(),
});

const ActionTypeSchema = z.enum(['email_draft', 'export_list', 'save_cohort']);
const ActionStatusSchema = z.enum(['proposed', 'prepared', 'completed', 'dismissed']);

const ActionRecordSchema = z.object({
  id: z.string(),
  organization_id: z.string(),
  artifact_id: z.string().nullable().optional(),
  run_id: z.string().nullable().optional(),
  action_key: z.string(),
  action_type: ActionTypeSchema,
  status: ActionStatusSchema,
  title: z.string(),
  summary: z.string(),
  why: z.string(),
  source_refs: z.record(z.string(), z.unknown()).default({}),
  payload: z.record(z.string(), z.unknown()).default({}),
  prepared_payload: z.record(z.string(), z.unknown()).default({}),
  prepared_at: z.string().nullable().optional(),
  completed_at: z.string().nullable().optional(),
  dismissed_at: z.string().nullable().optional(),
  created_at: z.string(),
  updated_at: z.string(),
});

const ActionPlaneRunResultSchema = z.object({
  organization_id: z.string(),
  run_id: z.string(),
  actions: z.array(ActionRecordSchema).default([]),
  created_count: z.number(),
  updated_count: z.number(),
  skipped_count: z.number(),
});

const ActionListSchema = z.object({
  actions: z.array(ActionRecordSchema).default([]),
});

const SavedCohortRecordSchema = z.object({
  id: z.string(),
  organization_id: z.string(),
  action_id: z.string().nullable().optional(),
  cohort_key: z.string(),
  name: z.string(),
  description: z.string(),
  audience: z.record(z.string(), z.unknown()).default({}),
  rows: z.array(z.record(z.string(), z.unknown())).default([]),
  source_refs: z.record(z.string(), z.unknown()).default({}),
  created_at: z.string(),
  updated_at: z.string(),
});

const SavedCohortListSchema = z.object({
  cohorts: z.array(SavedCohortRecordSchema).default([]),
});

const OperatingRunResultWithArtifactsSchema = OperatingRunResultSchema.extend({
  artifacts: ArtifactPlaneRunResultSchema.nullable().optional(),
  action_plane: ActionPlaneRunResultSchema.nullable().optional(),
});

export class Gateway {
  private readonly transport: Transport;

  constructor(config: GatewayConfig) {
    this.transport = config.transport;
  }

  readonly auth = {
    requestMagicLink: async (req: { email: string }): Promise<{ ok: boolean }> => {
      const resp = await this.transport.request(
        { method: 'POST', path: '/api/v1/auth/magic-link', body: req },
        z.object({ ok: z.boolean().optional() }),
      );
      return { ok: resp.data.ok ?? true };
    },

    verifyMagicLink: async (req: { email: string; token: string }): Promise<AuthSession> =>
      (
        await this.transport.request(
          { method: 'POST', path: '/api/v1/auth/magic-link/verify', body: req },
          AuthSessionSchema,
        )
      ).data,

    me: async (): Promise<MeResponse> =>
      (
        await this.transport.request(
          { method: 'GET', path: '/api/v1/auth/me' },
          MeSchema,
        )
      ).data,

    signOut: async (): Promise<void> => {
      await this.transport.request(
        { method: 'POST', path: '/api/v1/auth/logout' },
        VoidSchema,
      );
    },
  };

  readonly connectors = {
    list: async (): Promise<ConnectorInfo[]> => {
      const resp = await this.transport.request(
        { method: 'GET', path: '/api/v1/connectors' },
        z.object({
          connectors: z.array(
            z.object({
              kind: z.string(),
              display_name: z.string(),
              description: z.string(),
              auth_method: z.string(),
              capabilities: z.array(z.string()),
            }),
          ),
        }),
      );
      return resp.data.connectors;
    },

    start: async (
      kind: string,
      body?: { shop_domain?: string },
    ): Promise<{ authorize_url: string }> =>
      (
        await this.transport.request(
          { method: 'POST', path: `/api/v1/connectors/${kind}/connect`, body },
          z.object({ authorize_url: z.string() }),
        )
      ).data,
  };

  readonly data = {
    listSources: async (): Promise<DataSourceInfo[]> =>
      (
        await this.transport.request(
          { method: 'GET', path: '/api/v1/data-sources' },
          z.object({
            data_sources: z.array(
              z.object({
                id: z.string(),
                kind: z.string(),
                name: z.string(),
                status: z.string(),
                discovered_schema: z.record(z.string(), z.unknown()).nullable().optional(),
                last_synced_at: z.string().nullable().optional(),
                last_error: z.string().nullable().optional(),
                created_at: z.string(),
              }),
            ),
          }),
        )
      ).data.data_sources,

    listConnectionResources: async (connectionId: string): Promise<{ resources: AvailableResource[] }> =>
      (
        await this.transport.request(
          { method: 'GET', path: `/api/v1/connections/${connectionId}/resources` },
          z.object({
            connection: z.record(z.string(), z.unknown()),
            resources: z.array(
              z.object({
                external_id: z.string(),
                name: z.string(),
                metadata: z.record(z.string(), z.unknown()).default({}),
              }),
            ),
          }),
        )
      ).data,

    createSources: async (connectionId: string, resources: AvailableResource[]): Promise<DataSourceInfo[]> =>
      (
        await this.transport.request(
          {
            method: 'POST',
            path: `/api/v1/connections/${connectionId}/sources`,
            body: { resources },
          },
          z.object({
            data_sources: z.array(
              z.object({
                id: z.string(),
                kind: z.string(),
                name: z.string(),
                status: z.string(),
                discovered_schema: z.record(z.string(), z.unknown()).nullable().optional(),
                last_synced_at: z.string().nullable().optional(),
                last_error: z.string().nullable().optional(),
                created_at: z.string(),
              }),
            ),
          }),
        )
      ).data.data_sources,
  };

  readonly operating = {
    start: async (body: { mode: 'scan' | 'ask'; question?: string }): Promise<RunAccepted> =>
      (
        await this.transport.request(
          { method: 'POST', path: '/api/v1/operating/runs', body },
          RunAcceptedSchema,
        )
      ).data,

    get: async (runId: string): Promise<RunState> =>
      (
        await this.transport.request(
          { method: 'GET', path: `/api/v1/operating/runs/${runId}` },
          RunStateSchema,
        )
      ).data,

    result: async (runId: string): Promise<OperatingRunResult> =>
      (
        await this.transport.request(
          { method: 'GET', path: `/api/v1/operating/runs/${runId}/result` },
          OperatingRunResultWithArtifactsSchema,
        )
      ).data,

    eventsPath: (runId: string): string => `/api/v1/operating/runs/${runId}/events`,
  };

  readonly artifacts = {
    list: async (query?: {
      kind?: ArtifactKind;
      status?: ArtifactStatus;
      include_terminal?: boolean;
      limit?: number;
    }): Promise<ArtifactRecord[]> =>
      (
        await this.transport.request(
          { method: 'GET', path: '/api/v1/artifacts', query },
          ArtifactListSchema,
        )
      ).data.artifacts,

    brief: async (): Promise<ArtifactRecord> =>
      (
        await this.transport.request(
          { method: 'GET', path: '/api/v1/artifacts/brief' },
          ArtifactRecordSchema,
        )
      ).data,

    businessView: async (): Promise<ArtifactRecord> =>
      (
        await this.transport.request(
          { method: 'GET', path: '/api/v1/artifacts/business-view' },
          ArtifactRecordSchema,
        )
      ).data,

    businessSurfaces: async (): Promise<ArtifactRecord> =>
      (
        await this.transport.request(
          { method: 'GET', path: '/api/v1/artifacts/business-surfaces' },
          ArtifactRecordSchema,
        )
      ).data,

    semanticLayer: async (): Promise<ArtifactRecord> =>
      (
        await this.transport.request(
          { method: 'GET', path: '/api/v1/artifacts/semantic-layer' },
          ArtifactRecordSchema,
        )
      ).data,

    chartGrammar: async (): Promise<ArtifactRecord> =>
      (
        await this.transport.request(
          { method: 'GET', path: '/api/v1/artifacts/chart-grammar' },
          ArtifactRecordSchema,
        )
      ).data,

    insightRanking: async (): Promise<ArtifactRecord> =>
      (
        await this.transport.request(
          { method: 'GET', path: '/api/v1/artifacts/insight-ranking' },
          ArtifactRecordSchema,
        )
      ).data,

    entityResolution: async (): Promise<ArtifactRecord> =>
      (
        await this.transport.request(
          { method: 'GET', path: '/api/v1/artifacts/entity-resolution' },
          ArtifactRecordSchema,
        )
      ).data,

    knowledgeGraph: async (): Promise<ArtifactRecord> =>
      (
        await this.transport.request(
          { method: 'GET', path: '/api/v1/artifacts/knowledge-graph' },
          ArtifactRecordSchema,
        )
      ).data,

    lineage: async (): Promise<ArtifactRecord> =>
      (
        await this.transport.request(
          { method: 'GET', path: '/api/v1/artifacts/lineage' },
          ArtifactRecordSchema,
        )
      ).data,

    inbox: async (limit?: number): Promise<ArtifactRecord[]> =>
      (
        await this.transport.request(
          { method: 'GET', path: '/api/v1/artifacts/inbox', query: { limit } },
          ArtifactListSchema,
        )
      ).data.artifacts,

    forRun: async (runId: string): Promise<ArtifactRecord[]> =>
      (
        await this.transport.request(
          { method: 'GET', path: `/api/v1/artifacts/runs/${runId}` },
          ArtifactListSchema,
        )
      ).data.artifacts,

    updateStatus: async (
      artifactId: string,
      body: { status: ArtifactStatus; snoozed_until?: string | null },
    ): Promise<ArtifactRecord> =>
      (
        await this.transport.request(
          { method: 'PATCH', path: `/api/v1/artifacts/${artifactId}/status`, body },
          ArtifactRecordSchema,
        )
      ).data,
  };

  readonly actions = {
    list: async (query?: {
      action_type?: ActionType;
      status?: ActionStatus;
      include_terminal?: boolean;
      limit?: number;
    }): Promise<ActionRecord[]> =>
      (
        await this.transport.request(
          { method: 'GET', path: '/api/v1/actions', query },
          ActionListSchema,
        )
      ).data.actions,

    cohorts: async (limit?: number): Promise<SavedCohortRecord[]> =>
      (
        await this.transport.request(
          { method: 'GET', path: '/api/v1/actions/cohorts', query: { limit } },
          SavedCohortListSchema,
        )
      ).data.cohorts,

    get: async (actionId: string): Promise<ActionRecord> =>
      (
        await this.transport.request(
          { method: 'GET', path: `/api/v1/actions/${actionId}` },
          ActionRecordSchema,
        )
      ).data,

    prepare: async (
      actionId: string,
      body?: { options?: Record<string, unknown> },
    ): Promise<ActionRecord> =>
      (
        await this.transport.request(
          { method: 'POST', path: `/api/v1/actions/${actionId}/prepare`, body: body ?? {} },
          ActionRecordSchema,
        )
      ).data,

    complete: async (actionId: string): Promise<ActionRecord> =>
      (
        await this.transport.request(
          { method: 'POST', path: `/api/v1/actions/${actionId}/complete` },
          ActionRecordSchema,
        )
      ).data,

    dismiss: async (actionId: string): Promise<ActionRecord> =>
      (
        await this.transport.request(
          { method: 'POST', path: `/api/v1/actions/${actionId}/dismiss` },
          ActionRecordSchema,
        )
      ).data,
  };

  readonly system = {
    health: async () => {
      const Schema = z.object({ healthy: z.boolean().optional(), ok: z.boolean().optional() });
      return (
        await this.transport.request(
          { method: 'GET', path: '/api/v1/health' },
          Schema,
        )
      ).data;
    },
  };
}

export function createGateway(config: GatewayConfig): Gateway {
  return new Gateway(config);
}
