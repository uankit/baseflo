import { describe, expect, it } from "vitest";

import { parseSseStream } from "./sse.js";

function makeStream(chunks: string[]): Response {
  const encoder = new TextEncoder();
  let i = 0;
  const stream = new ReadableStream<Uint8Array>({
    pull(controller) {
      if (i >= chunks.length) {
        controller.close();
        return;
      }
      controller.enqueue(encoder.encode(chunks[i]!));
      i += 1;
    },
  });
  return new Response(stream, {
    headers: { "content-type": "text/event-stream" },
  });
}

describe("parseSseStream", () => {
  it("yields one event per blank-line-terminated frame", async () => {
    const response = makeStream([
      'event: agent.start\ndata: {"agent": "ColumnClassifier"}\n\n',
      'event: agent.complete\ndata: {"agent": "ColumnClassifier", "tokens": 142}\n\n',
    ]);
    const events = [];
    for await (const ev of parseSseStream(response)) {
      events.push(ev);
    }
    expect(events).toEqual([
      { event: "agent.start", data: { agent: "ColumnClassifier" } },
      {
        event: "agent.complete",
        data: { agent: "ColumnClassifier", tokens: 142 },
      },
    ]);
  });

  it("concatenates multi-line `data:` fields", async () => {
    const response = makeStream([
      "event: log\ndata: line one\ndata: line two\n\n",
    ]);
    const events = [];
    for await (const ev of parseSseStream(response)) {
      events.push(ev);
    }
    expect(events[0]!.event).toBe("log");
    expect(events[0]!.data).toEqual({ raw: "line one\nline two" });
  });

  it("captures the `id:` field for replay", async () => {
    const response = makeStream(['id: 17\nevent: tick\ndata: {"n": 17}\n\n']);
    const events = [];
    for await (const ev of parseSseStream(response)) {
      events.push(ev);
    }
    expect(events[0]!.id).toBe("17");
  });

  it("handles chunks split mid-event", async () => {
    const response = makeStream(["event: x\nda", 'ta: {"k": 1}\n\n']);
    const events = [];
    for await (const ev of parseSseStream(response)) {
      events.push(ev);
    }
    expect(events).toEqual([{ event: "x", data: { k: 1 } }]);
  });

  it("ignores comment lines", async () => {
    const response = makeStream([
      ': keep-alive\nevent: ping\ndata: {"ok": true}\n\n',
    ]);
    const events = [];
    for await (const ev of parseSseStream(response)) {
      events.push(ev);
    }
    expect(events[0]!.data).toEqual({ ok: true });
  });
});
