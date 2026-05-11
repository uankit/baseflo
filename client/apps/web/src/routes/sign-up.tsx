import { createFileRoute } from '@tanstack/react-router';
import { AuthShell } from '../layouts/AuthShell.js';
import { SignUpView } from '../features/auth/components/SignUpView.js';

export const Route = createFileRoute('/sign-up')({
  component: SignUpPage,
});

function SignUpPage() {
  return (
    <AuthShell>
      <SignUpView />
    </AuthShell>
  );
}
