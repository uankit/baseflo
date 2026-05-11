import { useEffect } from 'react';
import { useNavigate, useParams, useSearch } from '@tanstack/react-router';
import { ErrorCallout, Spinner } from '@baseflo/ui';
import { useAuth } from '../hooks/useAuth';

export function OAuthCallbackView() {
  const { provider } = useParams({ from: '/auth/oauth/$provider' });
  const search = useSearch({ from: '/auth/oauth/$provider' }) as { error?: string };
  const navigate = useNavigate();
  const { session, isLoading } = useAuth();

  useEffect(() => {
    if (!isLoading && session) {
      navigate({ to: '/welcome' });
    }
  }, [isLoading, session, navigate]);

  if (search.error) {
    return (
      <ErrorCallout
        title="Sign-in didn't complete"
        message={`The ${provider} flow returned an error. Start over from sign-in.`}
        action={{ label: 'Back to sign in', onClick: () => navigate({ to: '/sign-in' }) }}
      />
    );
  }

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center gap-4 py-20">
        <Spinner className="h-8 w-8" />
        <p className="text-sm text-fg-muted">Completing sign-in…</p>
      </div>
    );
  }

  return (
    <ErrorCallout
      title="Sign-in didn't complete"
      message="We couldn't verify your session. Use email sign-in instead."
      action={{ label: 'Back to sign in', onClick: () => navigate({ to: '/sign-in' }) }}
    />
  );
}
