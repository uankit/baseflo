import { describe, expect, it, vi } from "vitest";

import { BaseflowApiError, BaseflowClient } from "./index.js";

describe("BaseflowClient", () => {
  const baseUrl = "http://test.local";

  function mockFetch(handler: (req: Request) => Response | Promise<Response>): typeof fetch {
    return vi.fn(async (input, init) => {
      const url = typeof input === "string" ? input : input.toString();
      const request = new Request(url, init);
      return await handler(request);
    }) as unknown as typeof fetch;
  }

  it("requestMagicLink POSTs the email body and returns the typed response", async () => {
    let captured: Request | null = null;
    const fetchFn = mockFetch(async (req) => {
      captured = req;
      return new Response(
        JSON.stringify({ accepted: true, expires_at: "2026-05-07T12:15:00+00:00" }),
        { status: 202, headers: { "content-type": "application/json" } },
      );
    });
    const client = new BaseflowClient({ baseUrl, fetch: fetchFn });
    const result = await client.auth.requestMagicLink("alice@example.com");

    expect(result.accepted).toBe(true);
    expect(captured).not.toBeNull();
    expect(captured!.method).toBe("POST");
    expect(captured!.url).toBe(`${baseUrl}/api/v1/auth/magic-link/request`);
    expect(await captured!.json()).toEqual({ email: "alice@example.com" });
  });

  it("sends the session cookie header when a token is set", async () => {
    let captured: Request | null = null;
    const fetchFn = mockFetch(async (req) => {
      captured = req;
      return new Response(
        JSON.stringify({
          user_id: "00000000-0000-0000-0000-000000000001",
          organization_id: "00000000-0000-0000-0000-000000000002",
          role: "owner",
          session_id: "00000000-0000-0000-0000-000000000003",
          is_api_key: false,
        }),
        { status: 200, headers: { "content-type": "application/json" } },
      );
    });
    const client = new BaseflowClient({
      baseUrl,
      fetch: fetchFn,
      token: "raw-session-token-xxx",
    });

    const me = await client.auth.me();
    expect(me.role).toBe("owner");
    expect(captured!.headers.get("cookie")).toBe(
      "baseflo_session=raw-session-token-xxx",
    );
  });

  it("uses Authorization header when the token looks like an api-key", async () => {
    let captured: Request | null = null;
    const fetchFn = mockFetch(async (req) => {
      captured = req;
      return new Response(
        JSON.stringify({
          user_id: "00000000-0000-0000-0000-000000000001",
          organization_id: "00000000-0000-0000-0000-000000000002",
          role: null,
          session_id: null,
          is_api_key: true,
        }),
        { status: 200, headers: { "content-type": "application/json" } },
      );
    });
    const client = new BaseflowClient({
      baseUrl,
      fetch: fetchFn,
      token: "baseflo_abc123_xyz",
    });

    await client.auth.me();
    expect(captured!.headers.get("authorization")).toBe(
      "Bearer baseflo_abc123_xyz",
    );
  });

  it("throws BaseflowApiError with typed body on 4xx", async () => {
    const fetchFn = mockFetch(
      async () =>
        new Response(
          JSON.stringify({
            error_code: "BF-AUTH-001",
            message: "Authentication required.",
          }),
          { status: 401, headers: { "content-type": "application/json" } },
        ),
    );
    const client = new BaseflowClient({ baseUrl, fetch: fetchFn });

    await expect(client.auth.me()).rejects.toMatchObject({
      status: 401,
      errorCode: "BF-AUTH-001",
    });
  });

  it("createOrg POSTs the body and returns the typed response", async () => {
    let captured: Request | null = null;
    const fetchFn = mockFetch(async (req) => {
      captured = req;
      return new Response(
        JSON.stringify({
          organization_id: "00000000-0000-0000-0000-000000000010",
          workspace_id: "00000000-0000-0000-0000-000000000011",
          membership_id: "00000000-0000-0000-0000-000000000012",
          slug: "acme",
          role: "owner",
        }),
        { status: 201, headers: { "content-type": "application/json" } },
      );
    });
    const client = new BaseflowClient({
      baseUrl,
      fetch: fetchFn,
      token: "session-x",
    });

    const result = await client.orgs.create({ name: "Acme", slug: "acme" });
    expect(result.slug).toBe("acme");
    expect(captured!.method).toBe("POST");
    expect(captured!.url).toBe(`${baseUrl}/api/v1/orgs`);
  });

  it("connectors.list adds project_id query when supplied", async () => {
    let capturedUrl = "";
    const fetchFn = mockFetch(async (req) => {
      capturedUrl = req.url;
      return new Response(JSON.stringify({ connectors: [] }), {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    });
    const client = new BaseflowClient({
      baseUrl,
      fetch: fetchFn,
      token: "session-x",
    });
    await client.connectors.list({
      projectId: "00000000-0000-0000-0000-000000000020",
    });
    expect(capturedUrl).toContain(
      "project_id=00000000-0000-0000-0000-000000000020",
    );
  });

  it("activeOrg propagates as ?org= on every request", async () => {
    let capturedUrl = "";
    const fetchFn = mockFetch(async (req) => {
      capturedUrl = req.url;
      return new Response(JSON.stringify({ connectors: [] }), {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    });
    const client = new BaseflowClient({
      baseUrl,
      fetch: fetchFn,
      token: "session-x",
      activeOrg: "acme",
    });
    await client.connectors.list();
    expect(capturedUrl).toContain("org=acme");
  });

  it("conversations.create posts the initial content and returns JobAccepted", async () => {
    let captured: Request | null = null;
    const fetchFn = mockFetch(async (req) => {
      captured = req;
      return new Response(
        JSON.stringify({
          job_id: "00000000-0000-0000-0000-000000000030",
          conversation_id: "00000000-0000-0000-0000-000000000031",
          status: "queued",
          sse_url: "/api/v1/conversations/00000000-0000-0000-0000-000000000031/events",
        }),
        { status: 202, headers: { "content-type": "application/json" } },
      );
    });
    const client = new BaseflowClient({
      baseUrl,
      fetch: fetchFn,
      token: "session-x",
    });

    const result = await client.conversations.create({
      project_id: "00000000-0000-0000-0000-000000000020",
      content: "Build the alpha workspace",
    });

    expect(result.conversation_id).toBe("00000000-0000-0000-0000-000000000031");
    expect(captured!.method).toBe("POST");
    expect(captured!.url).toBe(`${baseUrl}/api/v1/conversations`);
    expect(await captured!.json()).toEqual({
      project_id: "00000000-0000-0000-0000-000000000020",
      content: "Build the alpha workspace",
    });
  });
});
