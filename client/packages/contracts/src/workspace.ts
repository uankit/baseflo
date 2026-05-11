import { z } from 'zod';
import { TimestampSchema, UUIDSchema } from './common.js';
import { ConnectorKindSchema } from './connector.js';

/**
 * AdminUISpec — the schema-driven admin pane shape. Generated server-side
 * from SchemaIR per docs/40-features/ADMIN-GEN.md §3.2.
 */
export const WidgetKindSchema = z.enum([
  'text',
  'long_text',
  'number',
  'money',
  'date',
  'datetime',
  'status_chip',
  'pii_masked',
  'link',
  'boolean',
  'file_upload',
  'select',
]);
export type WidgetKind = z.infer<typeof WidgetKindSchema>;

export const FilterKindSchema = z.enum([
  'text_contains',
  'number_range',
  'date_range',
  'status_in',
  'boolean',
]);
export type FilterKind = z.infer<typeof FilterKindSchema>;

export const SortDirectionSchema = z.enum(['asc', 'desc']);
export type SortDirection = z.infer<typeof SortDirectionSchema>;

export const ListColumnSpecSchema = z.object({
  name: z.string(),
  label: z.string(),
  widget: WidgetKindSchema,
  sortable: z.boolean().default(true),
  filterable: z.boolean().default(true),
  visibleByDefault: z.boolean().default(true),
  enumValues: z.array(z.string()).optional(),
  currency: z.string().optional(),
});
export type ListColumnSpec = z.infer<typeof ListColumnSpecSchema>;

export const ListViewSpecSchema = z.object({
  columns: z.array(ListColumnSpecSchema),
  defaultSort: z.object({
    column: z.string(),
    direction: SortDirectionSchema,
  }),
  searchColumns: z.array(z.string()),
  pageSize: z.number().int().positive().default(50),
  showSourceBadge: z.boolean().default(false),
});
export type ListViewSpec = z.infer<typeof ListViewSpecSchema>;

export const DetailSectionSchema = z.object({
  id: z.string(),
  label: z.string(),
  columns: z.array(z.string()),
});
export type DetailSection = z.infer<typeof DetailSectionSchema>;

export const RelationshipNavSpecSchema = z.object({
  fromColumn: z.string(),
  toTable: z.string(),
  label: z.string(),
});
export type RelationshipNavSpec = z.infer<typeof RelationshipNavSpecSchema>;

export const DetailViewSpecSchema = z.object({
  sections: z.array(DetailSectionSchema),
  relationships: z.array(RelationshipNavSpecSchema),
  activityTimeline: z.boolean().default(true),
  editableColumns: z.array(z.string()).default([]),
});
export type DetailViewSpec = z.infer<typeof DetailViewSpecSchema>;

export const BulkActionSchema = z.object({
  id: z.string(),
  label: z.string(),
  destructive: z.boolean().default(false),
});
export type BulkAction = z.infer<typeof BulkActionSchema>;

export const AdminTabSchema = z.object({
  id: z.string(),
  label: z.string(),
  icon: z.string().optional(),
  tableName: z.string(),
  listView: ListViewSpecSchema,
  detailView: DetailViewSpecSchema,
  bulkActions: z.array(BulkActionSchema).default([]),
  badgeCountQuery: z.string().nullable().optional(),
});
export type AdminTab = z.infer<typeof AdminTabSchema>;

export const AdminUISpecSchema = z.object({
  projectId: UUIDSchema,
  versionId: UUIDSchema,
  tabs: z.array(AdminTabSchema),
  refinementEnabled: z.boolean().default(true),
  exportEnabled: z.boolean().default(true),
});
export type AdminUISpec = z.infer<typeof AdminUISpecSchema>;

/** Source attribution for a row of a reconciled entity. */
export const SourceContributionSchema = z.object({
  connectorKind: ConnectorKindSchema,
  connectorId: UUIDSchema,
  fields: z.array(z.string()),
});
export type SourceContribution = z.infer<typeof SourceContributionSchema>;

export const EntityRowSchema = z.object({
  id: z.string(),
  values: z.record(z.string(), z.unknown()),
  contributions: z.array(SourceContributionSchema).default([]),
});
export type EntityRow = z.infer<typeof EntityRowSchema>;

export const EntityListSchema = z.object({
  rows: z.array(EntityRowSchema),
  total: z.number().int().nonnegative(),
  page: z.number().int().nonnegative(),
  pageSize: z.number().int().positive(),
});
export type EntityList = z.infer<typeof EntityListSchema>;

/** Overview tab payload. */
export const KPIPreviewSchema = z.object({
  id: z.string(),
  label: z.string(),
  value: z.string(),
  delta: z.string().nullable(),
  trend: z.enum(['up', 'down', 'flat']).nullable(),
  unit: z.string().nullable(),
});
export type KPIPreview = z.infer<typeof KPIPreviewSchema>;

export const ActivityEntrySchema = z.object({
  id: UUIDSchema,
  text: z.string(),
  source: z.string().nullable(),
  occurredAt: TimestampSchema,
});
export type ActivityEntry = z.infer<typeof ActivityEntrySchema>;

export const DigestSnippetSchema = z.object({
  headline: z.string(),
  body: z.string(),
  generatedAt: TimestampSchema,
});
export type DigestSnippet = z.infer<typeof DigestSnippetSchema>;

export const OverviewSummarySchema = z.object({
  versionId: UUIDSchema,
  digest: DigestSnippetSchema.nullable(),
  kpis: z.array(KPIPreviewSchema),
  activity: z.array(ActivityEntrySchema),
  onboardingChecklist: z.array(
    z.object({
      id: z.string(),
      label: z.string(),
      done: z.boolean(),
    }),
  ),
});
export type OverviewSummary = z.infer<typeof OverviewSummarySchema>;

export const PIIRevealResponseSchema = z.object({
  value: z.string(),
  expiresAt: TimestampSchema,
});
export type PIIRevealResponse = z.infer<typeof PIIRevealResponseSchema>;
