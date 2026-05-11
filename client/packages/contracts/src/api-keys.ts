import { z } from 'zod';
import { TimestampSchema, UUIDSchema } from './common.js';

export const ApiKeyScopeSchema = z.enum([
  'read:all',
  'write:all',
  'events:write',
  'refinements:propose',
]);
export type ApiKeyScope = z.infer<typeof ApiKeyScopeSchema>;

export const ApiKeySchema = z.object({
  id: UUIDSchema,
  organizationId: UUIDSchema,
  name: z.string(),
  prefix: z.string(),
  scopes: z.array(ApiKeyScopeSchema),
  lastUsedAt: TimestampSchema.nullable(),
  revokedAt: TimestampSchema.nullable(),
  createdAt: TimestampSchema,
  createdBy: z.object({ id: UUIDSchema, displayName: z.string().nullable() }),
});
export type ApiKey = z.infer<typeof ApiKeySchema>;

export const CreateApiKeyRequestSchema = z.object({
  name: z.string().min(1).max(64),
  scopes: z.array(ApiKeyScopeSchema).min(1),
});
export type CreateApiKeyRequest = z.infer<typeof CreateApiKeyRequestSchema>;

/** Server returns this once at creation; the secret cannot be retrieved again. */
export const CreateApiKeyResponseSchema = z.object({
  key: ApiKeySchema,
  secret: z.string(),
});
export type CreateApiKeyResponse = z.infer<typeof CreateApiKeyResponseSchema>;
