import { createRootRouteWithContext, Outlet } from '@tanstack/react-router';
import type { Gateway } from '@baseflo/api-client';

export interface RootRouteContext {
  gateway: Gateway;
}

export const Route = createRootRouteWithContext<RootRouteContext>()({
  component: RootComponent,
});

function RootComponent() {
  return <Outlet />;
}
