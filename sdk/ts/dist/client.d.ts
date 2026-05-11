import type { ConnectorInstallResult, ConnectorListResponse, ConnectorSummary, CreateConversationRequest, CreateOrgRequest, CreateOrgResponse, CreateProjectRequest, CreateProjectResponse, JobAccepted, MagicLinkResponse, MeResponse, MessageResponse, OAuthInstallResponse, ProjectSummary, RefinementRequest, RefinementResult, SSEEvent, StripeInstallRequest, UUID } from "./types.js";
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
export declare class BaseflowClient {
    readonly baseUrl: string;
    private readonly fetchFn;
    private readonly timeoutMs;
    private token;
    private activeOrg;
    constructor(opts: BaseflowClientOptions);
    /** Update the session/api-key token after construction. */
    setToken(token: string | undefined): void;
    /** Update the active org for subsequent requests. */
    setActiveOrg(slug: string | undefined): void;
    readonly auth: {
        requestMagicLink: (email: string) => Promise<MagicLinkResponse>;
        /**
         * Verify a magic-link token and return the raw `Set-Cookie` header so the
         * caller can persist the session. Server normally redirects to `/`; we
         * stop the redirect to capture the cookie.
         */
        verifyMagicLink: (token: string) => Promise<{
            cookie: string;
        }>;
        me: () => Promise<MeResponse>;
        signout: () => Promise<void>;
    };
    readonly orgs: {
        create: (body: CreateOrgRequest) => Promise<CreateOrgResponse>;
    };
    readonly projects: {
        create: (body: CreateProjectRequest) => Promise<CreateProjectResponse>;
        get: (id: UUID) => Promise<ProjectSummary>;
    };
    readonly connectors: {
        list: (opts?: {
            projectId?: UUID;
        }) => Promise<ConnectorListResponse>;
        get: (id: UUID) => Promise<ConnectorSummary>;
        shopify: {
            installUrl: (params: {
                projectId: UUID;
                shopDomain: string;
            }) => Promise<OAuthInstallResponse>;
        };
        googleSheets: {
            installUrl: (params: {
                projectId: UUID;
                spreadsheetId: string;
            }) => Promise<OAuthInstallResponse>;
        };
        stripe: {
            install: (body: StripeInstallRequest) => Promise<ConnectorInstallResult>;
        };
    };
    readonly conversations: {
        create: (body: CreateConversationRequest) => Promise<JobAccepted>;
        sendMessage: (conversationId: UUID, content: string) => Promise<MessageResponse>;
        /**
         * Stream events for a conversation. Yields each event as it arrives.
         * Pass `lastEventId` to resume from a specific sequence number.
         */
        events: (conversationId: UUID, opts?: {
            lastEventId?: string;
        }) => AsyncIterable<SSEEvent>;
    };
    private _streamEvents;
    readonly refinements: {
        create: (projectId: UUID, body: RefinementRequest) => Promise<RefinementResult>;
    };
    readonly exports: {
        /** Returns raw gzipped tarball bytes. */
        create: (projectId: UUID) => Promise<ArrayBuffer>;
    };
    private url;
    private headers;
    private request;
    private toApiError;
    private static toApiErrorStatic;
}
//# sourceMappingURL=client.d.ts.map