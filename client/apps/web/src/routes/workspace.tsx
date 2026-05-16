import { createFileRoute, redirect } from '@tanstack/react-router';
import { OperatingShell } from '../features/operating/components/OperatingShell.js';

export const Route = createFileRoute('/workspace')({
  beforeLoad: async ({ context, location }) => {
    try {
      await context.gateway.auth.me();
    } catch {
      throw redirect({
        to: '/sign-in',
        search: { redirect: location.href },
      });
    }
  },
  component: OperatingShell,
});
