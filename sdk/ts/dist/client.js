import { BaseflowApiError, BaseflowTransportError } from "./errors.js";
import { parseSseStream } from "./sse.js";
export class BaseflowClient {
    baseUrl;
    fetchFn;
    timeoutMs;
    token;
    activeOrg;
    constructor(opts) {
        this.baseUrl = opts.baseUrl.replace(/\/+$/, "");
        this.fetchFn = opts.fetch ?? fetch;
        this.token = opts.token;
        this.activeOrg = opts.activeOrg;
        this.timeoutMs = opts.timeoutMs ?? 30_000;
    }
    /** Update the session/api-key token after construction. */
    setToken(token) {
        this.token = token;
    }
    /** Update the active org for subsequent requests. */
    setActiveOrg(slug) {
        this.activeOrg = slug;
    }
    // ---------- Auth ----------
    auth = {
        requestMagicLink: (email) => this.request("POST", "/auth/magic-link/request", {
            json: { email },
            auth: false,
        }),
        /**
         * Verify a magic-link token and return the raw `Set-Cookie` header so the
         * caller can persist the session. Server normally redirects to `/`; we
         * stop the redirect to capture the cookie.
         */
        verifyMagicLink: async (token) => {
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
        me: () => this.request("GET", "/auth/me"),
        signout: () => this.request("POST", "/auth/signout", { expectStatus: 204 }),
    };
    // ---------- Orgs + projects ----------
    orgs = {
        create: (body) => this.request("POST", "/orgs", { json: body }),
    };
    projects = {
        create: (body) => this.request("POST", "/projects", { json: body }),
        get: (id) => this.request("GET", `/projects/${encodeURIComponent(id)}`),
    };
    // ---------- Connectors ----------
    connectors = {
        list: (opts = {}) => this.request("GET", "/connectors", opts.projectId ? { query: { project_id: opts.projectId } } : {}),
        get: (id) => this.request("GET", `/connectors/${encodeURIComponent(id)}`),
        shopify: {
            installUrl: (params) => this.request("GET", "/oauth/shopify/install", {
                query: {
                    project_id: params.projectId,
                    shop_domain: params.shopDomain,
                },
            }),
        },
        googleSheets: {
            installUrl: (params) => this.request("GET", "/oauth/google_sheets/install", {
                query: {
                    project_id: params.projectId,
                    spreadsheet_id: params.spreadsheetId,
                },
            }),
        },
        stripe: {
            install: (body) => this.request("POST", "/connectors/stripe/install", { json: body, expectStatus: 201 }),
        },
    };
    // ---------- Conversations + SSE ----------
    conversations = {
        create: (body) => this.request("POST", "/conversations", {
            json: body,
        }),
        sendMessage: (conversationId, content) => this.request("POST", `/conversations/${encodeURIComponent(conversationId)}/messages`, { json: { content } }),
        /**
         * Stream events for a conversation. Yields each event as it arrives.
         * Pass `lastEventId` to resume from a specific sequence number.
         */
        events: (conversationId, opts = {}) => this._streamEvents(conversationId, opts),
    };
    async *_streamEvents(conversationId, opts = {}) {
        const url = this.url(`/conversations/${encodeURIComponent(conversationId)}/events`);
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
    refinements = {
        create: (projectId, body) => this.request("POST", `/projects/${encodeURIComponent(projectId)}/refinements`, { json: body }),
    };
    // ---------- Exports ----------
    exports = {
        /** Returns raw gzipped tarball bytes. */
        create: async (projectId) => {
            const url = this.url(`/projects/${encodeURIComponent(projectId)}/exports`);
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
    url(path, query) {
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
    headers() {
        const h = { Accept: "application/json" };
        if (this.token !== undefined) {
            // The session token is normally in a cookie; for CLI we send it as
            // a `Cookie` header so node-fetch doesn't need a cookie jar.
            if (this.token.startsWith("baseflo_")) {
                h["Authorization"] = `Bearer ${this.token}`;
            }
            else {
                h["Cookie"] = `baseflo_session=${this.token}`;
            }
        }
        return h;
    }
    async request(method, path, opts = {}) {
        const headers = this.headers();
        const init = {
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
        let response;
        try {
            response = await this.fetchFn(this.url(path, opts.query), init);
        }
        catch (err) {
            throw new BaseflowTransportError(`Network error contacting ${this.baseUrl}: ${err.message}`, err);
        }
        finally {
            clearTimeout(timeout);
        }
        if (opts.expectStatus !== undefined) {
            if (response.status !== opts.expectStatus) {
                throw await BaseflowClient.toApiErrorStatic(response);
            }
            // 204 / 201 with no body
            if (response.status === 204) {
                return undefined;
            }
        }
        else if (response.status >= 400) {
            throw await BaseflowClient.toApiErrorStatic(response);
        }
        if (response.status === 204) {
            return undefined;
        }
        const text = await response.text();
        if (!text) {
            return undefined;
        }
        return JSON.parse(text);
    }
    async toApiError(response) {
        return BaseflowClient.toApiErrorStatic(response);
    }
    static async toApiErrorStatic(response) {
        let body;
        try {
            body = (await response.json());
        }
        catch {
            body = {
                error_code: "BF-API-UNKNOWN",
                message: `HTTP ${response.status}`,
            };
        }
        return new BaseflowApiError(response.status, body);
    }
}
//# sourceMappingURL=client.js.map