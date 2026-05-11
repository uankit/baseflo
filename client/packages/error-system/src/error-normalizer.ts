import { WebErrorCode, type ErrorEntry } from './error-codes.js';
import { getErrorEntry } from './error-registry.js';

/**
 * Backend payload shapes we accept. Anything not matching falls through to
 * BF-WEB-UNKNOWN-001. The normalizer never throws — it produces an ErrorEntry
 * the UI can render directly.
 */
export interface BackendErrorPayload {
  /** Server-issued BF-AREA-NNN code. */
  code?: string;
  /** Server-issued message; not guaranteed user-safe. We discard if registered. */
  message?: string;
  /** HTTP status, if any. Used for fallback classification. */
  httpStatus?: number;
  /** Free-form details from server; never shown to the user. */
  details?: unknown;
}

export interface NormalizedError extends ErrorEntry {
  /** Original code if known; null if we couldn't extract one. */
  serverCode: string | null;
  /** Server-supplied message, kept for telemetry/Sentry only. */
  serverMessage: string | null;
}

/**
 * Convert any unknown error into a user-renderable ErrorEntry.
 *
 * Rules from docs/40-features/WEB-APP.md §15.3:
 *  - Server message text is NEVER shown to the user.
 *  - Unknown codes resolve to BF-WEB-UNKNOWN-001.
 *  - The function never throws.
 */
export function normalizeError(input: unknown): NormalizedError {
  // Network failure — fetch threw before we got a response.
  if (input instanceof TypeError && /fetch|network/i.test(input.message)) {
    return wrap(getErrorEntry(WebErrorCode.Offline), null, input.message);
  }

  // Plain object that looks like our backend error envelope.
  if (isBackendErrorPayload(input)) {
    if (input.code && typeof input.code === 'string') {
      // Registered codes (BF-WEB-* or BF-AREA-NNN known to the registry) win.
      return wrap(getErrorEntry(input.code), input.code, input.message ?? null);
    }
    if (typeof input.httpStatus === 'number') {
      const fallback =
        input.httpStatus >= 500
          ? WebErrorCode.Server5xx
          : input.httpStatus >= 400
            ? WebErrorCode.Server4xxUnhandled
            : WebErrorCode.Unknown;
      return wrap(getErrorEntry(fallback), null, input.message ?? null);
    }
  }

  // Native Error — keep the message for telemetry only.
  if (input instanceof Error) {
    return wrap(getErrorEntry(WebErrorCode.Unknown), null, input.message);
  }

  return wrap(getErrorEntry(WebErrorCode.Unknown), null, null);
}

function wrap(
  entry: ErrorEntry,
  serverCode: string | null,
  serverMessage: string | null,
): NormalizedError {
  return { ...entry, serverCode, serverMessage };
}

function isBackendErrorPayload(value: unknown): value is BackendErrorPayload {
  if (typeof value !== 'object' || value === null) return false;
  const candidate = value as Record<string, unknown>;
  if ('code' in candidate && typeof candidate['code'] !== 'string' && candidate['code'] !== undefined) {
    return false;
  }
  if (
    'message' in candidate &&
    typeof candidate['message'] !== 'string' &&
    candidate['message'] !== undefined
  ) {
    return false;
  }
  if (
    'httpStatus' in candidate &&
    typeof candidate['httpStatus'] !== 'number' &&
    candidate['httpStatus'] !== undefined
  ) {
    return false;
  }
  return true;
}
