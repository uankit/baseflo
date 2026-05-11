import type { Transport, TransportRequest, TransportResponse } from './base.js';
import type { z } from 'zod';
import { normalizeError } from '@baseflo/error-system';

type HeaderBag = Record<string, string>;

export interface RestTransportConfig {
  baseUrl: string;
  /** Hook for the host app to inject CSRF tokens, custom headers, etc. */
  enrichHeaders?: () => HeaderBag;
}

export class RestTransport implements Transport {
  private readonly baseUrl: string;
  private readonly enrichHeaders: () => HeaderBag;

  constructor(config: RestTransportConfig) {
    this.baseUrl = config.baseUrl.replace(/\/+$/, '');
    this.enrichHeaders = config.enrichHeaders ?? (() => ({}));
  }

  async request<TData>(
    req: TransportRequest,
    schema: z.ZodSchema<TData>,
  ): Promise<TransportResponse<TData>> {
    const url = this.buildUrl(req.path, req.query);
    let response: Response;
    try {
      response = await fetch(url, {
        method: req.method,
        headers: {
          'content-type': 'application/json',
          accept: 'application/json',
          ...this.enrichHeaders(),
        },
        body: req.body !== undefined ? JSON.stringify(req.body) : undefined,
        credentials: 'include',
        signal: req.signal,
      });
    } catch (err) {
      throw normalizeError(err);
    }

    let payload: unknown = null;
    if (response.headers.get('content-type')?.includes('application/json')) {
      payload = await response.json().catch(() => null);
    }

    if (!response.ok) {
      throw normalizeError({
        ...(typeof payload === 'object' && payload !== null ? payload : {}),
        httpStatus: response.status,
      });
    }

    const parsed = schema.safeParse(payload);
    if (!parsed.success) {
      throw normalizeError({
        code: 'BF-WEB-003',
        message: 'Response did not match the contract schema.',
      });
    }

    return { data: parsed.data, status: response.status };
  }

  private buildUrl(path: string, query?: TransportRequest['query']): string {
    const base = `${this.baseUrl}${path.startsWith('/') ? path : `/${path}`}`;
    if (!query) return base;
    const params = new URLSearchParams();
    for (const [key, value] of Object.entries(query)) {
      if (value === undefined) continue;
      params.append(key, String(value));
    }
    const qs = params.toString();
    return qs ? `${base}?${qs}` : base;
  }
}
