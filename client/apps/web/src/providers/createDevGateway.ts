import { createGateway } from '@baseflo/api-client';
import { RestTransport } from '@baseflo/api-client/transports/rest';

/**
 * Production-shape Gateway. Always talks to a real backend over REST + SSE.
 * `VITE_API_BASE_URL` overrides the same-origin default; for local dev Vite
 * proxies `/api` to FastAPI on :8000 (see `apps/web/vite.config.ts`).
 *
 * Dev fixtures are gone — every gateway method
 * resolves against a real route in `server/app/api/v1/routes/`.
 */
export function createDevGateway() {
  const apiBase = import.meta.env.VITE_API_BASE_URL ?? '';
  const transport = new RestTransport({ baseUrl: apiBase });
  return createGateway({
    transport,
    sseBaseUrl: apiBase || window.location.origin,
  });
}
