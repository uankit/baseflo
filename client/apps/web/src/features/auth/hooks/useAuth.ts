import { useMemo } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useGateway } from '../../../providers/GatewayProvider.js';
import { createAuthService, type AuthUser } from '../services/authService.js';

const USER_KEY = ['auth', 'user'] as const;

export function useAuth() {
  const gateway = useGateway();
  const queryClient = useQueryClient();
  const service = useMemo(() => createAuthService(gateway), [gateway]);

  const userQuery = useQuery<AuthUser | null>({
    queryKey: USER_KEY,
    queryFn: async () => {
      try {
        return await service.fetchMe();
      } catch {
        return null;
      }
    },
    retry: false,
    refetchOnWindowFocus: false,
    staleTime: 5 * 60 * 1000,
  });

  const requestMagicLink = useMutation({
    mutationFn: (email: string) => service.requestMagicLink(email),
  });

  const verifyMagicLink = useMutation({
    mutationFn: ({ email, token }: { email: string; token: string }) =>
      service.verifyMagicLink(email, token),
    onSuccess: (user) => {
      queryClient.setQueryData(USER_KEY, user);
    },
  });

  const signOut = useMutation({
    mutationFn: () => service.signOut(),
    onSuccess: () => {
      queryClient.setQueryData(USER_KEY, null);
      queryClient.clear();
    },
  });

  return {
    user: userQuery.data ?? null,
    isLoading: userQuery.isPending,
    isAuthenticated: !!userQuery.data,
    requestMagicLink,
    verifyMagicLink,
    signOut,
  };
}
