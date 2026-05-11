import type { Gateway } from '@baseflo/api-client';
import {
  MagicLinkRequestSchema,
  SignInRequestSchema,
  type MagicLinkRequest,
  type Session,
  type SignInRequest,
} from '@baseflo/contracts';
import { normalizeError, type NormalizedError } from '@baseflo/error-system';

/**
 * Auth service. Wraps gateway calls in validated, typed operations and
 * normalizes errors before they reach hooks/UI. This is the only layer that
 * touches gateway.auth from the feature side.
 *
 * See docs/06-design.md §6 (boundaries) and docs/40-features/WEB-APP.md §5.1.
 */
export class AuthService {
  constructor(private readonly gateway: Gateway) {}

  async signInWithPassword(req: SignInRequest): Promise<Session> {
    const parsed = SignInRequestSchema.safeParse(req);
    if (!parsed.success) {
      throw this.formError(parsed.error.issues[0]?.message ?? 'Invalid sign-in request');
    }
    try {
      return await this.gateway.auth.signIn(parsed.data);
    } catch (err) {
      throw this.surface(err);
    }
  }

  async requestMagicLink(req: MagicLinkRequest): Promise<{ ok: true }> {
    const parsed = MagicLinkRequestSchema.safeParse(req);
    if (!parsed.success) {
      throw this.formError(parsed.error.issues[0]?.message ?? 'Invalid magic-link request');
    }
    try {
      return await this.gateway.auth.signInMagicLink(parsed.data);
    } catch (err) {
      throw this.surface(err);
    }
  }

  async session(): Promise<Session> {
    try {
      return await this.gateway.auth.session();
    } catch (err) {
      throw this.surface(err);
    }
  }

  async signOut(): Promise<void> {
    try {
      await this.gateway.auth.signOut();
    } catch (err) {
      throw this.surface(err);
    }
  }

  private formError(message: string): NormalizedError {
    return normalizeError({ code: 'BF-WEB-011', message });
  }

  private surface(err: unknown): NormalizedError {
    return normalizeError(err);
  }
}

export function createAuthService(gateway: Gateway): AuthService {
  return new AuthService(gateway);
}
