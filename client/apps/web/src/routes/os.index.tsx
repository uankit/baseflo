import { createFileRoute, redirect } from '@tanstack/react-router';

export const Route = createFileRoute('/os/')({
  beforeLoad: async () => {
    throw redirect({ to: '/os/overview' });
  },
});
