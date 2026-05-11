import { useMemo } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { MagicLinkRequest, Session, SignInRequest } from '@baseflo/contracts';
import { useGateway } from '../../../providers/GatewayProvider.js';
import { createAuthService } from '../services/authService.js';

const SESSION_KEY = ['auth', 'session'] as const;

/**
 * The single React-side entry point into the auth feature. Exposes a typed
 * surface for sign-in, magic-link, session lookup, and sign-out.
 */
export function useAuth() {
  const gateway = useGateway();
  const queryClient = useQueryClient();
  const service = useMemo(() => createAuthService(gateway), [gateway]);

  const sessionQuery = useQuery<Session>({
    queryKey: SESSION_KEY,
    queryFn: () => service.session(),
    retry: false,
    enabled: false, // sign-in screen does not auto-fetch; protected routes opt in.
  });

  const signIn = useMutation({
    mutationFn: (req: SignInRequest) => service.signInWithPassword(req),
    onSuccess: (session) => {
      queryClient.setQueryData(SESSION_KEY, session);
    },
  });

  const requestMagicLink = useMutation({
    mutationFn: (req: MagicLinkRequest) => service.requestMagicLink(req),
  });

  const signOut = useMutation({
    mutationFn: () => service.signOut(),
    onSuccess: () => {
      queryClient.setQueryData(SESSION_KEY, null);
    },
  });

  return {
    session: sessionQuery.data ?? null,
    isLoading: sessionQuery.isPending,
    signIn,
    requestMagicLink,
    signOut,
  };
}
