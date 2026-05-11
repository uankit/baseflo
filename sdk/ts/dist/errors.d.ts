import type { ErrorBody } from "./types.js";
/**
 * Thrown when the Baseflo API returns a non-2xx response with a typed
 * `{ error_code, message }` body. The original status + parsed body are
 * surfaced for callers that want to branch on `error_code`.
 */
export declare class BaseflowApiError extends Error {
    readonly status: number;
    readonly body: ErrorBody;
    constructor(status: number, body: ErrorBody);
    get errorCode(): string;
}
/**
 * Thrown when the transport itself fails (network down, timeout, malformed
 * response). Distinct from `BaseflowApiError` so callers can retry.
 */
export declare class BaseflowTransportError extends Error {
    readonly cause?: unknown;
    constructor(message: string, cause?: unknown);
}
//# sourceMappingURL=errors.d.ts.map