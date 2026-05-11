/**
 * Minimal frontend logger. Tagged JSON-style output during dev; in production
 * this hooks into Sentry breadcrumbs + a /api/v1/web-telemetry sink. See
 * docs/40-features/WEB-APP.md §17.
 *
 * Components must use this instead of console.* — `no-console` ESLint rule
 * forbids direct console (warn/error allowed for genuine errors only).
 */

export type LogLevel = 'debug' | 'info' | 'warn' | 'error';

export interface LogEntry {
  level: LogLevel;
  message: string;
  /** Structured key/value tags. */
  tags?: Record<string, string | number | boolean | null>;
}

type Sink = (entry: LogEntry) => void;

const sinks: Sink[] = [];

export function registerLogSink(sink: Sink): () => void {
  sinks.push(sink);
  return () => {
    const idx = sinks.indexOf(sink);
    if (idx >= 0) sinks.splice(idx, 1);
  };
}

function emit(entry: LogEntry): void {
  for (const sink of sinks) {
    try {
      sink(entry);
    } catch {
      // sinks must never break the caller
    }
  }
}

export const log = {
  debug(message: string, tags?: LogEntry['tags']) {
    emit({ level: 'debug', message, tags });
  },
  info(message: string, tags?: LogEntry['tags']) {
    emit({ level: 'info', message, tags });
  },
  warn(message: string, tags?: LogEntry['tags']) {
    emit({ level: 'warn', message, tags });
  },
  error(message: string, tags?: LogEntry['tags']) {
    emit({ level: 'error', message, tags });
  },
};
