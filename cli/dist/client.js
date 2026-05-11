import { BaseflowClient } from "@baseflo/sdk";
import { loadCredentials } from "./credentials.js";
export function buildClient(opts = {}) {
    const creds = loadCredentials();
    const baseUrl = opts.baseUrl ??
        creds?.baseUrl ??
        process.env.BASEFLO_API_BASE_URL ??
        "http://localhost:8000";
    const init = { baseUrl };
    if (creds?.sessionToken)
        init.token = creds.sessionToken;
    if (creds?.activeOrg)
        init.activeOrg = creds.activeOrg;
    if (opts.requireAuth && !creds?.sessionToken) {
        throw new Error("Not signed in. Run `baseflo login` first.");
    }
    return new BaseflowClient(init);
}
export function activeProjectIdOrThrow(explicit) {
    if (explicit)
        return explicit;
    const creds = loadCredentials();
    if (!creds?.activeProjectId) {
        throw new Error("No active project set. Pass --project-id <uuid> or run `baseflo projects:create` first.");
    }
    return creds.activeProjectId;
}
//# sourceMappingURL=client.js.map