import { readFileSync, writeFileSync, existsSync, mkdirSync, unlinkSync } from "node:fs";
import { homedir } from "node:os";
import { dirname, join } from "node:path";
const CONFIG_DIR = join(homedir(), ".baseflo");
const CREDENTIALS_PATH = join(CONFIG_DIR, "credentials.json");
export function loadCredentials() {
    if (!existsSync(CREDENTIALS_PATH))
        return null;
    try {
        const raw = readFileSync(CREDENTIALS_PATH, "utf-8");
        return JSON.parse(raw);
    }
    catch {
        return null;
    }
}
export function saveCredentials(c) {
    if (!existsSync(CONFIG_DIR)) {
        mkdirSync(CONFIG_DIR, { recursive: true, mode: 0o700 });
    }
    // Ensure parent dir exists (in case CONFIG_DIR was deleted out from under us).
    mkdirSync(dirname(CREDENTIALS_PATH), { recursive: true, mode: 0o700 });
    writeFileSync(CREDENTIALS_PATH, JSON.stringify(c, null, 2), { mode: 0o600 });
}
export function clearCredentials() {
    if (existsSync(CREDENTIALS_PATH)) {
        unlinkSync(CREDENTIALS_PATH);
    }
}
export function credentialsPath() {
    return CREDENTIALS_PATH;
}
//# sourceMappingURL=credentials.js.map