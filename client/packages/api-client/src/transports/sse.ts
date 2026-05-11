import { SagaEventKindSchema, SagaEventSchema, type SagaEvent } from '@baseflo/contracts';
import { log } from '../logger.js';

export interface SseSubscriptionOptions {
  baseUrl: string;
  conversationId: string;
  fromSequence?: number;
  onEvent: (event: SagaEvent) => void;
  onError?: (err: unknown) => void;
  onOpen?: () => void;
  onClose?: () => void;
  /** Backoff schedule (ms) for reconnect attempts. Empty array = no auto-reconnect. */
  backoff?: number[];
}

export interface SseSubscription {
  close: () => void;
  /** Last-seen monotonic sequence number (for resume on reconnect). */
  lastSequence: () => number;
}

const DEFAULT_BACKOFF = [500, 1000, 2000, 4000, 8000];

export function subscribeToSaga(opts: SseSubscriptionOptions): SseSubscription {
  let lastSeq = opts.fromSequence ?? 0;
  let attempt = 0;
  let closed = false;
  let source: EventSource | null = null;
  const backoff = opts.backoff ?? DEFAULT_BACKOFF;

  const open = () => {
    if (closed) return;
    const url = buildUrl(opts.baseUrl, opts.conversationId, lastSeq);
    source = new EventSource(url, { withCredentials: true });

    source.onopen = () => {
      attempt = 0;
      opts.onOpen?.();
    };

    const handleEvent = (msg: MessageEvent<string>) => {
      let parsed: unknown;
      try {
        parsed = JSON.parse(msg.data);
      } catch {
        log.warn('sse.invalid_json', { conversationId: opts.conversationId });
        return;
      }
      const result = SagaEventSchema.safeParse(parsed);
      if (!result.success) {
        log.warn('sse.invalid_event_shape', { conversationId: opts.conversationId });
        return;
      }
      lastSeq = Math.max(lastSeq, result.data.sequence);
      opts.onEvent(result.data);
    };
    source.onmessage = handleEvent;
    for (const kind of SagaEventKindSchema.options) {
      source.addEventListener(kind, handleEvent);
    }

    source.onerror = (err) => {
      opts.onError?.(err);
      source?.close();
      source = null;
      if (closed) return;
      const delay = backoff[Math.min(attempt, backoff.length - 1)];
      attempt += 1;
      if (delay === undefined) {
        opts.onClose?.();
        return;
      }
      setTimeout(open, delay);
    };
  };

  open();

  return {
    close: () => {
      closed = true;
      source?.close();
      source = null;
      opts.onClose?.();
    },
    lastSequence: () => lastSeq,
  };
}

function buildUrl(baseUrl: string, conversationId: string, fromSeq: number): string {
  const trimmed = baseUrl.replace(/\/+$/, '');
  const seq = fromSeq > 0 ? `?seq=${fromSeq}` : '';
  return `${trimmed}/api/v1/conversations/${conversationId}/events${seq}`;
}
