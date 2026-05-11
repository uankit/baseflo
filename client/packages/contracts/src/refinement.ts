import { z } from 'zod';
import { TimestampSchema, UUIDSchema } from './common.js';

export const ChangeKindSchema = z.enum([
  'add_column',
  'remove_column',
  'rename_column',
  'add_table',
  'remove_table',
  'rename_table',
  'add_kpi',
  'modify_kpi',
  'remove_kpi',
  'change_relationship',
]);
export type ChangeKind = z.infer<typeof ChangeKindSchema>;

export const PlannedChangeSchema = z.object({
  kind: ChangeKindSchema,
  target: z.string(),
  description: z.string(),
  destructive: z.boolean().default(false),
});
export type PlannedChange = z.infer<typeof PlannedChangeSchema>;

export const ImpactSummarySchema = z.object({
  affectedTables: z.array(z.string()),
  affectedKPIs: z.array(z.string()),
  destructive: z.boolean().default(false),
  estimatedRowsImpacted: z.number().int().nonnegative().nullable(),
});
export type ImpactSummary = z.infer<typeof ImpactSummarySchema>;

export const RefinementProposalSchema = z.object({
  refinementId: UUIDSchema,
  parentVersionId: UUIDSchema,
  intentText: z.string(),
  changes: z.array(PlannedChangeSchema),
  impact: ImpactSummarySchema,
  status: z.enum(['proposed', 'applied', 'discarded', 'failed']),
  createdAt: TimestampSchema,
});
export type RefinementProposal = z.infer<typeof RefinementProposalSchema>;

export const RefinementApplyResponseSchema = z.object({
  newVersionId: UUIDSchema,
});
export type RefinementApplyResponse = z.infer<typeof RefinementApplyResponseSchema>;

export const RefinementHistoryItemSchema = z.object({
  id: UUIDSchema,
  intentText: z.string(),
  status: z.enum(['proposed', 'applied', 'discarded', 'failed']),
  parentVersionId: UUIDSchema,
  childVersionId: UUIDSchema.nullable(),
  createdAt: TimestampSchema,
  createdBy: z.object({ id: UUIDSchema, displayName: z.string().nullable() }),
});
export type RefinementHistoryItem = z.infer<typeof RefinementHistoryItemSchema>;

export const ProjectVersionSchema = z.object({
  id: UUIDSchema,
  projectId: UUIDSchema,
  parentVersionId: UUIDSchema.nullable(),
  versionNumber: z.number().int().nonnegative(),
  validationStatus: z.enum(['passed', 'warning', 'failed', 'pending']),
  createdAt: TimestampSchema,
  createdBy: z.object({ id: UUIDSchema, displayName: z.string().nullable() }).nullable(),
});
export type ProjectVersion = z.infer<typeof ProjectVersionSchema>;
