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
export async function* parseSseStream(response) {
    if (!response.body) {
        throw new Error("SSE response has no body.");
    }
    const reader = response.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let buffer = "";
    let event = "message";
    let dataLines = [];
    let id;
    let retry;
    const flush = () => {
        if (dataLines.length === 0 && event === "message") {
            return null;
        }
        const dataText = dataLines.join("\n");
        let parsed = {};
        if (dataText) {
            try {
                parsed = JSON.parse(dataText);
            }
            catch {
                parsed = { raw: dataText };
            }
        }
        const out = { event, data: parsed };
        if (id !== undefined)
            out.id = id;
        if (retry !== undefined)
            out.retry = retry;
        event = "message";
        dataLines = [];
        id = undefined;
        retry = undefined;
        return out;
    };
    while (true) {
        const { done, value } = await reader.read();
        if (done) {
            const tail = flush();
            if (tail)
                yield tail;
            return;
        }
        buffer += decoder.decode(value, { stream: true });
        // Process complete lines.
        let newlineIdx = buffer.indexOf("\n");
        while (newlineIdx !== -1) {
            const line = buffer.slice(0, newlineIdx).replace(/\r$/, "");
            buffer = buffer.slice(newlineIdx + 1);
            if (line === "") {
                const ev = flush();
                if (ev)
                    yield ev;
            }
            else if (line.startsWith(":")) {
                // Comment line — skip.
            }
            else {
                const colonIdx = line.indexOf(":");
                const field = colonIdx === -1 ? line : line.slice(0, colonIdx);
                const rawValue = colonIdx === -1 ? "" : line.slice(colonIdx + 1);
                const value = rawValue.startsWith(" ") ? rawValue.slice(1) : rawValue;
                switch (field) {
                    case "event":
                        event = value;
                        break;
                    case "data":
                        dataLines.push(value);
                        break;
                    case "id":
                        id = value;
                        break;
                    case "retry": {
                        const n = Number.parseInt(value, 10);
                        if (!Number.isNaN(n))
                            retry = n;
                        break;
                    }
                    default:
                        // Unknown field — spec says ignore.
                        break;
                }
            }
            newlineIdx = buffer.indexOf("\n");
        }
    }
}
//# sourceMappingURL=sse.js.map