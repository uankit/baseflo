import { z } from 'zod';
import { EmailSchema, SlugSchema, TimestampSchema, UUIDSchema } from './common.js';

export const RoleSchema = z.enum(['owner', 'admin', 'editor', 'viewer']);
export type Role = z.infer<typeof RoleSchema>;

export const PlanSchema = z.enum(['free', 'hobby', 'pro', 'business', 'enterprise']);
export type Plan = z.infer<typeof PlanSchema>;

export const RegionSchema = z.enum(['us-east-1', 'eu-west-1']);
export type Region = z.infer<typeof RegionSchema>;

export const OrgMembershipSchema = z.object({
  organizationId: UUIDSchema,
  organizationSlug: SlugSchema,
  organizationName: z.string(),
  role: RoleSchema,
  plan: PlanSchema,
  region: RegionSchema,
});
export type OrgMembership = z.infer<typeof OrgMembershipSchema>;

export const SessionUserSchema = z.object({
  id: UUIDSchema,
  email: EmailSchema,
  displayName: z.string().nullable(),
  emailVerifiedAt: TimestampSchema.nullable(),
});
export type SessionUser = z.infer<typeof SessionUserSchema>;

export const SessionSchema = z.object({
  user: SessionUserSchema,
  organizations: z.array(OrgMembershipSchema),
  activeOrgId: UUIDSchema.nullable(),
  expiresAt: TimestampSchema,
});
export type Session = z.infer<typeof SessionSchema>;

export const SignInRequestSchema = z.object({
  email: z.email({ message: 'Enter a valid email address.' }),
  password: z.string().min(1, 'Password required.').optional(),
});
export type SignInRequest = z.infer<typeof SignInRequestSchema>;

export const MagicLinkRequestSchema = z.object({
  email: z.email({ message: 'Enter a valid email address.' }),
});
export type MagicLinkRequest = z.infer<typeof MagicLinkRequestSchema>;

export const MagicLinkConsumeSchema = z.object({
  token: z.string().min(8),
});
export type MagicLinkConsume = z.infer<typeof MagicLinkConsumeSchema>;

export const OAuthProviderSchema = z.enum(['google', 'github', 'microsoft']);
export type OAuthProvider = z.infer<typeof OAuthProviderSchema>;
