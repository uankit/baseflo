import type { z } from 'zod';
import type { Transport, TransportRequest, TransportResponse } from './base.js';

export interface MockRoute<TData = unknown> {
  method?: TransportRequest['method'];
  path: string | RegExp | ((req: TransportRequest) => boolean);
  response: TData | ((req: TransportRequest) => TData | Promise<TData>);
  status?: number;
}

export class MockTransport implements Transport {
  private readonly routes: MockRoute[];

  constructor(routes: MockRoute[] = []) {
    this.routes = [...routes];
  }

  add(route: MockRoute): void {
    this.routes.push(route);
  }

  async request<TData>(
    req: TransportRequest,
    schema: z.ZodSchema<TData>,
  ): Promise<TransportResponse<TData>> {
    const route = this.routes.find((candidate) => matches(candidate, req));
    if (!route) {
      throw new Error(`No mock route for ${req.method} ${req.path}`);
    }
    const raw =
      typeof route.response === 'function'
        ? await route.response(req)
        : route.response;
    return {
      data: schema.parse(raw),
      status: route.status ?? 200,
    };
  }
}

function matches(route: MockRoute, req: TransportRequest): boolean {
  if (route.method && route.method !== req.method) return false;
  if (typeof route.path === 'string') return route.path === req.path;
  if (route.path instanceof RegExp) return route.path.test(req.path);
  return route.path(req);
}
