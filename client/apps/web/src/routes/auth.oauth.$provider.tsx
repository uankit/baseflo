import { createFileRoute } from '@tanstack/react-router';
import { z } from 'zod';
import { AuthShell } from '../layouts/AuthShell.js';
import { OAuthCallbackView } from '../features/auth/components/OAuthCallbackView.js';

export const Route = createFileRoute('/auth/oauth/$provider')({
  validateSearch: z.object({ error: z.string().optional() }),
  component: OAuthCallbackPage,
});

function OAuthCallbackPage() {
  return (
    <AuthShell>
      <OAuthCallbackView />
    </AuthShell>
  );
}
