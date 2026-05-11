import { createFileRoute, useNavigate } from '@tanstack/react-router';
import { useEffect } from 'react';
import { useAuth } from '../features/auth/hooks/useAuth.js';

export const Route = createFileRoute('/')({
  component: HomePage,
});

function HomePage() {
  const { isLoading, isAuthenticated } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    if (isLoading) return;
    if (!isAuthenticated) {
      navigate({ to: '/sign-in', replace: true });
    }
  }, [isLoading, isAuthenticated, navigate]);

  return (
    <div className="flex h-screen items-center justify-center bg-gray-950 text-gray-500 text-sm">
      {isLoading ? 'Loading…' : 'Redirecting…'}
    </div>
  );
}
