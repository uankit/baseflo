import { z } from 'zod';
import { TimestampSchema, URLSchema, UUIDSchema } from './common.js';

export const ExportFormatSchema = z.enum(['csv', 'sql', 'json', 'full']);
export type ExportFormat = z.infer<typeof ExportFormatSchema>;

export const ExportStatusSchema = z.enum(['queued', 'running', 'ready', 'expired', 'failed']);
export type ExportStatus = z.infer<typeof ExportStatusSchema>;

export const ExportSchema = z.object({
  id: UUIDSchema,
  projectId: UUIDSchema,
  versionId: UUIDSchema,
  format: ExportFormatSchema,
  status: ExportStatusSchema,
  fileUrl: URLSchema.nullable(),
  expiresAt: TimestampSchema.nullable(),
  includesPII: z.boolean().default(false),
  requestedBy: z.object({ id: UUIDSchema, displayName: z.string().nullable() }),
  createdAt: TimestampSchema,
  completedAt: TimestampSchema.nullable(),
});
export type ExportRecord = z.infer<typeof ExportSchema>;

export const RequestExportSchema = z.object({
  format: ExportFormatSchema,
  includePII: z.boolean().default(false),
});
export type RequestExport = z.infer<typeof RequestExportSchema>;
