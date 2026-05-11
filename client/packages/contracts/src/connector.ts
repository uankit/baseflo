import { z } from 'zod';
import { TimestampSchema, URLSchema, UUIDSchema } from './common.js';

export const ConnectorKindSchema = z.enum([
  'postgres',
  'csv',
  'excel',
  'google_sheets',
  'shopify',
  'stripe',
  'mailchimp',
  'notion',
]);
export type ConnectorKind = z.infer<typeof ConnectorKindSchema>;

export const ConnectorStatusSchema = z.enum(['connected', 'error', 'revoked', 'expired']);
export type ConnectorStatus = z.infer<typeof ConnectorStatusSchema>;

export const ConnectorAuthKindSchema = z.enum([
  'oauth2',
  'api_key',
  'db_url',
  'file_upload',
]);
export type ConnectorAuthKind = z.infer<typeof ConnectorAuthKindSchema>;

export const ConnectorSchema = z.object({
  id: UUIDSchema,
  projectId: UUIDSchema,
  kind: ConnectorKindSchema,
  displayName: z.string(),
  status: ConnectorStatusSchema,
  authKind: ConnectorAuthKindSchema,
  rowCountEstimate: z.number().int().nonnegative().nullable(),
  lastSyncAt: TimestampSchema.nullable(),
  lastError: z
    .object({ code: z.string(), message: z.string() })
    .nullable()
    .optional(),
});
export type Connector = z.infer<typeof ConnectorSchema>;

/** Server response when starting an install — may include a redirect for OAuth. */
export const ConnectorInstallStartSchema = z.object({
  flowId: UUIDSchema,
  redirectUrl: URLSchema.nullable(),
  nextStep: z.enum(['oauth_redirect', 'collect_credentials', 'upload_file', 'ready']),
});
export type ConnectorInstallStart = z.infer<typeof ConnectorInstallStartSchema>;

export const PostgresInstallPayloadSchema = z.object({
  connectionString: z.string().min(8),
  displayName: z.string().min(1).max(64),
});
export type PostgresInstallPayload = z.infer<typeof PostgresInstallPayloadSchema>;

export const StripeInstallPayloadSchema = z.object({
  apiKey: z.string().min(8),
  displayName: z.string().min(1).max(64),
  testMode: z.boolean().default(false),
});
export type StripeInstallPayload = z.infer<typeof StripeInstallPayloadSchema>;

export const MailchimpInstallPayloadSchema = z.object({
  apiKey: z.string().min(8),
  displayName: z.string().min(1).max(64),
  serverPrefix: z.string().min(2).max(10),
});
export type MailchimpInstallPayload = z.infer<typeof MailchimpInstallPayloadSchema>;
