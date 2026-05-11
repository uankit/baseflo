import type { Gateway } from '@baseflo/api-client';
import { setToken, clearToken } from '@baseflo/api-client';

export interface AuthUser {
  id: string;
  email: string;
  organization: { id: string; name: string; slug: string };
}

export function createAuthService(gateway: Gateway) {
  return {
    async requestMagicLink(email: string): Promise<{ message: string; dev_token: string | null }> {
      return gateway.auth.requestMagicLink({ email });
    },

    async verifyMagicLink(email: string, token: string): Promise<AuthUser> {
      const resp = await gateway.auth.verifyMagicLink({ email, token });
      setToken(resp.access_token);
      return {
        id: resp.user.id,
        email: resp.user.email,
        organization: {
          id: resp.user.organization_id,
          name: '',
          slug: '',
        },
      };
    },

    async fetchMe(): Promise<AuthUser> {
      const me = await gateway.auth.me();
      return {
        id: me.id,
        email: me.email,
        organization: me.organization,
      };
    },

    async signOut(): Promise<void> {
      await gateway.auth.signOut();
      clearToken();
    },
  };
}
