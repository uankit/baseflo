import { createFileRoute, useNavigate } from '@tanstack/react-router';
import { useEffect } from 'react';
import { useAuth } from '../features/auth/hooks/useAuth.js';

export const Route = createFileRoute('/welcome')({
  component: WelcomePage,
});

function WelcomePage() {
  const { isLoading, user } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    if (isLoading) return;
    if (!user) {
      navigate({ to: '/sign-in', replace: true });
      return;
    }
    navigate({ to: '/workspace/business', replace: true });
  }, [isLoading, navigate, user]);

  return (
    <div className="flex min-h-screen items-center justify-center bg-paper px-4 text-sm text-ink/55">
      Opening your operating workspace...
    </div>
  );
}
