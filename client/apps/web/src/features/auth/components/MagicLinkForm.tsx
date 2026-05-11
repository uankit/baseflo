import { useForm } from 'react-hook-form';
import { MagicLinkRequestSchema, type MagicLinkRequest } from '@baseflo/contracts';
import { Button } from '@baseflo/ui';
import { IconSparkles } from '@baseflo/ui/icons';
import { zodResolver } from '../../../lib/forms/zodResolver.js';
import { useAuth } from '../hooks/useAuth.js';

export function MagicLinkForm() {
  const { requestMagicLink } = useAuth();
  const form = useForm<MagicLinkRequest>({
    resolver: zodResolver(MagicLinkRequestSchema),
    defaultValues: { email: '' },
  });

  const onSubmit = form.handleSubmit((values) => {
    requestMagicLink.mutate(values);
  });

  return (
    <form onSubmit={onSubmit} className="flex flex-col gap-5" noValidate>
      <div className="flex flex-col gap-1.5">
        <label htmlFor="magic-email" className="text-sm font-medium text-fg">
          Email
        </label>
        <input
          id="magic-email"
          type="email"
          autoComplete="email"
          inputMode="email"
          aria-invalid={form.formState.errors.email ? 'true' : 'false'}
          aria-describedby={form.formState.errors.email ? 'magic-email-error' : 'magic-email-helper'}
          className="h-11 rounded-lg border border-border bg-bg px-4 text-sm text-fg shadow-sm transition-all placeholder:text-fg-subtle focus-visible:border-border-focus focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-border-focus/50 focus-visible:ring-offset-2 focus-visible:ring-offset-bg"
          placeholder="you@company.com"
          {...form.register('email')}
        />
        {form.formState.errors.email ? (
          <p id="magic-email-error" className="text-sm text-danger">
            {form.formState.errors.email.message}
          </p>
        ) : (
          <p id="magic-email-helper" className="flex items-start gap-1.5 text-xs leading-relaxed text-fg-subtle">
            <IconSparkles size={12} className="mt-0.5 shrink-0 text-accent" />
            We&apos;ll email a secure, one-time magic link. No password to remember — just click and you&apos;re in.
          </p>
        )}
      </div>

      <Button
        type="submit"
        disabled={requestMagicLink.isPending}
        className="h-11 text-base shadow-md shadow-accent/20 transition-shadow hover:shadow-lg hover:shadow-accent/30"
      >
        {requestMagicLink.isPending ? 'Sending…' : 'Email me a link'}
      </Button>

      {requestMagicLink.isSuccess && (
        <p role="status" className="text-sm text-success">
          Check your inbox. The link works for 15 minutes.
        </p>
      )}

      {requestMagicLink.isError && (
        <p role="alert" className="text-sm text-danger">
          We couldn&apos;t send the link. Try again.
        </p>
      )}
    </form>
  );
}
