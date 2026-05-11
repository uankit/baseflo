import { z } from 'zod';

export const InsightSeveritySchema = z.enum(['info', 'low', 'medium', 'high', 'critical']);
export type InsightSeverity = z.infer<typeof InsightSeveritySchema>;

export const InsightKindSchema = z.enum([
  'volume',
  'gap',
  'concentration',
  'trend',
  'anomaly',
  'correlation',
  'segment',
]);
export type InsightKind = z.infer<typeof InsightKindSchema>;

export const InsightSchema = z.object({
  id: z.string().uuid(),
  kind: InsightKindSchema,
  severity: InsightSeveritySchema,
  title: z.string(),
  description: z.string(),
  confidence: z.number().min(0).max(1),
  sql: z.string().nullable(),
  data: z.record(z.string(), z.unknown()).default({}),
  is_read: z.boolean().default(false),
  is_dismissed: z.boolean().default(false),
  created_at: z.iso.datetime(),
});
export type Insight = z.infer<typeof InsightSchema>;

export const InsightListResponseSchema = z.object({
  items: z.array(InsightSchema),
  total: z.number().int().nonnegative(),
  unread_count: z.number().int().nonnegative(),
});
export type InsightListResponse = z.infer<typeof InsightListResponseSchema>;

export const InsightStatsResponseSchema = z.object({
  total: z.number().int().nonnegative(),
  unread: z.number().int().nonnegative(),
  by_severity: z.record(z.string(), z.number().int().nonnegative()),
});
export type InsightStatsResponse = z.infer<typeof InsightStatsResponseSchema>;
