import { z } from 'zod';
import { UUIDSchema } from './common.js';

export const FunnelStepSchema = z.object({
  id: z.string(),
  label: z.string(),
  count: z.number().int().nonnegative(),
  conversionRate: z.number().min(0).max(1).nullable(),
});
export type FunnelStep = z.infer<typeof FunnelStepSchema>;

export const FunnelSchema = z.object({
  id: z.string(),
  name: z.string(),
  steps: z.array(FunnelStepSchema),
});
export type Funnel = z.infer<typeof FunnelSchema>;

export const CohortRowSchema = z.object({
  cohortLabel: z.string(),
  size: z.number().int().nonnegative(),
  retention: z.array(z.number().min(0).max(1)),
});
export type CohortRow = z.infer<typeof CohortRowSchema>;

export const CohortGridSchema = z.object({
  id: z.string(),
  name: z.string(),
  bucketLabels: z.array(z.string()),
  rows: z.array(CohortRowSchema),
});
export type CohortGrid = z.infer<typeof CohortGridSchema>;

export const TopNRowSchema = z.object({
  label: z.string(),
  value: z.number(),
  unit: z.string().nullable(),
});
export type TopNRow = z.infer<typeof TopNRowSchema>;

export const TopNListSchema = z.object({
  id: z.string(),
  name: z.string(),
  rows: z.array(TopNRowSchema),
});
export type TopNList = z.infer<typeof TopNListSchema>;

export const GeoBucketSchema = z.object({
  region: z.string(),
  count: z.number().int().nonnegative(),
});
export type GeoBucket = z.infer<typeof GeoBucketSchema>;

export const LapsingRowSchema = z.object({
  entityId: z.string(),
  label: z.string(),
  lastActiveAt: z.string(),
  reason: z.string(),
});
export type LapsingRow = z.infer<typeof LapsingRowSchema>;

export const AnalyticsSummarySchema = z.object({
  versionId: UUIDSchema,
  funnels: z.array(FunnelSchema),
  cohorts: z.array(CohortGridSchema),
  topN: z.array(TopNListSchema),
  geo: z.array(GeoBucketSchema),
  lapsing: z.array(LapsingRowSchema),
});
export type AnalyticsSummary = z.infer<typeof AnalyticsSummarySchema>;
