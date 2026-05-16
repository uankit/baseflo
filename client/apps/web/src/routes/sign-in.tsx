import { createFileRoute } from '@tanstack/react-router';
import { z } from 'zod';
import { SignInView } from '../features/auth/components/SignInView.js';

export const Route = createFileRoute('/sign-in')({
  validateSearch: z.object({
    redirect: z.string().optional(),
  }),
  component: SignInPage,
});

function SignInPage() {
  const search = Route.useSearch();
  return <SignInView redirectTo={search.redirect ?? '/workspace/business'} />;
}
