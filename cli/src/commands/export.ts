import { writeFileSync } from "node:fs";
import { resolve } from "node:path";

import { activeProjectIdOrThrow, buildClient } from "../client.js";
import { colors } from "../colors.js";

export async function exportCommand(
  projectIdArg: string | undefined,
  opts: { out?: string },
): Promise<void> {
  const projectId = activeProjectIdOrThrow(projectIdArg);
  const client = buildClient({ requireAuth: true });
  const buffer = await client.exports.create(projectId);
  const outPath = resolve(
    process.cwd(),
    opts.out ?? `baseflo-export-${projectId}.tar.gz`,
  );
  writeFileSync(outPath, new Uint8Array(buffer));
  const sizeKb = (buffer.byteLength / 1024).toFixed(1);
  console.log(colors.green("✓") + ` Exported to ${outPath} (${sizeKb} KB).`);
}
