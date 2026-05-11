import { z } from 'zod';
import { TimestampSchema, UUIDSchema } from './common.js';

export const AuditActorTypeSchema = z.enum(['user', 'agent', 'system', 'api_key']);
export type AuditActorType = z.infer<typeof AuditActorTypeSchema>;

export const AuditActionSchema = z.enum([
  'read',
  'write',
  'delete',
  'export',
  'connector.connect',
  'connector.revoke',
  'auth.login',
  'auth.logout',
  'pii.reveal',
  'refinement.apply',
  'share.create',
  'share.revoke',
  'invite.send',
  'invite.accept',
]);
export type AuditAction = z.infer<typeof AuditActionSchema>;

export const AuditEventSchema = z.object({
  id: UUIDSchema,
  organizationId: UUIDSchema,
  actorType: AuditActorTypeSchema,
  actorId: z.string(),
  actorLabel: z.string(),
  action: AuditActionSchema,
  targetKind: z.string(),
  targetId: z.string(),
  targetLabel: z.string(),
  ipAddress: z.string().nullable(),
  createdAt: TimestampSchema,
});
export type AuditEvent = z.infer<typeof AuditEventSchema>;

export const AuditPageSchema = z.object({
  events: z.array(AuditEventSchema),
  nextCursor: z.string().nullable(),
});
export type AuditPage = z.infer<typeof AuditPageSchema>;

export const AuditFilterSchema = z.object({
  cursor: z.string().nullable().optional(),
  action: AuditActionSchema.optional(),
  actorType: AuditActorTypeSchema.optional(),
  fromDate: TimestampSchema.optional(),
  toDate: TimestampSchema.optional(),
  projectId: UUIDSchema.optional(),
});
export type AuditFilter = z.infer<typeof AuditFilterSchema>;
