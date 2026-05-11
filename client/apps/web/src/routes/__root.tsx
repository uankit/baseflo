import { Outlet, createRootRouteWithContext } from '@tanstack/react-router';
import type { RouterContext } from '../router.js';

export const Route = createRootRouteWithContext<RouterContext>()({
  component: RootComponent,
  notFoundComponent: NotFound,
  errorComponent: RootError,
});

function RootComponent() {
  return <Outlet />;
}

function NotFound() {
  return (
    <div className="flex min-h-full flex-col items-center justify-center gap-3 px-4 py-12 text-center">
      <p className="text-sm font-medium text-fg-muted">404</p>
      <h1 className="text-2xl font-semibold text-fg">We couldn't find that page</h1>
      <p className="text-sm text-fg-muted">Check the URL or head back home.</p>
    </div>
  );
}

function RootError({ error }: { error: Error }) {
  return (
    <div className="flex min-h-full flex-col items-center justify-center gap-3 px-4 py-12 text-center">
      <h1 className="text-2xl font-semibold text-fg">Something went wrong</h1>
      <p className="max-w-md text-sm text-fg-muted">
        Refresh the page. If this keeps happening, contact support.
      </p>
      <p className="font-mono text-xs text-fg-subtle">{error.message}</p>
    </div>
  );
}
