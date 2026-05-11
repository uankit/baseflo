import { z } from 'zod';
import { SlugSchema, TimestampSchema, UUIDSchema } from './common.js';

export const DeploymentModeSchema = z.enum(['hosted', 'byo_db', 'self_host', 'local_dev']);
export type DeploymentMode = z.infer<typeof DeploymentModeSchema>;

export const ProjectStatusSchema = z.enum([
  'ready',
  'generating',
  'needs_clarification',
  'failed',
  'no_connectors',
]);
export type ProjectStatus = z.infer<typeof ProjectStatusSchema>;

export const ProjectSummarySchema = z.object({
  id: UUIDSchema,
  organizationId: UUIDSchema,
  slug: SlugSchema,
  name: z.string(),
  description: z.string().nullable(),
  deploymentMode: DeploymentModeSchema,
  currentVersionId: UUIDSchema.nullable(),
  createdAt: TimestampSchema,
  updatedAt: TimestampSchema,
  status: ProjectStatusSchema,
  currency: z.string().length(3).default('USD'),
});
export type ProjectSummary = z.infer<typeof ProjectSummarySchema>;

export const ProjectDetailSchema = ProjectSummarySchema.extend({
  connectorCount: z.number().int().nonnegative().default(0),
  versionCount: z.number().int().positive().default(1),
});
export type ProjectDetail = z.infer<typeof ProjectDetailSchema>;

export const CreateProjectRequestSchema = z.object({
  name: z.string().min(1).max(80),
  slug: SlugSchema.optional(),
  description: z.string().max(280).nullable().optional(),
  deploymentMode: DeploymentModeSchema.default('hosted'),
});
export type CreateProjectRequest = z.infer<typeof CreateProjectRequestSchema>;

export const StartSagaRequestSchema = z.object({
  prompt: z.string().min(8),
  parentVersionId: UUIDSchema.nullable().optional(),
});
export type StartSagaRequest = z.infer<typeof StartSagaRequestSchema>;

export const StartSagaResponseSchema = z.object({
  conversationId: UUIDSchema,
  jobId: UUIDSchema,
});
export type StartSagaResponse = z.infer<typeof StartSagaResponseSchema>;
