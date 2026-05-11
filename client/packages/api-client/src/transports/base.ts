import type { z } from 'zod';

export interface TransportRequest<TBody = unknown> {
  method: 'GET' | 'POST' | 'PATCH' | 'PUT' | 'DELETE';
  path: string;
  body?: TBody;
  query?: Record<string, string | number | boolean | undefined>;
  signal?: AbortSignal;
}

export interface TransportResponse<TData> {
  data: TData;
  status: number;
}

export interface Transport {
  request<TData>(
    req: TransportRequest,
    schema: z.ZodSchema<TData>,
  ): Promise<TransportResponse<TData>>;
}
