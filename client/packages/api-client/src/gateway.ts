import { z } from 'zod';
import {
  AdminUISpecSchema,
  AnalyticsSummarySchema,
  ApiKeySchema,
  AuditPageSchema,
  BillingSchema,
  CreateApiKeyRequestSchema,
  CreateApiKeyResponseSchema,
  CreateOrgRequestSchema,
  CreateProjectRequestSchema,
  CreateShareLinkRequestSchema,
  EntityListSchema,
  EntityRowSchema,
  ExportSchema,
  InviteRequestSchema,
  MembershipSchema,
  OrgSchema,
  OverviewSummarySchema,
  PIIRevealResponseSchema,
  ProjectSummarySchema,
  ProjectVersionSchema,
  PublicShareSchema,
  RefinementApplyResponseSchema,
  RefinementHistoryItemSchema,
  RefinementProposalSchema,
  RequestExportSchema,
  SessionSchema,
  ShareLinkSchema,
  StartSagaResponseSchema,
  ListAgentsResponseSchema,
  GetAgentFeedResponseSchema,
  GetAgentTasksResponseSchema,

  type AdminUISpec,
  type AnalyticsSummary,
  type ApiKey,
  type AuditFilter,
  type AuditPage,
  type Billing,
  type Connector,
  type CreateApiKeyRequest,
  type CreateApiKeyResponse,
  type CreateOrgRequest,
  type CreateProjectRequest,
  type CreateShareLinkRequest,
  type EntityList,
  type EntityRow,
  type ExportRecord,
  type InviteRequest,
  type MagicLinkConsume,
  type MagicLinkRequest,
  type Membership,
  type Org,
  type OverviewSummary,
  type PIIRevealResponse,
  type ProjectSummary,
  type ProjectVersion,
  type PublicShare,
  type RefinementApplyResponse,
  type RefinementHistoryItem,
  type RefinementProposal,
  type RequestExport,
  type Session,
  type ShareLink,
  type SignInRequest,
  type StartSagaResponse,
} from '@baseflo/contracts';
import type { Transport, TransportRequest } from './transports/base.js';
import { subscribeToSaga, type SseSubscription } from './transports/sse.js';

/**
 * Production gateway. Public alpha calls map 1:1 to the FastAPI route surface;
 * password sign-in remains a typed future extension while alpha uses magic
 * links. See docs/40-features/WEB-APP.md §3.6. Path conventions match the
 * routes in `server/app/api/v1/routes/`:
 *
 *   /api/v1/auth/{magic-link/request, magic-link/consume, session, signout}
 *   /api/v1/orgs[, /{slug}, /{slug}/projects, /{slug}/projects/{slug}]
 *   /api/v1/projects/{id}[/connectors, /sagas/start, /refinements, /versions]
 *   /api/v1/connectors[, /{id}, /{id}/revoke, /{id}/reconnect, /upload]
 *   /api/v1/sagas/{id}/{cancel, clarification}
 *   /api/v1/conversations/{id}/events
 *   /api/v1/versions/{id}/{admin-ui-spec, overview, data/*, analytics}
 *   /api/v1/refinements/{id}/{apply, discard}
 *   /api/v1/exports/{id}
 *   /api/v1/share-links/{token}/revoke
 *   /api/v1/public/shares/{token}
 *   /api/v1/orgs/{slug}/{members, invites, audit, api-keys, billing}
 */
export interface GatewayConfig {
  transport: Transport;
  /** Base URL for SSE subscriptions. Usually same origin as REST. */
  sseBaseUrl?: string;
}

const VoidSchema = z.looseObject({});
const OkSchema = z.object({ ok: z.boolean().optional(), accepted: z.boolean().optional() });
const ProjectListSchema = z.array(ProjectSummarySchema);
const OrgListSchema = z.array(OrgSchema);
const MembershipListSchema = z.array(MembershipSchema);
const RefinementHistorySchema = z.array(RefinementHistoryItemSchema);
const ShareLinkListSchema = z.array(ShareLinkSchema);
const ProjectVersionListSchema = z.array(ProjectVersionSchema);
const ApiKeyListSchema = z.array(ApiKeySchema);
const ExportListSchema = z.array(ExportSchema);

export class Gateway {
  private readonly transport: Transport;
  private readonly sseBaseUrl: string;

  constructor(config: GatewayConfig) {
    this.transport = config.transport;
    this.sseBaseUrl = config.sseBaseUrl ?? '';
  }

  // ── auth ──────────────────────────────────────────────────────────────────
  readonly auth = {
    signIn: async (req: SignInRequest): Promise<Session> =>
      (
        await this.transport.request(
          { method: 'POST', path: '/api/v1/auth/sign-in', body: req },
          SessionSchema,
        )
      ).data,

    signInMagicLink: async (
      req: MagicLinkRequest,
    ): Promise<{ ok: true }> => {
      await this.transport.request(
        { method: 'POST', path: '/api/v1/auth/magic-link/request', body: req },
        OkSchema,
      );
      return { ok: true };
    },

    consumeMagicLink: async (req: MagicLinkConsume): Promise<Session> =>
      (
        await this.transport.request(
          { method: 'POST', path: '/api/v1/auth/magic-link/consume', body: req },
          SessionSchema,
        )
      ).data,

    session: async (): Promise<Session> =>
      (
        await this.transport.request(
          { method: 'GET', path: '/api/v1/auth/session' },
          SessionSchema,
        )
      ).data,

    signOut: async (): Promise<void> => {
      await this.transport.request(
        { method: 'POST', path: '/api/v1/auth/signout' },
        VoidSchema,
      );
    },

    /** Backend returns a 302; frontend just opens this in a new window for OAuth. */
    oauthStartUrl: (provider: 'google'): string =>
      `/api/v1/auth/oauth/${provider}/start`,
  };

  // ── orgs ──────────────────────────────────────────────────────────────────
  readonly orgs = {
    list: async (): Promise<Org[]> =>
      (await this.transport.request({ method: 'GET', path: '/api/v1/orgs' }, OrgListSchema))
        .data,

    create: async (req: CreateOrgRequest): Promise<Org> => {
      const parsed = CreateOrgRequestSchema.parse(req);
      const body = { name: parsed.name, slug: parsed.slug ?? slugify(parsed.name) };
      // Backend returns CreateOrgResponse; we re-fetch to get full Org shape.
      await this.transport.request(
        { method: 'POST', path: '/api/v1/orgs', body },
        z.looseObject({}),
      );
      return this.orgs.get(body.slug);
    },

    get: async (orgSlug: string): Promise<Org> =>
      (
        await this.transport.request(
          { method: 'GET', path: `/api/v1/orgs/${orgSlug}` },
          OrgSchema,
        )
      ).data,

    members: async (orgSlug: string): Promise<Membership[]> =>
      (
        await this.transport.request(
          { method: 'GET', path: `/api/v1/orgs/${orgSlug}/members` },
          MembershipListSchema,
        )
      ).data,

    invite: async (orgSlug: string, req: InviteRequest): Promise<Membership> => {
      const parsed = InviteRequestSchema.parse(req);
      return (
        await this.transport.request(
          { method: 'POST', path: `/api/v1/orgs/${orgSlug}/invites`, body: parsed },
          MembershipSchema,
        )
      ).data;
    },
  };

  // ── projects ──────────────────────────────────────────────────────────────
  readonly projects = {
    list: async (orgSlug: string): Promise<ProjectSummary[]> =>
      (
        await this.transport.request(
          { method: 'GET', path: `/api/v1/orgs/${orgSlug}/projects` },
          ProjectListSchema,
        )
      ).data,

    get: async (orgSlug: string, projectSlug: string) =>
      (
        await this.transport.request(
          { method: 'GET', path: `/api/v1/orgs/${orgSlug}/projects/${projectSlug}` },
          ProjectSummarySchema.extend({
            connectorCount: z.number().int().nonnegative().default(0),
            versionCount: z.number().int().positive().default(1),
          }),
        )
      ).data,

    create: async (orgSlug: string, req: CreateProjectRequest): Promise<ProjectSummary> => {
      const parsed = CreateProjectRequestSchema.parse(req);
      const body = {
        name: parsed.name,
        slug: parsed.slug ?? slugify(parsed.name),
        description: parsed.description,
        deployment_mode: parsed.deploymentMode,
      };
      return (
        await this.transport.request(
          { method: 'POST', path: `/api/v1/orgs/${orgSlug}/projects`, body },
          ProjectSummarySchema,
        )
      ).data;
    },

    versions: async (projectId: string): Promise<ProjectVersion[]> =>
      (
        await this.transport.request(
          { method: 'GET', path: `/api/v1/projects/${projectId}/versions` },
          ProjectVersionListSchema,
        )
      ).data,

    rollback: async (projectId: string, versionId: string) => {
      const Schema = z.object({ currentVersionId: z.string().uuid() });
      return (
        await this.transport.request(
          {
            method: 'POST',
            path: `/api/v1/projects/${projectId}/rollback`,
            body: { versionId },
          },
          Schema,
        )
      ).data;
    },
  };

  // ── connectors ────────────────────────────────────────────────────────────
  readonly connectors = {
    list: async (projectId: string): Promise<Connector[]> => {
      const ServerListSchema = z.object({
        connectors: z.array(z.looseObject({})),
      });
      const resp = await this.transport.request(
        {
          method: 'GET',
          path: `/api/v1/connectors`,
          query: { project_id: projectId },
        },
        ServerListSchema,
      );
      // Coerce server's snake_case ConnectorSummary to camelCase Connector.
      return (resp.data.connectors as unknown[]).map((row): Connector => {
        const r = row as Record<string, unknown>;
        return {
          id: String(r.id),
          projectId: String(r.project_id),
          kind: String(r.kind) as Connector['kind'],
          displayName: String(r.display_name),
          status: String(r.status) as Connector['status'],
          authKind: 'api_key',
          rowCountEstimate: null,
          lastSyncAt: r.last_sync_at != null ? String(r.last_sync_at) : null,
          lastError: null,
        };
      });
    },

    /**
     * Returns the right next step for each supported connector kind. The dialog
     * uses this to decide whether to show credentials, file upload, or OAuth.
     */
    startInstall: async (
      projectId: string,
      kind: string,
    ): Promise<{
      flowId: string;
      redirectUrl: string | null;
      nextStep: 'oauth_redirect' | 'collect_credentials' | 'upload_file' | 'unsupported';
    }> => {
      if (kind === 'csv' || kind === 'excel') {
        return { flowId: '', redirectUrl: null, nextStep: 'upload_file' };
      }
      if (kind === 'shopify') {
        return {
          flowId: '',
          // Dialog asks for shop_domain and appends &shop_domain=<value> before window.location.assign.
          redirectUrl: `/api/v1/oauth/shopify/install?project_id=${projectId}`,
          nextStep: 'oauth_redirect',
        };
      }
      if (kind === 'google_sheets') {
        return {
          flowId: '',
          // Dialog asks for spreadsheet_id and appends &spreadsheet_id=<value>.
          redirectUrl: `/api/v1/oauth/google_sheets/install?project_id=${projectId}`,
          nextStep: 'oauth_redirect',
        };
      }
      if (kind === 'stripe' || kind === 'postgres') {
        return { flowId: '', redirectUrl: null, nextStep: 'collect_credentials' };
      }
      return { flowId: '', redirectUrl: null, nextStep: 'unsupported' };
    },

    /** Install Stripe by API key — backend validates against Stripe's /v1/account. */
    installStripe: async (projectId: string, apiKey: string): Promise<Connector> => {
      const Schema = z.object({
        connector_id: z.string().uuid(),
        kind: z.string(),
        project_id: z.string().uuid(),
        display_name: z.string(),
        account_id: z.string().nullable(),
      });
      const resp = await this.transport.request(
        {
          method: 'POST',
          path: '/api/v1/connectors/stripe/install',
          body: { project_id: projectId, api_key: apiKey },
        },
        Schema,
      );
      return {
        id: resp.data.connector_id,
        projectId: resp.data.project_id,
        kind: 'stripe',
        displayName: resp.data.display_name,
        status: 'connected',
        authKind: 'api_key',
        rowCountEstimate: null,
        lastSyncAt: null,
        lastError: null,
      };
    },

    /** Install Postgres by DSN — backend validates with `SELECT 1`. */
    installPostgres: async (
      projectId: string,
      dsn: string,
      displayName = 'Postgres',
    ): Promise<Connector> => {
      const Schema = z.object({
        connector_id: z.string().uuid(),
        kind: z.string(),
        project_id: z.string().uuid(),
        display_name: z.string(),
        account_id: z.string().nullable(),
      });
      const resp = await this.transport.request(
        {
          method: 'POST',
          path: '/api/v1/connectors/postgres/install',
          body: { project_id: projectId, dsn, display_name: displayName },
        },
        Schema,
      );
      return {
        id: resp.data.connector_id,
        projectId: resp.data.project_id,
        kind: 'postgres',
        displayName: resp.data.display_name,
        status: 'connected',
        authKind: 'db_url',
        rowCountEstimate: null,
        lastSyncAt: null,
        lastError: null,
      };
    },

    /** Multipart file upload for CSV / Excel connectors. */
    uploadInstall: async (
      projectId: string,
      kind: 'csv' | 'excel',
      file: File,
      displayName: string,
    ): Promise<Connector> => {
      const form = new FormData();
      form.append('project_id', projectId);
      form.append('kind', kind);
      form.append('display_name', displayName);
      form.append('file', file);
      const resp = await fetch('/api/v1/connectors/upload', {
        method: 'POST',
        credentials: 'include',
        body: form,
      });
      if (!resp.ok) {
        throw new Error(`Upload failed (${resp.status}): ${await resp.text()}`);
      }
      const row = (await resp.json()) as Record<string, unknown>;
      return {
        id: String(row.id),
        projectId: String(row.project_id),
        kind: String(row.kind) as Connector['kind'],
        displayName: String(row.display_name),
        status: 'connected',
        authKind: 'file_upload',
        rowCountEstimate: null,
        lastSyncAt: null,
        lastError: null,
      };
    },

    completeInstall: async (
      _projectId: string,
      _flowId: string,
      _payload: unknown,
    ): Promise<Connector> => {
      throw new Error(
        'completeInstall is only used by OAuth flows (handled by /oauth router) ' +
          'and direct credential routes (e.g. /connectors/stripe/install). For ' +
          'CSV/Excel use uploadInstall.',
      );
    },

    revoke: async (connectorId: string): Promise<void> => {
      await this.transport.request(
        { method: 'POST', path: `/api/v1/connectors/${connectorId}/revoke` },
        VoidSchema,
      );
    },

    reconnect: async (connectorId: string) => {
      const Schema = z.object({ redirect_url: z.string().nullable() });
      const resp = await this.transport.request(
        { method: 'POST', path: `/api/v1/connectors/${connectorId}/reconnect` },
        Schema,
      );
      return { redirectUrl: resp.data.redirect_url };
    },

    health: async (_id: string) => Promise.resolve({ ok: true }),
  };

  // ── sagas ─────────────────────────────────────────────────────────────────
  readonly sagas = {
    start: async (
      projectId: string,
      prompt: string,
      parentVersionId?: string | null,
    ): Promise<StartSagaResponse> =>
      (
        await this.transport.request(
          {
            method: 'POST',
            path: `/api/v1/projects/${projectId}/sagas/start`,
            body: { prompt, parent_version_id: parentVersionId ?? null },
          },
          StartSagaResponseSchema,
        )
      ).data,

    cancel: async (conversationId: string): Promise<void> => {
      await this.transport.request(
        { method: 'POST', path: `/api/v1/sagas/${conversationId}/cancel` },
        VoidSchema,
      );
    },

    answerClarification: async (
      conversationId: string,
      questionId: string,
      answer: string,
    ): Promise<void> => {
      await this.transport.request(
        {
          method: 'POST',
          path: `/api/v1/sagas/${conversationId}/clarification`,
          body: { questionId, answer },
        },
        VoidSchema,
      );
    },

    subscribe: (
      conversationId: string,
      handlers: Parameters<typeof subscribeToSaga>[0] extends infer T
        ? T extends { onEvent: infer U }
          ? {
              onEvent: U;
              onError?: (e: unknown) => void;
              onOpen?: () => void;
              onClose?: () => void;
              fromSequence?: number;
            }
          : never
        : never,
    ): SseSubscription =>
      subscribeToSaga({
        baseUrl: this.sseBaseUrl,
        conversationId,
        ...handlers,
      }),
  };

  // ── workspace ─────────────────────────────────────────────────────────────
  readonly workspace = {
    getAdminUISpec: async (versionId: string): Promise<AdminUISpec> =>
      (
        await this.transport.request(
          { method: 'GET', path: `/api/v1/versions/${versionId}/admin-ui-spec` },
          AdminUISpecSchema,
        )
      ).data,

    getOverview: async (versionId: string): Promise<OverviewSummary> =>
      (
        await this.transport.request(
          { method: 'GET', path: `/api/v1/versions/${versionId}/overview` },
          OverviewSummarySchema,
        )
      ).data,

    listEntities: async (
      versionId: string,
      table: string,
      query: { search?: string; page?: number; pageSize?: number; sort?: string } = {},
    ): Promise<EntityList> =>
      (
        await this.transport.request(
          {
            method: 'GET',
            path: `/api/v1/versions/${versionId}/data/${table}`,
            query: queryToParams(query),
          },
          EntityListSchema,
        )
      ).data,

    getEntity: async (versionId: string, table: string, id: string): Promise<EntityRow> =>
      (
        await this.transport.request(
          { method: 'GET', path: `/api/v1/versions/${versionId}/data/${table}/${id}` },
          EntityRowSchema,
        )
      ).data,

    revealPII: async (
      versionId: string,
      table: string,
      id: string,
      column: string,
    ): Promise<PIIRevealResponse> =>
      (
        await this.transport.request(
          {
            method: 'POST',
            path: `/api/v1/versions/${versionId}/data/${table}/${id}/reveal-pii`,
            body: { column },
          },
          PIIRevealResponseSchema,
        )
      ).data,

    getAnalytics: async (versionId: string): Promise<AnalyticsSummary> =>
      (
        await this.transport.request(
          { method: 'GET', path: `/api/v1/versions/${versionId}/analytics` },
          AnalyticsSummarySchema,
        )
      ).data,
  };

  // ── refinements ───────────────────────────────────────────────────────────
  readonly refinements = {
    propose: async (projectId: string, intentText: string): Promise<RefinementProposal> =>
      (
        await this.transport.request(
          {
            method: 'POST',
            path: `/api/v1/projects/${projectId}/refinements`,
            body: { intent_text: intentText },
          },
          RefinementProposalSchema,
        )
      ).data,

    apply: async (refinementId: string): Promise<RefinementApplyResponse> =>
      (
        await this.transport.request(
          { method: 'POST', path: `/api/v1/refinements/${refinementId}/apply` },
          RefinementApplyResponseSchema,
        )
      ).data,

    discard: async (refinementId: string): Promise<void> => {
      await this.transport.request(
        { method: 'POST', path: `/api/v1/refinements/${refinementId}/discard` },
        VoidSchema,
      );
    },

    history: async (projectId: string): Promise<RefinementHistoryItem[]> =>
      (
        await this.transport.request(
          { method: 'GET', path: `/api/v1/projects/${projectId}/refinements` },
          RefinementHistorySchema,
        )
      ).data,
  };

  // ── exports ───────────────────────────────────────────────────────────────
  readonly exports = {
    request: async (versionId: string, req: RequestExport): Promise<ExportRecord> => {
      const parsed = RequestExportSchema.parse(req);
      return (
        await this.transport.request(
          { method: 'POST', path: `/api/v1/versions/${versionId}/exports`, body: parsed },
          ExportSchema,
        )
      ).data;
    },

    list: async (projectId: string): Promise<ExportRecord[]> =>
      (
        await this.transport.request(
          { method: 'GET', path: `/api/v1/projects/${projectId}/exports` },
          ExportListSchema,
        )
      ).data,

    poll: async (exportId: string): Promise<ExportRecord> =>
      (
        await this.transport.request(
          { method: 'GET', path: `/api/v1/exports/${exportId}` },
          ExportSchema,
        )
      ).data,
  };

  // ── share links ───────────────────────────────────────────────────────────
  readonly shareLinks = {
    list: async (projectId: string): Promise<ShareLink[]> =>
      (
        await this.transport.request(
          { method: 'GET', path: `/api/v1/projects/${projectId}/share-links` },
          ShareLinkListSchema,
        )
      ).data,

    create: async (projectId: string, req: CreateShareLinkRequest): Promise<ShareLink> => {
      const parsed = CreateShareLinkRequestSchema.parse(req);
      return (
        await this.transport.request(
          {
            method: 'POST',
            path: `/api/v1/projects/${projectId}/share-links`,
            body: parsed,
          },
          ShareLinkSchema,
        )
      ).data;
    },

    revoke: async (shareLinkId: string): Promise<void> => {
      await this.transport.request(
        { method: 'POST', path: `/api/v1/share-links/${shareLinkId}/revoke` },
        VoidSchema,
      );
    },

    publicGet: async (token: string): Promise<PublicShare> =>
      (
        await this.transport.request(
          { method: 'GET', path: `/api/v1/public/shares/${token}` },
          PublicShareSchema,
        )
      ).data,
  };

  // ── audit / api-keys / billing ────────────────────────────────────────────
  readonly audit = {
    list: async (orgSlug: string, filter: AuditFilter = {}): Promise<AuditPage> =>
      (
        await this.transport.request(
          {
            method: 'GET',
            path: `/api/v1/orgs/${orgSlug}/audit`,
            query: queryToParams(filter as Record<string, unknown>),
          },
          AuditPageSchema,
        )
      ).data,
  };

  readonly apiKeys = {
    list: async (orgSlug: string): Promise<ApiKey[]> =>
      (
        await this.transport.request(
          { method: 'GET', path: `/api/v1/orgs/${orgSlug}/api-keys` },
          ApiKeyListSchema,
        )
      ).data,

    create: async (
      orgSlug: string,
      req: CreateApiKeyRequest,
    ): Promise<CreateApiKeyResponse> => {
      const parsed = CreateApiKeyRequestSchema.parse(req);
      return (
        await this.transport.request(
          { method: 'POST', path: `/api/v1/orgs/${orgSlug}/api-keys`, body: parsed },
          CreateApiKeyResponseSchema,
        )
      ).data;
    },

    revoke: async (orgSlug: string, id: string): Promise<void> => {
      await this.transport.request(
        { method: 'POST', path: `/api/v1/orgs/${orgSlug}/api-keys/${id}/revoke` },
        VoidSchema,
      );
    },
  };

  readonly billing = {
    subscription: async (orgSlug: string): Promise<Billing> =>
      (
        await this.transport.request(
          { method: 'GET', path: `/api/v1/orgs/${orgSlug}/billing` },
          BillingSchema,
        )
      ).data,

    portalLink: async (orgSlug: string) => {
      const Schema = z.object({ url: z.url() });
      return (
        await this.transport.request(
          { method: 'POST', path: `/api/v1/orgs/${orgSlug}/billing/portal` },
          Schema,
        )
      ).data;
    },
  };

  readonly artifacts = {
    list: async (projectId: string) => {
      const { ListArtifactsResponseSchema } = await import('@baseflo/contracts');
      return (
        await this.transport.request(
          { method: 'GET', path: `/api/v1/projects/${projectId}/artifacts` },
          ListArtifactsResponseSchema,
        )
      ).data;
    },
    latest: async (projectId: string, artifactType: string) => {
      const { ArtifactSchema } = await import('@baseflo/contracts');
      return (
        await this.transport.request(
          {
            method: 'GET',
            path: `/api/v1/projects/${projectId}/artifacts/latest`,
            query: { artifact_type: artifactType },
          },
          ArtifactSchema,
        )
      ).data;
    },
  };

  readonly agents = {
    list: async (projectId: string) => {
      return (
        await this.transport.request(
          { method: 'GET', path: `/api/v1/projects/${projectId}/agents` },
          ListAgentsResponseSchema,
        )
      ).data;
    },

    getFeed: async (projectId: string, agentId?: string) => {
      return (
        await this.transport.request(
          {
            method: 'GET',
            path: `/api/v1/projects/${projectId}/agents/feed`,
            query: agentId ? { agent_id: agentId } : undefined,
          },
          GetAgentFeedResponseSchema,
        )
      ).data;
    },

    getTasks: async (projectId: string) => {
      return (
        await this.transport.request(
          { method: 'GET', path: `/api/v1/projects/${projectId}/agents/tasks` },
          GetAgentTasksResponseSchema,
        )
      ).data;
    },


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

function slugify(name: string): string {
  return (
    name
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-+|-+$/g, '')
      .slice(0, 60) || 'org'
  );
}

export function createGateway(config: GatewayConfig): Gateway {
  return new Gateway(config);
}
