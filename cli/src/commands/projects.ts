import { BaseflowApiError } from "@baseflo/sdk";

import { buildClient } from "../client.js";
import { colors } from "../colors.js";
import { type Credentials, loadCredentials, saveCredentials } from "../credentials.js";

export async function projectsCreateCommand(
  slug: string,
  opts: { name?: string; description?: string; deploymentMode?: string },
): Promise<void> {
  const client = buildClient({ requireAuth: true });
  const result = await client.projects.create({
    name: opts.name ?? slug,
    slug,
    ...(opts.description !== undefined ? { description: opts.description } : {}),
    ...(opts.deploymentMode !== undefined
      ? {
          deployment_mode: opts.deploymentMode as
            | "hosted"
            | "byo_db"
            | "self_host"
            | "local_dev",
        }
      : {}),
  });
  console.log(colors.green("✓") + ` Project "${result.slug}" created.`);
  console.log(colors.dim(`  project_id    ${result.project_id}`));
  console.log(colors.dim(`  workspace_id  ${result.workspace_id}`));

  const creds = loadCredentials();
  if (creds) {
    const next: Credentials = { ...creds, activeProjectId: result.project_id };
    saveCredentials(next);
    console.log(
      colors.dim("  set as active project for `ask` / `refine` / `export`"),
    );
  }
}

export async function projectsGetCommand(id: string): Promise<void> {
  const client = buildClient({ requireAuth: true });
  try {
    const project = await client.projects.get(id);
    console.log(colors.bold(project.name) + ` (${project.slug})`);
    console.log(colors.dim(`  id                       ${project.id}`));
    console.log(colors.dim(`  organization_id          ${project.organization_id}`));
    console.log(colors.dim(`  workspace_id             ${project.workspace_id}`));
    console.log(colors.dim(`  description              ${project.description ?? "—"}`));
    console.log(colors.dim(`  deployment_mode          ${project.deployment_mode}`));
    console.log(
      colors.dim(`  current_version_id       ${project.current_version_id ?? "—"}`),
    );
    console.log(
      colors.dim(`  tenant_data_schema_name  ${project.tenant_data_schema_name ?? "—"}`),
    );
    console.log(colors.dim(`  created_at               ${project.created_at}`));
  } catch (err) {
    if (err instanceof BaseflowApiError && err.status === 404) {
      console.error(colors.red("Project not found.") + ` (id=${id})`);
      process.exitCode = 1;
      return;
    }
    throw err;
  }
}
