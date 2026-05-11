import { createFileRoute, useNavigate } from '@tanstack/react-router';
import { useQuery } from '@tanstack/react-query';
import { useEffect } from 'react';
import { Spinner } from '@baseflo/ui';
import { useGateway } from '../providers/GatewayProvider.js';
import { LandingView } from '../features/landing/LandingView.js';

export const Route = createFileRoute('/')({
  component: RootIndex,
});

/**
 * Root route. Behaviour:
 *   - unauthenticated → render the public landing page (LandingView)
 *   - authenticated, has orgs → redirect to last/first org dashboard
 *   - authenticated, no orgs → redirect to /welcome
 *
 * The session lookup runs once on mount; while it's pending we render the
 * landing page itself rather than a spinner — there's no flash of "marketing"
 * for signed-in users because the redirect happens as soon as the session
 * resolves.
 */
function RootIndex() {
  const gateway = useGateway();
  const navigate = useNavigate();
  const sessionQuery = useQuery({
    queryKey: ['auth', 'session'],
    queryFn: () => gateway.auth.session(),
    retry: false,
  });

  useEffect(() => {
    if (sessionQuery.isSuccess) {
      const session = sessionQuery.data;
      const slug = session.organizations[0]?.organizationSlug;
      if (slug) {
        navigate({ to: '/o/$orgSlug', params: { orgSlug: slug }, replace: true });
      } else {
        navigate({ to: '/welcome', replace: true });
      }
    }
    // On error: stay on the landing page (the error means "no session").
  }, [sessionQuery.isSuccess, sessionQuery.data, navigate]);

  // While we're checking the session, show the landing page anyway. No spinner,
  // no flash. If the session resolves to "signed-in", the redirect happens
  // before the user can interact.
  if (sessionQuery.isPending) {
    return (
      <div className="relative">
        <LandingView />
        <span className="sr-only" role="status">
          Loading session…
        </span>
      </div>
    );
  }

  if (sessionQuery.isSuccess) {
    return (
      <div className="flex min-h-full items-center justify-center bg-bg">
        <Spinner />
      </div>
    );
  }

  return <LandingView />;
}
