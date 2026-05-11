import { createFileRoute } from '@tanstack/react-router';
import { AuthShell } from '../layouts/AuthShell.js';
import { SignInView } from '../features/auth/components/SignInView.js';

export const Route = createFileRoute('/sign-in')({
  component: SignInPage,
});

function SignInPage() {
  return (
    <AuthShell>
      <SignInView />
    </AuthShell>
  );
}
