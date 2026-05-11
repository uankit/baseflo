import { z } from 'zod';
import { TimestampSchema, UUIDSchema } from './common.js';
import { PlanSchema } from './auth.js';

export const BillingStatusSchema = z.enum([
  'active',
  'trialing',
  'past_due',
  'cancelled',
  'paused',
]);
export type BillingStatus = z.infer<typeof BillingStatusSchema>;

export const UsageMeterSchema = z.object({
  metric: z.string(),
  label: z.string(),
  used: z.number(),
  limit: z.number().nullable(),
  unit: z.string(),
});
export type UsageMeter = z.infer<typeof UsageMeterSchema>;

export const BillingSchema = z.object({
  organizationId: UUIDSchema,
  plan: PlanSchema,
  status: BillingStatusSchema,
  currentPeriodEnd: TimestampSchema.nullable(),
  meters: z.array(UsageMeterSchema),
  paymentMethodLast4: z.string().nullable(),
});
export type Billing = z.infer<typeof BillingSchema>;
