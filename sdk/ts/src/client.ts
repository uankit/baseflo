import { BaseflowApiError, BaseflowTransportError } from "./errors.js";
import { parseSseStream } from "./sse.js";
import type {
  ConnectorInstallResult,
  ConnectorListResponse,
  ConnectorSummary,
  CreateConversationRequest,
  CreateOrgRequest,
  CreateOrgResponse,
  CreateProjectRequest,
  CreateProjectResponse,
  ErrorBody,
  JobAccepted,
  MagicLinkResponse,
  MeResponse,
  MessageResponse,
  OAuthInstallResponse,
  ProjectSummary,
  RefinementRequest,
  RefinementResult,
  SSEEvent,
  StripeInstallRequest,
  UUID,
} from "./types.js";

export interface BaseflowClientOptions {
  /**
   * API base URL, e.g. `https://api.baseflo.com` or `http://localhost:8000`.
   * The SDK appends `/api/v1/...` paths internally.
   */
  baseUrl: string;
  /**
   * Session token for cookie auth, or an API key (`baseflo_<prefix>_<secret>`)
   * for programmatic access. Optional — public endpoints (magic-link request)
   * don't need it.
   */
  token?: string;
  /**
   * Override fetch (for tests). Defaults to global `fetch`.
   */
  fetch?: typeof fetch;
  /**
   * Active org slug or UUID. Sent as `?org=...` on requests; the server's
   * resolver picks the matching membership.
   */
  activeOrg?: string;
  /** Default request timeout in ms. */
  timeoutMs?: number;
}

export class BaseflowClient {
  readonly baseUrl: string;
  private readonly fetchFn: typeof fetch;
  private readonly timeoutMs: number;
  private token: string | undefined;
  private activeOrg: string | undefined;

  constructor(opts: BaseflowClientOptions) {
    this.baseUrl = opts.baseUrl.replace(/\/+$/, "");
    this.fetchFn = opts.fetch ?? fetch;
    this.token = opts.token;
    this.activeOrg = opts.activeOrg;
    this.timeoutMs = opts.timeoutMs ?? 30_000;
  }

  /** Update the session/api-key token after construction. */
  setToken(token: string | undefined): void {
    this.token = token;
  }

  /** Update the active org for subsequent requests. */
  setActiveOrg(slug: string | undefined): void {
    this.activeOrg = slug;
  }

  // ---------- Auth ----------

  readonly auth = {
    requestMagicLink: (email: string): Promise<MagicLinkResponse> =>
      this.request<MagicLinkResponse>("POST", "/auth/magic-link/request", {
        json: { email },
        auth: false,
      }),
    /**
     * Verify a magic-link token and return the raw `Set-Cookie` header so the
     * caller can persist the session. Server normally redirects to `/`; we
     * stop the redirect to capture the cookie.
     */
    verifyMagicLink: async (token: string): Promise<{ cookie: string }> => {
      const url = this.url("/auth/magic-link/verify", { token });
      const response = await this.fetchFn(url, {
        method: "GET",
        redirect: "manual",
      });
      const setCookie = response.headers.get("set-cookie");
      if (response.status >= 400 || !setCookie) {
        throw await this.toApiError(response);
      }
      return { cookie: setCookie };
    },
    me: (): Promise<MeResponse> =>
      this.request<MeResponse>("GET", "/auth/me"),
    signout: (): Promise<void> =>
      this.request<void>("POST", "/auth/signout", { expectStatus: 204 }),
  };

  // ---------- Orgs + projects ----------

  readonly orgs = {
    create: (body: CreateOrgRequest): Promise<CreateOrgResponse> =>
      this.request<CreateOrgResponse>("POST", "/orgs", { json: body }),
  };

  readonly projects = {
    create: (body: CreateProjectRequest): Promise<CreateProjectResponse> =>
      this.request<CreateProjectResponse>("POST", "/projects", { json: body }),
    get: (id: UUID): Promise<ProjectSummary> =>
      this.request<ProjectSummary>("GET", `/projects/${encodeURIComponent(id)}`),
  };

  // ---------- Connectors ----------

  readonly connectors = {
    list: (opts: { projectId?: UUID } = {}): Promise<ConnectorListResponse> =>
      this.request<ConnectorListResponse>(
        "GET",
        "/connectors",
        opts.projectId ? { query: { project_id: opts.projectId } } : {},
      ),
    get: (id: UUID): Promise<ConnectorSummary> =>
      this.request<ConnectorSummary>(
        "GET",
        `/connectors/${encodeURIComponent(id)}`,
      ),
    shopify: {
      installUrl: (params: {
        projectId: UUID;
        shopDomain: string;
      }): Promise<OAuthInstallResponse> =>
        this.request<OAuthInstallResponse>(
          "GET",
          "/oauth/shopify/install",
          {
            query: {
              project_id: params.projectId,
              shop_domain: params.shopDomain,
            },
          },
        ),
    },
    googleSheets: {
      installUrl: (params: {
        projectId: UUID;
        spreadsheetId: string;
      }): Promise<OAuthInstallResponse> =>
        this.request<OAuthInstallResponse>(
          "GET",
          "/oauth/google_sheets/install",
          {
            query: {
              project_id: params.projectId,
              spreadsheet_id: params.spreadsheetId,
            },
          },
        ),
    },
    stripe: {
      install: (body: StripeInstallRequest): Promise<ConnectorInstallResult> =>
        this.request<ConnectorInstallResult>(
          "POST",
          "/connectors/stripe/install",
          { json: body, expectStatus: 201 },
        ),
    },
  };

  // ---------- Conversations + SSE ----------

  readonly conversations = {
    create: (body: CreateConversationRequest): Promise<JobAccepted> =>
      this.request<JobAccepted>("POST", "/conversations", {
        json: body,
      }),
    sendMessage: (
      conversationId: UUID,
      content: string,
    ): Promise<MessageResponse> =>
      this.request<MessageResponse>(
        "POST",
        `/conversations/${encodeURIComponent(conversationId)}/messages`,
        { json: { content } },
      ),
    /**
     * Stream events for a conversation. Yields each event as it arrives.
     * Pass `lastEventId` to resume from a specific sequence number.
     */
    events: (
      conversationId: UUID,
      opts: { lastEventId?: string } = {},
    ): AsyncIterable<SSEEvent> => this._streamEvents(conversationId, opts),
  };

  private async *_streamEvents(
    conversationId: UUID,
    opts: { lastEventId?: string } = {},
  ): AsyncIterable<SSEEvent> {
    const url = this.url(
      `/conversations/${encodeURIComponent(conversationId)}/events`,
    );
    const headers = this.headers();
    headers["Accept"] = "text/event-stream";
    if (opts.lastEventId !== undefined) {
      headers["Last-Event-ID"] = opts.lastEventId;
    }
    const response = await this.fetchFn(url, { method: "GET", headers });
    if (response.status >= 400) {
      throw await BaseflowClient.toApiErrorStatic(response);
    }
    yield* parseSseStream(response);
  }

  // ---------- Refinements ----------

  readonly refinements = {
    create: (
      projectId: UUID,
      body: RefinementRequest,
    ): Promise<RefinementResult> =>
      this.request<RefinementResult>(
        "POST",
        `/projects/${encodeURIComponent(projectId)}/refinements`,
        { json: body },
      ),
  };

  // ---------- Exports ----------

  readonly exports = {
    /** Returns raw gzipped tarball bytes. */
    create: async (projectId: UUID): Promise<ArrayBuffer> => {
      const url = this.url(
        `/projects/${encodeURIComponent(projectId)}/exports`,
      );
      const response = await this.fetchFn(url, {
        method: "POST",
        headers: this.headers(),
      });
      if (response.status >= 400) {
        throw await BaseflowClient.toApiErrorStatic(response);
      }
      return await response.arrayBuffer();
    },
  };

  // ---------- HTTP plumbing ----------

  private url(path: string, query?: Record<string, string>): string {
    const url = new URL(this.baseUrl + "/api/v1" + path);
    const merged = { ...query };
    if (this.activeOrg !== undefined && !("org" in merged)) {
      merged.org = this.activeOrg;
    }
    for (const [k, v] of Object.entries(merged)) {
      url.searchParams.set(k, v);
    }
    return url.toString();
  }

  private headers(): Record<string, string> {
    const h: Record<string, string> = { Accept: "application/json" };
    if (this.token !== undefined) {
      // The session token is normally in a cookie; for CLI we send it as
      // a `Cookie` header so node-fetch doesn't need a cookie jar.
      if (this.token.startsWith("baseflo_")) {
        h["Authorization"] = `Bearer ${this.token}`;
      } else {
        h["Cookie"] = `baseflo_session=${this.token}`;
      }
    }
    return h;
  }

  private async request<T>(
    method: string,
    path: string,
    opts: {
      query?: Record<string, string>;
      json?: unknown;
      auth?: boolean;
      expectStatus?: number;
    } = {},
  ): Promise<T> {
    const headers = this.headers();
    const init: RequestInit = {
      method,
      headers,
    };
    if (opts.json !== undefined) {
      headers["Content-Type"] = "application/json";
      init.body = JSON.stringify(opts.json);
    }

    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), this.timeoutMs);
    init.signal = controller.signal;

    let response: Response;
    try {
      response = await this.fetchFn(this.url(path, opts.query), init);
    } catch (err) {
      throw new BaseflowTransportError(
        `Network error contacting ${this.baseUrl}: ${(err as Error).message}`,
        err,
      );
    } finally {
      clearTimeout(timeout);
    }

    if (opts.expectStatus !== undefined) {
      if (response.status !== opts.expectStatus) {
        throw await BaseflowClient.toApiErrorStatic(response);
      }
      // 204 / 201 with no body
      if (response.status === 204) {
        return undefined as unknown as T;
      }
    } else if (response.status >= 400) {
      throw await BaseflowClient.toApiErrorStatic(response);
    }

    if (response.status === 204) {
      return undefined as unknown as T;
    }
    const text = await response.text();
    if (!text) {
      return undefined as unknown as T;
    }
    return JSON.parse(text) as T;
  }

  private async toApiError(response: Response): Promise<BaseflowApiError> {
    return BaseflowClient.toApiErrorStatic(response);
  }

  private static async toApiErrorStatic(
    response: Response,
  ): Promise<BaseflowApiError> {
    let body: ErrorBody;
    try {
      body = (await response.json()) as ErrorBody;
    } catch {
      body = {
        error_code: "BF-API-UNKNOWN",
        message: `HTTP ${response.status}`,
      };
    }
    return new BaseflowApiError(response.status, body);
  }
}
