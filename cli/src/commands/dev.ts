import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { resolve } from "node:path";

import { colors } from "../colors.js";

const DEFAULT_COMPOSE_FILE = "docker-compose.dev.yml";

export async function devCommand(opts: {
  composeFile?: string;
  detached?: boolean;
}): Promise<void> {
  const composeFile = resolve(process.cwd(), opts.composeFile ?? DEFAULT_COMPOSE_FILE);
  if (!existsSync(composeFile)) {
    console.error(
      colors.red("✗") +
        ` ${composeFile} not found. Run from the Baseflo monorepo root, ` +
        `or pass --compose-file <path>.`,
    );
    process.exitCode = 1;
    return;
  }

  console.log(
    colors.dim(`  Starting Postgres + Redis from ${composeFile}…`),
  );
  await runProcess("docker", ["compose", "-f", composeFile, "up", "-d"]);

  console.log(colors.green("✓") + " Postgres + Redis running.");
  console.log("");
  console.log(colors.bold("Next steps:"));
  console.log(
    `  1. Apply migrations:    ${colors.cyan("cd server && uv run alembic upgrade head")}`,
  );
  console.log(
    `  2. Start the API:       ${colors.cyan(
      "cd server && uv run uvicorn app.main:app --reload",
    )}`,
  );
  console.log(
    `  3. Sign in:             ${colors.cyan("baseflo login")}`,
  );
  console.log("");
  if (opts.detached === false) {
    console.log(colors.dim("  Containers stay up until you run `docker compose down`."));
  }
}

function runProcess(cmd: string, args: string[]): Promise<void> {
  return new Promise((resolveFn, reject) => {
    const proc = spawn(cmd, args, { stdio: "inherit" });
    proc.on("error", reject);
    proc.on("exit", (code) => {
      if (code === 0) resolveFn();
      else reject(new Error(`${cmd} exited with code ${code}`));
    });
  });
}
