import { RouterProvider } from '@tanstack/react-router';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useMemo } from 'react';
import { ToastProvider, TooltipProvider } from '@baseflo/ui';
import { router } from './router.js';
import { GatewayProvider } from './providers/GatewayProvider.js';
import { createDevGateway } from './providers/createDevGateway.js';

declare module '@tanstack/react-router' {
  interface Register {
    router: typeof router;
  }
}

export function App() {
  const queryClient = useMemo(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 30_000,
            retry: 1,
            refetchOnWindowFocus: false,
          },
          mutations: {
            retry: 0,
          },
        },
      }),
    [],
  );

  const gateway = useMemo(() => createDevGateway(), []);

  return (
    <QueryClientProvider client={queryClient}>
      <GatewayProvider gateway={gateway}>
        <ToastProvider>
          <TooltipProvider delayDuration={200}>
            <RouterProvider router={router} context={{ gateway }} />
          </TooltipProvider>
        </ToastProvider>
      </GatewayProvider>
    </QueryClientProvider>
  );
}
