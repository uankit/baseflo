import { BaseflowClient, type BaseflowClientOptions } from "@baseflo/sdk";

import { loadCredentials } from "./credentials.js";

export interface CliClientOptions {
  /** Override base URL — falls back to `BASEFLO_API_BASE_URL`, then localhost. */
  baseUrl?: string;
  /**
   * If true, requires a saved session token. Throws when missing.
   * Default false (lets `login` work without prior auth).
   */
  requireAuth?: boolean;
}

export function buildClient(opts: CliClientOptions = {}): BaseflowClient {
  const creds = loadCredentials();
  const baseUrl =
    opts.baseUrl ??
    creds?.baseUrl ??
    process.env.BASEFLO_API_BASE_URL ??
    "http://localhost:8000";
  const init: BaseflowClientOptions = { baseUrl };
  if (creds?.sessionToken) init.token = creds.sessionToken;
  if (creds?.activeOrg) init.activeOrg = creds.activeOrg;
  if (opts.requireAuth && !creds?.sessionToken) {
    throw new Error("Not signed in. Run `baseflo login` first.");
  }
  return new BaseflowClient(init);
}

export function activeProjectIdOrThrow(explicit: string | undefined): string {
  if (explicit) return explicit;
  const creds = loadCredentials();
  if (!creds?.activeProjectId) {
    throw new Error(
      "No active project set. Pass --project-id <uuid> or run `baseflo projects:create` first.",
    );
  }
  return creds.activeProjectId;
}
