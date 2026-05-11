import type { ErrorBody } from "./types.js";

/**
 * Thrown when the Baseflo API returns a non-2xx response with a typed
 * `{ error_code, message }` body. The original status + parsed body are
 * surfaced for callers that want to branch on `error_code`.
 */
export class BaseflowApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly body: ErrorBody,
  ) {
    super(`[${body.error_code}] ${body.message}`);
    this.name = "BaseflowApiError";
  }

  get errorCode(): string {
    return this.body.error_code;
  }
}

/**
 * Thrown when the transport itself fails (network down, timeout, malformed
 * response). Distinct from `BaseflowApiError` so callers can retry.
 */
export class BaseflowTransportError extends Error {
  public override readonly cause?: unknown;

  constructor(message: string, cause?: unknown) {
    super(message);
    this.name = "BaseflowTransportError";
    if (cause !== undefined) {
      this.cause = cause;
    }
  }
}
