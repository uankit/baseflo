import { z } from 'zod';
import {
  type Insight,
  type InsightListResponse,
  type InsightStatsResponse,
  InsightListResponseSchema,
  InsightStatsResponseSchema,
  type MagicLinkConsume,
  type MagicLinkRequest,
  type Session,
} from '@baseflo/contracts';
import type { Transport, TransportRequest } from './transports/base.js';

export interface GatewayConfig {
  transport: Transport;
}

const VoidSchema = z.looseObject({});
const OkSchema = z.object({ ok: z.boolean().optional(), accepted: z.boolean().optional() });

export class Gateway {
  private readonly transport: Transport;

  constructor(config: GatewayConfig) {
    this.transport = config.transport;
  }

  // ── auth ──────────────────────────────────────────────────────────────────
  readonly auth = {
    /** Request a magic link. Returns dev_token for MVP (no email service). */
    requestMagicLink: async (
      req: MagicLinkRequest,
    ): Promise<{ message: string; dev_token: string | null }> => {
      const resp = await this.transport.request(
        { method: 'POST', path: '/api/v1/auth/magic-link', body: req },
        z.object({ message: z.string(), dev_token: z.string().nullable() }),
      );
      return resp.data;
    },

    /** Verify magic link token and get JWT access token. */
    verifyMagicLink: async (req: {
      email: string;
      token: string;
    }): Promise<{ access_token: string; token_type: string; user: { id: string; email: string; organization_id: string } }> =>
      (
        await this.transport.request(
          { method: 'POST', path: '/api/v1/auth/magic-link/verify', body: req },
          z.object({
            access_token: z.string(),
            token_type: z.string(),
            user: z.object({
              id: z.string().uuid(),
              email: z.string().email(),
              organization_id: z.string().uuid(),
            }),
          }),
        )
      ).data,

    /** Get current authenticated user. */
    me: async (): Promise<{ id: string; email: string; organization: { id: string; name: string; slug: string } }> =>
      (
        await this.transport.request(
          { method: 'GET', path: '/api/v1/auth/me' },
          z.object({
            id: z.string().uuid(),
            email: z.string().email(),
            organization: z.object({
              id: z.string().uuid(),
              name: z.string(),
              slug: z.string(),
            }),
          }),
        )
      ).data,

    signOut: async (): Promise<void> => {
      await this.transport.request(
        { method: 'POST', path: '/api/v1/auth/logout' },
        VoidSchema,
      );
    },
  };

  // ── projects ──────────────────────────────────────────────────────────────
  readonly projects = {
    list: async (): Promise<{ id: string; name: string; slug: string }[]> => {
      const resp = await this.transport.request(
        { method: 'GET', path: '/api/v1/projects' },
        z.array(
          z.object({
            id: z.string().uuid(),
            organization_id: z.string().uuid(),
            name: z.string(),
            slug: z.string(),
            created_at: z.string(),
          }),
        ),
      );
      return resp.data;
    },

    create: async (body: { name: string }): Promise<{ id: string; name: string; slug: string }> => {
      const resp = await this.transport.request(
        { method: 'POST', path: '/api/v1/projects', body },
        z.object({
          id: z.string().uuid(),
          organization_id: z.string().uuid(),
          name: z.string(),
          slug: z.string(),
          created_at: z.string(),
        }),
      );
      return resp.data;
    },

    get: async (projectId: string): Promise<{ id: string; name: string; slug: string }> => {
      const resp = await this.transport.request(
        { method: 'GET', path: `/api/v1/projects/${projectId}` },
        z.object({
          id: z.string().uuid(),
          organization_id: z.string().uuid(),
          name: z.string(),
          slug: z.string(),
          created_at: z.string(),
        }),
      );
      return resp.data;
    },
  };

  // ── connectors ────────────────────────────────────────────────────────────
  readonly connectors = {
    list: async (projectId: string): Promise<{ id: string; kind: string; name: string; status: string; config: Record<string, unknown> }[]> => {
      const resp = await this.transport.request(
        { method: 'GET', path: '/api/v1/connectors', query: { project_id: projectId } },
        z.array(z.looseObject({})),
      );
      return (resp.data as unknown[]).map((row): { id: string; kind: string; name: string; status: string; config: Record<string, unknown> } => {
        const r = row as Record<string, unknown>;
        return {
          id: String(r.id),
          kind: String(r.kind),
          name: String(r.name),
          status: String(r.status),
          config: (r.config as Record<string, unknown>) ?? {},
        };
      });
    },

    create: async (body: { project_id: string; kind: string; name: string; config: Record<string, unknown> }): Promise<{ id: string }> => {
      const resp = await this.transport.request(
        { method: 'POST', path: '/api/v1/connectors', body },
        z.object({ id: z.string().uuid() }),
      );
      return resp.data;
    },

    getAuthUrl: async (projectId: string, spreadsheetId?: string, returnTo?: string): Promise<{ auth_url: string }> => {
      const query: Record<string, string> = { project_id: projectId };
      if (spreadsheetId) query.spreadsheet_id = spreadsheetId;
      if (returnTo) query.return_to = returnTo;
      const resp = await this.transport.request(
        { method: 'GET', path: '/api/v1/connectors/google-sheets/auth-url', query },
        z.object({ auth_url: z.string() }),
      );
      return resp.data;
    },

    sync: async (sourceId: string): Promise<{ sync_run_id: string; status: string; rows_synced: number; error_message: string | null }> => {
      const resp = await this.transport.request(
        { method: 'POST', path: `/api/v1/connectors/${sourceId}/sync` },
        z.object({
          sync_run_id: z.string().uuid(),
          status: z.string(),
          rows_synced: z.number().int(),
          error_message: z.string().nullable(),
        }),
      );
      return resp.data;
    },
  };

  // ── insights ──────────────────────────────────────────────────────────────
  readonly insights = {
    list: async (query: {
      project_id: string;
      unread_only?: boolean;
      limit?: number;
      offset?: number;
    }): Promise<InsightListResponse> =>
      (
        await this.transport.request(
          { method: 'GET', path: '/api/v1/insights', query: queryToParams(query) },
          InsightListResponseSchema,
        )
      ).data,

    stats: async (project_id: string): Promise<InsightStatsResponse> =>
      (
        await this.transport.request(
          { method: 'GET', path: '/api/v1/insights/stats', query: { project_id } },
          InsightStatsResponseSchema,
        )
      ).data,

    markRead: async (insightId: string): Promise<void> => {
      await this.transport.request(
        { method: 'POST', path: `/api/v1/insights/${insightId}/read` },
        VoidSchema,
      );
    },

    dismiss: async (insightId: string): Promise<void> => {
      await this.transport.request(
        { method: 'POST', path: `/api/v1/insights/${insightId}/dismiss` },
        VoidSchema,
      );
    },
  };

  // ── query ─────────────────────────────────────────────────────────────────
  readonly query = {
    ask: async (body: { project_id: string; question: string }): Promise<{ answer: string; sql: string | null }> => {
      const resp = await this.transport.request(
        { method: 'POST', path: '/api/v1/query/ask', body },
        z.object({ answer: z.string(), sql: z.string().nullable() }),
      );
      return resp.data;
    },
  };

  // ── system ────────────────────────────────────────────────────────────────
  readonly system = {
    health: async () => {
      const Schema = z.object({ healthy: z.boolean().optional(), ok: z.boolean().optional() });
      return (
        await this.transport.request(
          { method: 'GET', path: '/api/v1/health' },
          Schema,
        )
      ).data;
    },
  };
}

export function createGateway(config: GatewayConfig): Gateway {
  return new Gateway(config);
}

function queryToParams(query: Record<string, unknown>): TransportRequest['query'] {
  const out: Record<string, string | number | boolean | undefined> = {};
  for (const [key, value] of Object.entries(query)) {
    if (value === null || value === undefined) continue;
    if (
      typeof value === 'string' ||
      typeof value === 'number' ||
      typeof value === 'boolean'
    ) {
      out[key] = value;
    } else {
      out[key] = JSON.stringify(value);
    }
  }
  return out;
}
