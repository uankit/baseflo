#!/usr/bin/env node
import { Command } from "commander";
import { BaseflowApiError, BaseflowTransportError } from "@baseflo/sdk";
import { colors } from "./colors.js";
import { askCommand, refineCommand } from "./commands/ask.js";
import { loginCommand, logoutCommand, whoamiCommand } from "./commands/auth.js";
import { connectShopifyCommand, connectStripeCommand, connectSheetsCommand, connectorsListCommand, } from "./commands/connect.js";
import { devCommand } from "./commands/dev.js";
import { exportCommand } from "./commands/export.js";
import { orgsCreateCommand } from "./commands/orgs.js";
import { projectsCreateCommand, projectsGetCommand } from "./commands/projects.js";
const program = new Command();
program
    .name("baseflo")
    .description("Baseflo command-line client.")
    .version("0.1.0");
// ---------- Auth ----------
program
    .command("login")
    .description("Sign in via magic link.")
    .option("-e, --email <email>", "Skip the prompt and use this email.")
    .option("--base-url <url>", "API base URL (default: $BASEFLO_API_BASE_URL or http://localhost:8000).")
    .action(async (opts) => {
    await runWithErrorHandler(() => loginCommand(opts));
});
program
    .command("whoami")
    .description("Print the active session and tenant context.")
    .action(async () => {
    await runWithErrorHandler(() => whoamiCommand());
});
program
    .command("logout")
    .description("Revoke the session and clear local credentials.")
    .action(async () => {
    await runWithErrorHandler(() => logoutCommand());
});
// ---------- Orgs ----------
program
    .command("orgs:create <slug>")
    .description("Bootstrap a new organization (becomes active).")
    .option("-n, --name <name>", "Display name (defaults to <slug>).")
    .action(async (slug, opts) => {
    await runWithErrorHandler(() => orgsCreateCommand(slug, opts));
});
// ---------- Projects ----------
program
    .command("projects:create <slug>")
    .description("Create a project under the active organization.")
    .option("-n, --name <name>", "Display name.")
    .option("-d, --description <text>", "One-line description.")
    .option("--deployment-mode <mode>", "hosted | byo_db | self_host | local_dev (default: hosted).")
    .action(async (slug, opts) => {
    await runWithErrorHandler(() => projectsCreateCommand(slug, opts));
});
program
    .command("projects:get <id>")
    .description("Print one project's details.")
    .action(async (id) => {
    await runWithErrorHandler(() => projectsGetCommand(id));
});
// ---------- Connectors ----------
const connect = program
    .command("connect")
    .description("Install a connector for the active project.");
connect
    .command("shopify")
    .description("Print a Shopify install URL (open in browser).")
    .requiredOption("--shop-domain <domain>", "e.g. acme.myshopify.com")
    .option("--project-id <uuid>", "Override the active project.")
    .action(async (opts) => {
    await runWithErrorHandler(() => connectShopifyCommand(opts));
});
connect
    .command("stripe")
    .description("Install a Stripe connector by validating an API key.")
    .requiredOption("--api-key <key>", "Restricted or secret Stripe API key (sk_... or rk_...).")
    .option("--project-id <uuid>", "Override the active project.")
    .action(async (opts) => {
    await runWithErrorHandler(() => connectStripeCommand(opts));
});
connect
    .command("sheets")
    .description("Print a Google Sheets install URL (open in browser).")
    .requiredOption("--spreadsheet-id <id>", "Google spreadsheet id.")
    .option("--project-id <uuid>", "Override the active project.")
    .action(async (opts) => {
    await runWithErrorHandler(() => connectSheetsCommand(opts));
});
program
    .command("connectors:list")
    .description("List installed connectors.")
    .option("--project-id <uuid>", "Filter to one project.")
    .action(async (opts) => {
    await runWithErrorHandler(() => connectorsListCommand(opts));
});
// ---------- Conversations + refinements ----------
program
    .command("ask <prompt>")
    .description("Open a conversation and stream agent events to your terminal.")
    .option("--project-id <uuid>", "Override the active project.")
    .action(async (prompt, opts) => {
    await runWithErrorHandler(() => askCommand(prompt, opts));
});
program
    .command("refine <request>")
    .description("Run a refinement saga in plain English.")
    .option("--project-id <uuid>", "Override the active project.")
    .action(async (request, opts) => {
    await runWithErrorHandler(() => refineCommand(request, opts));
});
// ---------- Export ----------
program
    .command("export [project-id]")
    .description("Download the project's export tarball (IR + KPIs + DDL + rows).")
    .option("--out <path>", "Output file path.")
    .action(async (projectIdArg, opts) => {
    await runWithErrorHandler(() => exportCommand(projectIdArg, opts));
});
// ---------- Dev ----------
program
    .command("dev")
    .description("Start local Postgres + Redis from docker-compose.dev.yml.")
    .option("--compose-file <path>", "Path to docker-compose file.")
    .action(async (opts) => {
    await runWithErrorHandler(() => devCommand(opts));
});
program.parseAsync(process.argv).catch((err) => {
    console.error(colors.red("✗") + " " + err.message);
    process.exitCode = 1;
});
// ---------- Error handler ----------
async function runWithErrorHandler(fn) {
    try {
        await fn();
    }
    catch (err) {
        if (err instanceof BaseflowApiError) {
            console.error(colors.red("✗") +
                ` API error [${err.errorCode}] ` +
                colors.dim(`(HTTP ${err.status})`));
            console.error("  " + err.body.message);
            if (err.body.request_id) {
                console.error(colors.dim(`  request_id: ${err.body.request_id}`));
            }
        }
        else if (err instanceof BaseflowTransportError) {
            console.error(colors.red("✗") + " " + err.message);
        }
        else if (err instanceof Error) {
            console.error(colors.red("✗") + " " + err.message);
        }
        else {
            console.error(colors.red("✗") + " " + String(err));
        }
        process.exitCode = 1;
    }
}
//# sourceMappingURL=index.js.map