import { z } from 'zod';
import type { ArtifactRecord } from '@baseflo/api-client';

export class ContractMismatchError extends Error {
  constructor(
    message: string,
    readonly details?: unknown,
  ) {
    super(message);
    this.name = 'ContractMismatchError';
  }
}

const RecordSchema = z.record(z.string(), z.unknown());

export const BusinessViewMetricSchema = z.strictObject({
  label: z.string(),
  value: z.string(),
  unit: z.string().nullable(),
  why: z.string(),
  evidence_refs: z.array(z.string()),
});

export const BusinessViewDrilldownSchema = z.strictObject({
  drilldown_id: z.string(),
  label: z.string(),
  entity: z.string().nullable(),
  question: z.string(),
  graph_refs: z.array(z.string()),
  field_refs: z.array(z.string()),
  artifact_refs: z.array(z.string()),
});

export const BusinessViewSectionSchema = z.strictObject({
  section_id: z.string(),
  kind: z.string(),
  title: z.string(),
  description: z.string(),
  why_built: z.string(),
  confidence: z.number(),
  tags: z.array(z.string()),
  metrics: z.array(BusinessViewMetricSchema),
  source_asset_ids: z.array(z.string()),
  field_refs: z.array(z.string()),
  graph_refs: z.array(z.string()),
  insight_refs: z.array(z.string()),
  table_refs: z.array(z.string()),
  chart_refs: z.array(z.string()),
  action_refs: z.array(z.string()),
  suggested_questions: z.array(z.string()),
  drilldowns: z.array(BusinessViewDrilldownSchema),
});

export const BusinessEntityViewSchema = z.strictObject({
  entity: z.string(),
  plural: z.string(),
  description: z.string(),
  why_available: z.string(),
  source_asset_ids: z.array(z.string()),
  field_refs: z.array(z.string()),
  graph_refs: z.array(z.string()),
  suggested_questions: z.array(z.string()),
});

export const BusinessViewPackageSchema = z.strictObject({
  headline: z.string(),
  summary: z.string(),
  why: z.string(),
  sections: z.array(BusinessViewSectionSchema),
  entity_views: z.array(BusinessEntityViewSchema),
  generated_from: RecordSchema,
  confidence: z.number(),
});

export const SurfaceDimensionSchema = z.strictObject({
  dimension_id: z.string(),
  label: z.string(),
  kind: z.string(),
  field_id: z.string(),
  asset_id: z.string(),
  entity_hint: z.string().nullable(),
  why: z.string(),
  confidence: z.number(),
});

export const SurfaceMeasureSchema = z.strictObject({
  measure_id: z.string(),
  label: z.string(),
  kind: z.string(),
  field_id: z.string(),
  asset_id: z.string(),
  default_aggregate: z.enum(['sum', 'avg', 'count', 'min', 'max']),
  unit: z.string().nullable(),
  why: z.string(),
  confidence: z.number(),
});

export const CandidateViewSchema = z.strictObject({
  view_id: z.string(),
  surface_id: z.string(),
  title: z.string(),
  question: z.string(),
  algorithm: z.string(),
  dimensions: z.array(z.string()),
  measures: z.array(z.string()),
  expected_output: z.string(),
  priority: z.number(),
  why: z.string(),
  execution_hint: RecordSchema,
});

export const SurfaceCohortSchema = z.strictObject({
  cohort_id: z.string(),
  surface_id: z.string(),
  label: z.string(),
  entity: z.string().nullable(),
  description: z.string(),
  filter_refs: z.array(z.string()),
  measure_refs: z.array(z.string()),
  dimension_refs: z.array(z.string()),
  size_hint: z.string().nullable(),
  value_hint: z.string().nullable(),
  actionability: z.number(),
  why: z.string(),
});

export const BulkActionPackSchema = z.strictObject({
  action_pack_id: z.string(),
  surface_id: z.string(),
  title: z.string(),
  action_type: z.enum(['email_draft', 'export_list', 'save_cohort']),
  execution_mode: z.literal('prepare_for_user'),
  target_entity: z.string().nullable(),
  cohort_refs: z.array(z.string()),
  evidence_refs: z.array(z.string()),
  payload_template: RecordSchema,
  why: z.string(),
  approval_required: z.string(),
  risk: z.string(),
  priority: z.number(),
});

export const BusinessSurfaceSchema = z.strictObject({
  surface_id: z.string(),
  kind: z.string(),
  title: z.string(),
  description: z.string(),
  entity: z.string().nullable(),
  why_built: z.string(),
  source_asset_ids: z.array(z.string()),
  field_refs: z.array(z.string()),
  graph_refs: z.array(z.string()),
  dimensions: z.array(SurfaceDimensionSchema),
  measures: z.array(SurfaceMeasureSchema),
  candidate_views: z.array(CandidateViewSchema),
  cohorts: z.array(SurfaceCohortSchema),
  action_packs: z.array(BulkActionPackSchema),
  confidence: z.number(),
});

export const BusinessSurfacePackageSchema = z.strictObject({
  headline: z.string(),
  summary: z.string(),
  why: z.string(),
  algorithms: z.array(z.string()),
  surfaces: z.array(BusinessSurfaceSchema),
  insight_graph: RecordSchema,
  generated_from: RecordSchema,
  confidence: z.number(),
});

export const RankedInsightSchema = z.strictObject({
  rank: z.number(),
  item_id: z.string(),
  item_kind: z.string(),
  title: z.string(),
  score: z.number(),
  score_breakdown: RecordSchema,
  why_ranked: z.string(),
  refs: RecordSchema,
  tags: z.array(z.string()),
});

export const InsightRankingPackageSchema = z.strictObject({
  ranked: z.array(RankedInsightSchema),
  generated_from: RecordSchema,
  scoring_version: z.string(),
});

export const BriefPackageSchema = z.strictObject({
  agent: z.literal('BriefSynthesizer'),
  headline: z.string(),
  body: z.string().optional(),
  summary_points: z.array(z.string()),
  urgent_artifact_ids: z.array(z.string()),
  why: z.string(),
});

export const StructureTransformationSchema = z.strictObject({
  operation: z.enum([
    'drop_empty_rows',
    'promote_header',
    'split_region',
    'unnest_json',
    'pivot_to_rows',
    'merge_columns',
    'parse_document',
    'normalize_values',
  ]),
  why: z.string(),
  parameters: RecordSchema,
});

export const StructuredFieldProposalSchema = z.strictObject({
  field_key: z.string(),
  label: z.string(),
  source_fields: z.array(z.string()),
  baseflo_type: z.enum([
    'null',
    'string',
    'integer',
    'number',
    'boolean',
    'date',
    'datetime',
    'email',
    'phone',
    'money',
    'id',
    'json',
    'binary',
  ]),
  semantic_hint: z.string().nullable(),
  nullable: z.boolean(),
  confidence: z.number(),
  evidence: RecordSchema,
});

export const StructuredAssetProposalSchema = z.strictObject({
  asset_key: z.string(),
  label: z.string(),
  asset_id: z.string().nullable(),
  extraction_mode: z.enum(['deterministic', 'agent_proposed', 'human_confirmed']),
  structure_type: z.enum([
    'table',
    'event_stream',
    'entity_collection',
    'document_collection',
    'metric_series',
    'unknown',
  ]),
  source_locator: RecordSchema,
  grain: z.string(),
  primary_time_field: z.string().nullable(),
  primary_entity_fields: z.array(z.string()),
  fields: z.array(StructuredFieldProposalSchema),
  transformations: z.array(StructureTransformationSchema),
  rejected_source_fields: z.array(z.string()),
  confidence: z.number(),
  requires_human_confirmation: z.boolean(),
  why: z.string(),
});

export const StructureRoutingDecisionSchema = z.strictObject({
  asset_id: z.string(),
  asset_key: z.string(),
  label: z.string(),
  route: z.enum(['deterministic_ready', 'agentic_structure', 'human_confirmation']),
  reason: z.string(),
  confidence: z.number(),
});

export const WorkbenchViewSchema = z.strictObject({
  view_id: z.string(),
  title: z.string(),
  output_kind: z.enum(['table', 'metric', 'bar', 'line', 'map', 'cohort']),
  question: z.string(),
  asset_refs: z.array(z.string()),
  dimension_field_refs: z.array(z.string()),
  measure_field_refs: z.array(z.string()),
  why: z.string(),
  confidence: z.number(),
});

export const WorkbenchActionSchema = z.strictObject({
  action_id: z.string(),
  title: z.string(),
  action_type: z.enum([
    'ask',
    'export_table',
    'save_cohort',
    'bulk_message',
    'send_reminder',
    'prepare_report',
  ]),
  target_entity: z.string().nullable(),
  payload_template: RecordSchema,
  approval_required: z.string(),
  why: z.string(),
  confidence: z.number(),
});

export const GeneratedWorkbenchSchema = z.strictObject({
  workbench_id: z.string(),
  title: z.string(),
  kind: z.enum([
    'sales',
    'receivables',
    'inventory',
    'customers_parties',
    'products_items',
    'expenses',
    'profit_loss',
    'operations',
    'source_health',
  ]),
  description: z.string(),
  asset_refs: z.array(z.string()),
  field_refs: z.array(z.string()),
  views: z.array(WorkbenchViewSchema),
  actions: z.array(WorkbenchActionSchema),
  confidence: z.number(),
  why: z.string(),
});

export const SourceStructureAgentOutputSchema = z.strictObject({
  agent: z.literal('SourceStructureAgent'),
  source_kind: z.string(),
  extraction_mode: z.literal('agent_proposed'),
  assets: z.array(StructuredAssetProposalSchema),
  rejected_regions: z.array(
    z.strictObject({
      locator: RecordSchema,
      reason: z.string(),
      confidence: z.number(),
    }),
  ),
  questions_for_user: z.array(z.string()),
  confidence: z.number(),
});

export const SourceStructurePackageSchema = z.strictObject({
  assets: z.array(StructuredAssetProposalSchema),
  workbenches: z.array(GeneratedWorkbenchSchema),
  routing: z.array(StructureRoutingDecisionSchema),
  agentic_outputs: z.array(SourceStructureAgentOutputSchema),
  agentic_status: z.enum(['not_needed', 'ran', 'unavailable', 'failed']),
  deterministic_policy: z.array(z.string()),
  generated_from: RecordSchema,
  confidence: z.number(),
});

export const LineagePackageSchema = z.strictObject({
  runs: z.array(RecordSchema),
  datasets: z.array(RecordSchema),
  generated_from: RecordSchema,
});

export const SemanticLayerPackageSchema = z.strictObject({
  entities: z.array(RecordSchema),
  dimensions: z.array(RecordSchema),
  measures: z.array(RecordSchema),
  metrics: z.array(RecordSchema),
  surfaces: z.array(RecordSchema),
  generated_from: RecordSchema,
  confidence: z.number(),
});

export const KnowledgeGraphPackageSchema = z.strictObject({
  status: z.enum(['completed', 'failed']),
  backend: z.literal('kuzu'),
  graph_path: z.string(),
  node_count: z.number(),
  edge_count: z.number(),
  query_examples: z.array(z.string()),
  error: z.string().nullable(),
});

export const ChartGrammarPackageSchema = z.strictObject({
  charts: z.array(RecordSchema),
  generated_from: RecordSchema,
});

export const EntityResolutionPackageSchema = z.strictObject({
  plans: z.array(RecordSchema),
  executions: z.array(RecordSchema),
  generated_from: RecordSchema,
});

// ---------------------------------------------------------------------------
// Entity Register
// ---------------------------------------------------------------------------

export const EntityRegisterColumnSchema = z.strictObject({
  key: z.string(),
  label: z.string(),
  role: z.string(),
  unit: z.string().nullable(),
});

export const EntityRegisterRowSchema = z.strictObject({
  cluster_id: z.string(),
  display_name: z.string(),
  entity_type: z.string(),
  fields: RecordSchema,
  cohort_flags: z.array(z.string()),
  decision_tags: z.array(z.string()),
  source_names: z.array(z.string()),
  source_count: z.number(),
  member_record_ids: z.array(z.string()),
});

export const EntityRegisterCohortSummarySchema = z.strictObject({
  cohort_id: z.string(),
  label: z.string(),
  description: z.string(),
  size_hint: z.string().nullable(),
  value_hint: z.string().nullable(),
  actionability: z.number(),
  why: z.string(),
});

export const EntityRegisterTabSchema = z.strictObject({
  entity_type: z.string(),
  label: z.string(),
  description: z.string(),
  total_count: z.number(),
  rows: z.array(EntityRegisterRowSchema),
  columns: z.array(EntityRegisterColumnSchema),
  cohort_summaries: z.array(EntityRegisterCohortSummarySchema),
  available_action_types: z.array(z.string()),
});

export const EntityRegisterPackageSchema = z.strictObject({
  business_kind: z.string(),
  tabs: z.array(EntityRegisterTabSchema),
  total_row_count: z.number(),
  source_count: z.number(),
  cross_source_cluster_count: z.number(),
  resolved_entity_count: z.number(),
  generated_from: RecordSchema,
});

export type EntityRegisterPackage = z.infer<typeof EntityRegisterPackageSchema>;
export type SourceStructurePackage = z.infer<typeof SourceStructurePackageSchema>;
export type GeneratedWorkbench = z.infer<typeof GeneratedWorkbenchSchema>;
export type StructuredAssetProposal = z.infer<typeof StructuredAssetProposalSchema>;
export type EntityRegisterTab = z.infer<typeof EntityRegisterTabSchema>;
export type EntityRegisterRow = z.infer<typeof EntityRegisterRowSchema>;
export type EntityRegisterColumn = z.infer<typeof EntityRegisterColumnSchema>;
export type EntityRegisterCohortSummary = z.infer<typeof EntityRegisterCohortSummarySchema>;
export type BusinessViewPackage = z.infer<typeof BusinessViewPackageSchema>;
export type BusinessViewSection = z.infer<typeof BusinessViewSectionSchema>;
export type BusinessViewMetric = z.infer<typeof BusinessViewMetricSchema>;
export type BusinessViewDrilldown = z.infer<typeof BusinessViewDrilldownSchema>;
export type BusinessEntityView = z.infer<typeof BusinessEntityViewSchema>;
export type BusinessSurfacePackage = z.infer<typeof BusinessSurfacePackageSchema>;
export type BusinessSurface = z.infer<typeof BusinessSurfaceSchema>;
export type CandidateView = z.infer<typeof CandidateViewSchema>;
export type SurfaceCohort = z.infer<typeof SurfaceCohortSchema>;
export type BulkActionPack = z.infer<typeof BulkActionPackSchema>;
export type RankedInsight = z.infer<typeof RankedInsightSchema>;
export type BriefPackage = z.infer<typeof BriefPackageSchema>;
export type EntityResolutionPackage = z.infer<typeof EntityResolutionPackageSchema>;

export function parseArtifactPayload<T>(
  artifact: ArtifactRecord,
  payloadKey: string,
  schema: z.ZodType<T>,
): T {
  const payload = artifact.payload[payloadKey];
  const parsed = schema.safeParse(payload);
  if (!parsed.success) {
    throw new ContractMismatchError(
      `${artifact.kind} artifact payload is missing a valid ${payloadKey} package.`,
      parsed.error.flatten(),
    );
  }
  return parsed.data;
}

export function safeParseArtifactPayload<T>(
  artifact: ArtifactRecord | null | undefined,
  payloadKey: string,
  schema: z.ZodType<T>,
): { data: T | null; error: ContractMismatchError | null } {
  if (!artifact) return { data: null, error: null };
  try {
    return { data: parseArtifactPayload(artifact, payloadKey, schema), error: null };
  } catch (error) {
    if (error instanceof ContractMismatchError) {
      return { data: null, error };
    }
    throw error;
  }
}

export function parsePackage<T>(
  value: unknown,
  label: string,
  schema: z.ZodType<T>,
): T {
  const parsed = schema.safeParse(value);
  if (!parsed.success) {
    throw new ContractMismatchError(`${label} did not match the UI contract.`, parsed.error.flatten());
  }
  return parsed.data;
}
