import { createFileRoute, useNavigate } from '@tanstack/react-router';
import { useEffect } from 'react';
import { useAuth } from '../features/auth/hooks/useAuth.js';
import { Landing } from '../features/landing/Landing.js';

export const Route = createFileRoute('/')({
  component: HomePage,
});

function HomePage() {
  const { isLoading, isAuthenticated } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    if (isLoading) return;
    if (isAuthenticated) {
      navigate({ to: '/workspace/business', replace: true });
    }
  }, [isLoading, isAuthenticated, navigate]);

  if (isLoading || isAuthenticated) {
    return (
      <div className="flex h-screen items-center justify-center bg-bg text-fg-subtle text-sm">
        {isLoading ? 'Loading…' : 'Opening your workspace…'}
      </div>
    );
  }

  return <Landing />;
}
