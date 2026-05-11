import type { SSEEvent } from "./types.js";
/**
 * Parse a Server-Sent-Events stream into typed `SSEEvent`s.
 *
 * Implements the minimum of the SSE wire format used by Baseflo:
 *   - `event: <name>`
 *   - `data: <json>` (one or more lines; concatenated with `\n`)
 *   - `id: <opaque>` (used for resume)
 *   - blank line terminates an event
 *
 * Returns an async iterable so callers can `for await (const ev of ...)`.
 */
export declare function parseSseStream(response: Response): AsyncIterable<SSEEvent>;
//# sourceMappingURL=sse.d.ts.map