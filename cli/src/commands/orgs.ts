import { type Credentials, loadCredentials, saveCredentials } from "../credentials.js";
import { buildClient } from "../client.js";
import { colors } from "../colors.js";

export async function orgsCreateCommand(
  slug: string,
  opts: { name?: string },
): Promise<void> {
  const client = buildClient({ requireAuth: true });
  const result = await client.orgs.create({
    name: opts.name ?? slug,
    slug,
  });
  console.log(colors.green("✓") + ` Organization "${result.slug}" created.`);
  console.log(colors.dim(`  organization_id  ${result.organization_id}`));
  console.log(colors.dim(`  workspace_id     ${result.workspace_id} (Default)`));
  console.log(colors.dim(`  role             ${result.role}`));

  // Persist as active org so subsequent commands resolve correctly.
  const creds = loadCredentials();
  if (creds) {
    const next: Credentials = { ...creds, activeOrg: slug };
    saveCredentials(next);
    console.log(colors.dim(`  active_org       ${slug} (saved)`));
  }
}
