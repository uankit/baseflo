import { createContext, useContext, type ReactNode } from 'react';
import type { Gateway } from '@baseflo/api-client';

const GatewayContext = createContext<Gateway | null>(null);

export function GatewayProvider({
  gateway,
  children,
}: {
  gateway: Gateway;
  children: ReactNode;
}) {
  return <GatewayContext.Provider value={gateway}>{children}</GatewayContext.Provider>;
}

export function useGateway(): Gateway {
  const ctx = useContext(GatewayContext);
  if (!ctx) {
    throw new Error('useGateway() called outside <GatewayProvider>.');
  }
  return ctx;
}
