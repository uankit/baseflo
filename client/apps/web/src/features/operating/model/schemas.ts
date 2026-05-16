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
  summary_points: z.array(z.string()),
  urgent_artifact_ids: z.array(z.string()),
  why: z.string(),
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
