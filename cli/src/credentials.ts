import { readFileSync, writeFileSync, existsSync, mkdirSync, unlinkSync } from "node:fs";
import { homedir } from "node:os";
import { dirname, join } from "node:path";

const CONFIG_DIR = join(homedir(), ".baseflo");
const CREDENTIALS_PATH = join(CONFIG_DIR, "credentials.json");

export interface Credentials {
  baseUrl: string;
  /** Raw session cookie value (the token after `baseflo_session=`). */
  sessionToken: string;
  email?: string;
  activeOrg?: string;
  /** Optional default project for `ask` / `refine` / `export`. */
  activeProjectId?: string;
}

export function loadCredentials(): Credentials | null {
  if (!existsSync(CREDENTIALS_PATH)) return null;
  try {
    const raw = readFileSync(CREDENTIALS_PATH, "utf-8");
    return JSON.parse(raw) as Credentials;
  } catch {
    return null;
  }
}

export function saveCredentials(c: Credentials): void {
  if (!existsSync(CONFIG_DIR)) {
    mkdirSync(CONFIG_DIR, { recursive: true, mode: 0o700 });
  }
  // Ensure parent dir exists (in case CONFIG_DIR was deleted out from under us).
  mkdirSync(dirname(CREDENTIALS_PATH), { recursive: true, mode: 0o700 });
  writeFileSync(CREDENTIALS_PATH, JSON.stringify(c, null, 2), { mode: 0o600 });
}

export function clearCredentials(): void {
  if (existsSync(CREDENTIALS_PATH)) {
    unlinkSync(CREDENTIALS_PATH);
  }
}

export function credentialsPath(): string {
  return CREDENTIALS_PATH;
}
