/**
 * Thrown when the Baseflo API returns a non-2xx response with a typed
 * `{ error_code, message }` body. The original status + parsed body are
 * surfaced for callers that want to branch on `error_code`.
 */
export class BaseflowApiError extends Error {
    status;
    body;
    constructor(status, body) {
        super(`[${body.error_code}] ${body.message}`);
        this.status = status;
        this.body = body;
        this.name = "BaseflowApiError";
    }
    get errorCode() {
        return this.body.error_code;
    }
}
/**
 * Thrown when the transport itself fails (network down, timeout, malformed
 * response). Distinct from `BaseflowApiError` so callers can retry.
 */
export class BaseflowTransportError extends Error {
    cause;
    constructor(message, cause) {
        super(message);
        this.name = "BaseflowTransportError";
        if (cause !== undefined) {
            this.cause = cause;
        }
    }
}
//# sourceMappingURL=errors.js.map