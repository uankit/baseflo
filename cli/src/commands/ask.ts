import { activeProjectIdOrThrow, buildClient } from "../client.js";
import { colors } from "../colors.js";

const STAGE_COLORS: Record<string, (s: string) => string> = {
  "agent.start": colors.cyan,
  "agent.complete": colors.green,
  "validation.passed": colors.green,
  "validation.warning": colors.yellow,
  "validation.failed": colors.red,
  "workspace.ready": colors.bold,
  "artifact.ready": colors.bold,
  "error.recoverable": colors.yellow,
  "error.terminal": colors.red,
};

const TERMINAL_EVENTS = new Set([
  "workspace.ready",
  "error.terminal",
]);

export async function askCommand(
  prompt: string,
  opts: { projectId?: string },
): Promise<void> {
  const projectId = activeProjectIdOrThrow(opts.projectId);
  const client = buildClient({ requireAuth: true });

  const accepted = await client.conversations.create({
    project_id: projectId,
    content: prompt,
  });
  console.log(colors.dim(`  conversation_id  ${accepted.conversation_id}`));
  console.log(colors.dim(`  job_id           ${accepted.job_id}`));
  console.log(colors.dim(`  prompt           ${truncate(prompt, 80)}`));
  console.log("");

  for await (const ev of client.conversations.events(accepted.conversation_id)) {
    const colorFn = STAGE_COLORS[ev.event] ?? colors.gray;
    const ts = new Date().toISOString().slice(11, 19);
    const summary = formatEventSummary(ev.event, ev.data);
    console.log(`${colors.dim(ts)} ${colorFn(ev.event.padEnd(20))} ${summary}`);

    if (TERMINAL_EVENTS.has(ev.event)) {
      break;
    }
  }
}

export async function refineCommand(
  request: string,
  opts: { projectId?: string },
): Promise<void> {
  const projectId = activeProjectIdOrThrow(opts.projectId);
  const client = buildClient({ requireAuth: true });
  const result = await client.refinements.create(projectId, { request });
  if (result.clarification_needed) {
    console.log(colors.yellow("?") + " The agent needs a clarification:");
    console.log("  " + (result.clarification_question ?? "(no question text returned)"));
    return;
  }
  console.log(colors.green("✓") + " Refinement applied.");
  if (result.new_version_id) {
    console.log(colors.dim(`  new_version_id  ${result.new_version_id}`));
  }
  if (result.diff_summary) {
    console.log("");
    console.log(result.diff_summary);
  }
}

function formatEventSummary(eventName: string, data: Record<string, unknown>): string {
  if (eventName.startsWith("agent.")) {
    const agent = typeof data["agent_name"] === "string" ? data["agent_name"] : "?";
    const tokens = typeof data["tokens"] === "number" ? `${data["tokens"]}t` : "";
    const dur = typeof data["duration_ms"] === "number" ? `${data["duration_ms"]}ms` : "";
    return `${agent} ${[tokens, dur].filter(Boolean).join(" ")}`.trim();
  }
  if (eventName === "workspace.ready") {
    const projectId =
      typeof data["project_id"] === "string" ? data["project_id"] : "?";
    const versionId =
      typeof data["project_version_id"] === "string"
        ? data["project_version_id"]
        : "?";
    return `project=${projectId} version=${versionId}`;
  }
  if (eventName.startsWith("error")) {
    const code = typeof data["error_code"] === "string" ? data["error_code"] : "?";
    const message = typeof data["message"] === "string" ? data["message"] : "?";
    return `${code}: ${message}`;
  }
  // Default: tiny single-line dump.
  const keys = Object.keys(data);
  if (keys.length === 0) return "";
  if (keys.length === 1) return `${keys[0]}=${String(data[keys[0]!])}`;
  return JSON.stringify(data);
}

function truncate(s: string, n: number): string {
  return s.length <= n ? s : s.slice(0, n - 1) + "…";
}
