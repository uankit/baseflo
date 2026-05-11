import { BaseflowApiError, BaseflowClient } from "@baseflo/sdk";
import { createInterface } from "node:readline/promises";
import { clearCredentials, credentialsPath, loadCredentials, saveCredentials, } from "../credentials.js";
import { colors } from "../colors.js";
import { buildClient } from "../client.js";
export async function loginCommand(opts) {
    const baseUrl = opts.baseUrl ?? process.env.BASEFLO_API_BASE_URL ?? "http://localhost:8000";
    const rl = createInterface({ input: process.stdin, output: process.stdout });
    try {
        const email = opts.email ?? (await rl.question("Email: "));
        if (!email.includes("@")) {
            throw new Error(`That doesn't look like an email: ${email}`);
        }
        const client = new BaseflowClient({ baseUrl });
        const issued = await client.auth.requestMagicLink(email);
        console.log(colors.green("✓") + " Magic link sent.");
        console.log(colors.dim("  In dev (LogEmailSender), the link is in the server's stdout. " +
            "Paste the `token=` value from the URL."));
        if (issued.expires_at) {
            console.log(colors.dim(`  Expires at ${issued.expires_at}.`));
        }
        const token = (await rl.question("Token: ")).trim();
        if (!token) {
            throw new Error("No token entered.");
        }
        const verified = await client.auth.verifyMagicLink(token);
        const sessionToken = parseSessionTokenFromCookie(verified.cookie);
        if (!sessionToken) {
            throw new Error("Verify endpoint did not return a session cookie. " +
                "Check that the server's auth middleware is installed.");
        }
        const creds = { baseUrl, sessionToken, email };
        saveCredentials(creds);
        console.log(colors.green("✓") + ` Signed in as ${email}.`);
        console.log(colors.dim(`  Credentials saved to ${credentialsPath()}.`));
        // Pre-fetch /me so the user sees their org/role immediately.
        const me = await buildClient({ baseUrl }).auth.me().catch(() => null);
        if (me) {
            console.log(colors.dim(`  org_id=${me.organization_id} role=${me.role ?? "—"}`));
        }
        else {
            console.log(colors.yellow("!") +
                " You're signed in but have no organization yet. Run " +
                colors.cyan("`baseflo orgs:create <slug>`") +
                " to bootstrap one.");
        }
    }
    finally {
        rl.close();
    }
}
export async function whoamiCommand() {
    const client = buildClient({ requireAuth: true });
    try {
        const me = await client.auth.me();
        const creds = loadCredentials();
        console.log(colors.bold("user_id") + `        ${me.user_id}`);
        console.log(colors.bold("email") + `          ${creds?.email ?? "—"}`);
        console.log(colors.bold("organization") + `   ${me.organization_id} (role=${me.role ?? "—"})`);
        console.log(colors.bold("session_id") + `     ${me.session_id ?? "—"}`);
        console.log(colors.bold("base_url") + `       ${client.baseUrl}`);
    }
    catch (err) {
        if (err instanceof BaseflowApiError && err.status === 401) {
            console.error(colors.red("Not signed in.") + " Run " + colors.cyan("`baseflo login`."));
            process.exitCode = 1;
            return;
        }
        throw err;
    }
}
export async function logoutCommand() {
    const client = buildClient();
    await client.auth.signout().catch(() => {
        // Ignore — signout is best-effort; we still wipe local creds.
    });
    clearCredentials();
    console.log(colors.green("✓") + " Signed out. Credentials cleared.");
}
/** Extract the value of `baseflo_session=...` from a Set-Cookie header. */
function parseSessionTokenFromCookie(setCookie) {
    const match = setCookie.match(/baseflo_session=([^;]+)/);
    return match ? match[1] ?? null : null;
}
//# sourceMappingURL=auth.js.map