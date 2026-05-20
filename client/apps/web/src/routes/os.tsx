import { createFileRoute, redirect } from '@tanstack/react-router';
import { OsShell } from '../os/components/OsShell';

export const Route = createFileRoute('/os')({
  component: OsShell,
  beforeLoad: async ({ context }) => {
    // Auth guard — same as workspace
    const me = await context.gateway.auth.me();
    if (!me.user) {
      throw redirect({ to: '/sign-in' });
    }
  },
});
