import { z } from 'zod';
import { EmailSchema, SlugSchema, TimestampSchema, UUIDSchema } from './common.js';
import { PlanSchema, RegionSchema, RoleSchema } from './auth.js';

export const OrgSchema = z.object({
  id: UUIDSchema,
  slug: SlugSchema,
  name: z.string(),
  plan: PlanSchema,
  region: RegionSchema,
  status: z.enum(['active', 'paused', 'cancelled']),
  createdAt: TimestampSchema,
});
export type Org = z.infer<typeof OrgSchema>;

export const CreateOrgRequestSchema = z.object({
  name: z.string().min(2).max(80),
  slug: SlugSchema.optional(),
  region: RegionSchema.default('us-east-1'),
});
export type CreateOrgRequest = z.infer<typeof CreateOrgRequestSchema>;

export const MembershipSchema = z.object({
  id: UUIDSchema,
  organizationId: UUIDSchema,
  userId: UUIDSchema,
  email: EmailSchema,
  displayName: z.string().nullable(),
  role: RoleSchema,
  invitedBy: UUIDSchema.nullable(),
  acceptedAt: TimestampSchema.nullable(),
  createdAt: TimestampSchema,
});
export type Membership = z.infer<typeof MembershipSchema>;

export const InviteRequestSchema = z.object({
  email: EmailSchema,
  role: RoleSchema,
});
export type InviteRequest = z.infer<typeof InviteRequestSchema>;
