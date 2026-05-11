import { createFileRoute } from '@tanstack/react-router';
import { SignInView } from '../features/auth/components/SignInView.js';

export const Route = createFileRoute('/sign-in')({
  component: SignInPage,
});

function SignInPage() {
  return <SignInView />;
}
