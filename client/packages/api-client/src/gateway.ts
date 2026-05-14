import { z } from 'zod';
import type { Transport } from './transports/base.js';

export interface GatewayConfig {
  transport: Transport;
}

export interface AuthUser {
  id: string;
  email: string;
  status: string;
}

export interface AuthOrganization {
  id: string;
  name: string;
  slug: string;
  plan?: string;
}

export interface AuthSession {
  access_token: string;
  refresh_token?: string;
  token_type: string;
  user: AuthUser;
  current_organization: AuthOrganization;
}

export interface MeResponse {
  user: AuthUser;
  current_organization: AuthOrganization;
}

export interface ConnectorInfo {
  kind: string;
  display_name: string;
  description: string;
  auth_method: string;
  capabilities: string[];
}

export interface DataSourceInfo {
  id: string;
  kind: string;
  name: string;
  status: string;
  discovered_schema?: Record<string, unknown> | null;
  last_synced_at?: string | null;
  last_error?: string | null;
  created_at: string;
}

export interface AvailableResource {
  external_id: string;
  name: string;
  metadata: Record<string, unknown>;
}

export interface ToolCallTrace {
  name: string;
  arguments: Record<string, unknown>;
  result?: unknown;
  error?: string | null;
}

export interface AskResponse {
  answer: string;
  artifacts: Array<Record<string, unknown>>;
  tool_calls: ToolCallTrace[];
  iterations: number;
  model: string;
  warning?: string | null;
}

export interface OperatingBrief {
  summary: {
    assets: number;
    columns: number;
    relationships: number;
    metrics: number;
    open_insights: number;
    proposed_actions: number;
    memories: number;
    last_built_at?: string | null;
  };
  business?: Record<string, unknown>;
  assets: Array<Record<string, unknown>>;
  relationships: Array<Record<string, unknown>>;
  metrics: Array<Record<string, unknown>>;
  insights: Array<Record<string, unknown>>;
  memories: Array<Record<string, unknown>>;
  actions: Array<Record<string, unknown>>;
}

const VoidSchema = z.looseObject({});
const OkSchema = z.object({ ok: z.boolean().optional(), accepted: z.boolean().optional() });

const AuthUserSchema = z.object({
  id: z.string(),
  email: z.string(),
  status: z.string(),
});

const AuthOrganizationSchema = z.object({
  id: z.string(),
  name: z.string(),
  slug: z.string(),
  plan: z.string().optional(),
});

const AuthSessionSchema = z.object({
  access_token: z.string(),
  refresh_token: z.string().optional(),
  token_type: z.string(),
  user: AuthUserSchema,
  current_organization: AuthOrganizationSchema,
});

const MeSchema = z.object({
  user: AuthUserSchema,
  current_organization: AuthOrganizationSchema,
});

const OperatingBriefSchema = z.object({
  summary: z.object({
    assets: z.number(),
    columns: z.number(),
    relationships: z.number(),
    metrics: z.number(),
    open_insights: z.number(),
    proposed_actions: z.number(),
    memories: z.number(),
    last_built_at: z.string().nullable().optional(),
  }),
  business: z.record(z.string(), z.unknown()).optional().default({}),
  assets: z.array(z.record(z.string(), z.unknown())),
  relationships: z.array(z.record(z.string(), z.unknown())),
  metrics: z.array(z.record(z.string(), z.unknown())),
  insights: z.array(z.record(z.string(), z.unknown())),
  memories: z.array(z.record(z.string(), z.unknown())),
  actions: z.array(z.record(z.string(), z.unknown())),
});

export class Gateway {
  private readonly transport: Transport;

  constructor(config: GatewayConfig) {
    this.transport = config.transport;
  }

  readonly auth = {
    requestMagicLink: async (req: { email: string }): Promise<{ ok: boolean }> => {
      const resp = await this.transport.request(
        { method: 'POST', path: '/api/v1/auth/magic-link', body: req },
        z.object({ ok: z.boolean().optional() }),
      );
      return { ok: resp.data.ok ?? true };
    },

    verifyMagicLink: async (req: { email: string; token: string }): Promise<AuthSession> =>
      (
        await this.transport.request(
          { method: 'POST', path: '/api/v1/auth/magic-link/verify', body: req },
          AuthSessionSchema,
        )
      ).data,

    me: async (): Promise<MeResponse> =>
      (
        await this.transport.request(
          { method: 'GET', path: '/api/v1/auth/me' },
          MeSchema,
        )
      ).data,

    signOut: async (): Promise<void> => {
      await this.transport.request(
        { method: 'POST', path: '/api/v1/auth/logout' },
        VoidSchema,
      );
    },
  };

  readonly connectors = {
    list: async (): Promise<ConnectorInfo[]> => {
      const resp = await this.transport.request(
        { method: 'GET', path: '/api/v1/connectors' },
        z.object({
          connectors: z.array(
            z.object({
              kind: z.string(),
              display_name: z.string(),
              description: z.string(),
              auth_method: z.string(),
              capabilities: z.array(z.string()),
            }),
          ),
        }),
      );
      return resp.data.connectors;
    },

    start: async (
      kind: string,
      body?: { shop_domain?: string },
    ): Promise<{ authorize_url: string }> =>
      (
        await this.transport.request(
          { method: 'POST', path: `/api/v1/connectors/${kind}/connect`, body },
          z.object({ authorize_url: z.string() }),
        )
      ).data,
  };

  readonly data = {
    listSources: async (): Promise<DataSourceInfo[]> =>
      (
        await this.transport.request(
          { method: 'GET', path: '/api/v1/data-sources' },
          z.object({
            data_sources: z.array(
              z.object({
                id: z.string(),
                kind: z.string(),
                name: z.string(),
                status: z.string(),
                discovered_schema: z.record(z.string(), z.unknown()).nullable().optional(),
                last_synced_at: z.string().nullable().optional(),
                last_error: z.string().nullable().optional(),
                created_at: z.string(),
              }),
            ),
          }),
        )
      ).data.data_sources,

    listConnectionResources: async (connectionId: string): Promise<{ resources: AvailableResource[] }> =>
      (
        await this.transport.request(
          { method: 'GET', path: `/api/v1/connections/${connectionId}/resources` },
          z.object({
            connection: z.record(z.string(), z.unknown()),
            resources: z.array(
              z.object({
                external_id: z.string(),
                name: z.string(),
                metadata: z.record(z.string(), z.unknown()).default({}),
              }),
            ),
          }),
        )
      ).data,

    createSources: async (connectionId: string, resources: AvailableResource[]): Promise<DataSourceInfo[]> =>
      (
        await this.transport.request(
          {
            method: 'POST',
            path: `/api/v1/connections/${connectionId}/sources`,
            body: { resources },
          },
          z.object({
            data_sources: z.array(
              z.object({
                id: z.string(),
                kind: z.string(),
                name: z.string(),
                status: z.string(),
                discovered_schema: z.record(z.string(), z.unknown()).nullable().optional(),
                last_synced_at: z.string().nullable().optional(),
                last_error: z.string().nullable().optional(),
                created_at: z.string(),
              }),
            ),
          }),
        )
      ).data.data_sources,
  };

  readonly operating = {
    brief: async (): Promise<OperatingBrief> =>
      (
        await this.transport.request(
          { method: 'GET', path: '/api/v1/operating/brief' },
          OperatingBriefSchema,
        )
      ).data,

    rebuild: async (): Promise<OperatingBrief> =>
      (
        await this.transport.request(
          { method: 'POST', path: '/api/v1/operating/rebuild' },
          OperatingBriefSchema,
        )
      ).data,

    scan: async (): Promise<OperatingBrief> =>
      (
        await this.transport.request(
          { method: 'POST', path: '/api/v1/operating/scan' },
          OperatingBriefSchema,
        )
      ).data,

    remember: async (body: { key: string; value: string }): Promise<{ id: string; key: string; value: string }> =>
      (
        await this.transport.request(
          { method: 'POST', path: '/api/v1/operating/memory', body },
          z.object({ id: z.string(), key: z.string(), value: z.string() }),
        )
      ).data,

    dismissInsight: async (insightId: string): Promise<void> => {
      await this.transport.request(
        { method: 'POST', path: `/api/v1/operating/insights/${insightId}/dismiss` },
        OkSchema,
      );
    },

    approveAction: async (actionId: string): Promise<void> => {
      await this.transport.request(
        { method: 'POST', path: `/api/v1/operating/actions/${actionId}/approve` },
        OkSchema,
      );
    },
  };

  readonly query = {
    ask: async (body: { question: string }): Promise<AskResponse> =>
      (
        await this.transport.request(
          { method: 'POST', path: '/api/v1/ask', body },
          z.object({
            answer: z.string(),
            artifacts: z.array(z.record(z.string(), z.unknown())).optional().default([]),
            tool_calls: z.array(
              z.object({
                name: z.string(),
                arguments: z.record(z.string(), z.unknown()),
                result: z.unknown().optional(),
                error: z.string().nullable().optional(),
              }),
            ),
            iterations: z.number(),
            model: z.string(),
            warning: z.string().nullable().optional(),
          }),
        )
      ).data,
  };

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
