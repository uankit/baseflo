import type { Gateway } from '@baseflo/api-client';
import { setToken, clearToken } from '@baseflo/api-client';

export interface AuthUser {
  id: string;
  email: string;
  organization: { id: string; name: string; slug: string };
}

export function createAuthService(gateway: Gateway) {
  return {
    async requestMagicLink(email: string): Promise<{ ok: boolean; dev_token: string | null }> {
      // The server only logs local/dev tokens now; production-shape responses do
      // not leak sign-in tokens to the browser.
      const resp = await gateway.auth.requestMagicLink({ email });
      return { ok: resp.ok, dev_token: null };
    },

    async verifyMagicLink(email: string, token: string): Promise<AuthUser> {
      const resp = await gateway.auth.verifyMagicLink({ email, token });
      setToken(resp.access_token);
      return {
        id: resp.user.id,
        email: resp.user.email,
        organization: {
          id: resp.current_organization.id,
          name: resp.current_organization.name,
          slug: resp.current_organization.slug,
        },
      };
    },

    async fetchMe(): Promise<AuthUser> {
      const me = await gateway.auth.me();
      return {
        id: me.user.id,
        email: me.user.email,
        organization: me.current_organization,
      };
    },

    async signOut(): Promise<void> {
      try {
        await gateway.auth.signOut();
      } finally {
        clearToken();
      }
    },
  };
}
