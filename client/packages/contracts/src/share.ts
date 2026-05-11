import { z } from 'zod';
import { TimestampSchema, URLSchema, UUIDSchema } from './common.js';

export const SharePermissionSchema = z.enum([
  'overview_only',
  'overview_kpis',
  'full_read_only',
]);
export type SharePermission = z.infer<typeof SharePermissionSchema>;

export const ShareLinkSchema = z.object({
  id: UUIDSchema,
  projectId: UUIDSchema,
  versionId: UUIDSchema,
  token: z.string(),
  url: URLSchema,
  permissions: SharePermissionSchema,
  hasPassword: z.boolean(),
  expiresAt: TimestampSchema.nullable(),
  notes: z.string().nullable(),
  createdAt: TimestampSchema,
  revokedAt: TimestampSchema.nullable(),
  createdBy: z.object({ id: UUIDSchema, displayName: z.string().nullable() }),
});
export type ShareLink = z.infer<typeof ShareLinkSchema>;

export const CreateShareLinkRequestSchema = z.object({
  versionId: UUIDSchema,
  permissions: SharePermissionSchema.default('full_read_only'),
  expiresInHours: z.number().int().positive().nullable().default(168),
  password: z.string().min(4).optional(),
  notes: z.string().max(280).optional(),
});
export type CreateShareLinkRequest = z.infer<typeof CreateShareLinkRequestSchema>;

/** Public share-page payload. Server has redacted PII, traces, audit, internal validation. */
export const PublicShareSchema = z.object({
  projectName: z.string(),
  businessSummary: z.string(),
  kpis: z.array(
    z.object({
      label: z.string(),
      value: z.string(),
      caption: z.string().nullable(),
    }),
  ),
  topAssumptions: z.array(z.string()),
  topRisks: z.array(z.string()),
  generatedAt: TimestampSchema,
  permissions: SharePermissionSchema,
  ownerOrgName: z.string(),
  ownerOrgPlan: z.string(),
});
export type PublicShare = z.infer<typeof PublicShareSchema>;
