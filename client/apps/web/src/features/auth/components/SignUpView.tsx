import { Link } from '@tanstack/react-router';
import { MagicLinkForm } from './MagicLinkForm.js';

export function SignUpView() {
  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-col gap-1">
        <h1 className="font-serif text-2xl font-semibold leading-tight text-fg">
          Stop wrestling spreadsheets.
        </h1>
        <p className="text-sm text-fg-muted">
          Four agents map, reconcile, and understand your data — then surface what actually matters. No SQL required.
        </p>
      </header>

      <MagicLinkForm />

      <p className="text-sm text-fg-muted">
        Already have an account?{' '}
        <Link
          to="/sign-in"
          className="text-accent underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-border-focus rounded"
        >
          Sign in
        </Link>
      </p>
    </div>
  );
}
