import { createFileRoute } from '@tanstack/react-router';
import { z } from 'zod';
import { AuthShell } from '../layouts/AuthShell.js';
import { MagicLinkConsumeView } from '../features/auth/components/MagicLinkConsumeView.js';

export const Route = createFileRoute('/auth/magic-link')({
  validateSearch: z.object({ token: z.string().optional() }),
  component: MagicLinkPage,
});

function MagicLinkPage() {
  return (
    <AuthShell>
      <MagicLinkConsumeView />
    </AuthShell>
  );
}
