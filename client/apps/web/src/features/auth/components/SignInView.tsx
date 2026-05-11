import { MagicLinkForm } from './MagicLinkForm.js';

export function SignInView() {
  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-col gap-1">
        <h1 className="font-serif text-2xl font-semibold leading-tight text-fg">
          Pick up where your agents left off.
        </h1>
        <p className="text-sm text-fg-muted">
          Sign in to see what Source, Recon, Schema, and Insight have prepared for you.
        </p>
      </header>

      <MagicLinkForm />
    </div>
  );
}
