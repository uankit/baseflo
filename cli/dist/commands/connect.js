import { activeProjectIdOrThrow, buildClient } from "../client.js";
import { colors } from "../colors.js";
export async function connectShopifyCommand(opts) {
    const client = buildClient({ requireAuth: true });
    const projectId = activeProjectIdOrThrow(opts.projectId);
    const install = await client.connectors.shopify.installUrl({
        projectId,
        shopDomain: opts.shopDomain,
    });
    console.log(colors.bold("Open this URL in a browser to authorize Shopify:"));
    console.log("");
    console.log("  " + colors.cyan(install.redirect_url));
    console.log("");
    console.log(colors.dim("  After granting access, Shopify redirects to /api/v1/oauth/shopify/callback. " +
        "We'll persist the encrypted token automatically."));
}
export async function connectStripeCommand(opts) {
    const client = buildClient({ requireAuth: true });
    const projectId = activeProjectIdOrThrow(opts.projectId);
    const result = await client.connectors.stripe.install({
        project_id: projectId,
        api_key: opts.apiKey,
    });
    console.log(colors.green("✓") + " Stripe connector installed.");
    console.log(colors.dim(`  connector_id  ${result.connector_id}`));
    console.log(colors.dim(`  account_id    ${result.account_id ?? "—"}`));
}
export async function connectSheetsCommand(opts) {
    const client = buildClient({ requireAuth: true });
    const projectId = activeProjectIdOrThrow(opts.projectId);
    const install = await client.connectors.googleSheets.installUrl({
        projectId,
        spreadsheetId: opts.spreadsheetId,
    });
    console.log(colors.bold("Open this URL in a browser to authorize Google Sheets:"));
    console.log("");
    console.log("  " + colors.cyan(install.redirect_url));
    console.log("");
    console.log(colors.dim("  After granting `spreadsheets` + `drive.metadata.readonly`, Google " +
        "redirects to /api/v1/oauth/google_sheets/callback."));
}
export async function connectorsListCommand(opts) {
    const client = buildClient({ requireAuth: true });
    const list = await client.connectors.list(opts.projectId !== undefined ? { projectId: opts.projectId } : {});
    if (list.connectors.length === 0) {
        console.log(colors.dim("No connectors installed."));
        return;
    }
    for (const c of list.connectors) {
        console.log(`${colors.bold(c.kind.padEnd(15))} ${colors.dim(c.id)} ${colors.cyan(c.display_name)} ` +
            `${colors.dim(`status=${c.status}`)}`);
    }
}
//# sourceMappingURL=connect.js.map