import { createGateway, getToken } from '@baseflo/api-client';
import { RestTransport } from '@baseflo/api-client/transports/rest';

/**
 * Production-shape Gateway. Always talks to a real backend over REST.
 * `VITE_API_BASE_URL` overrides the same-origin default; for local dev Vite
 * proxies `/api` to FastAPI on :8000 (see `apps/web/vite.config.ts`).
 */
export function createDevGateway() {
  const apiBase = import.meta.env.VITE_API_BASE_URL ?? '';
  const transport = new RestTransport({
    baseUrl: apiBase,
    getToken,
  });
  return createGateway({ transport });
}
