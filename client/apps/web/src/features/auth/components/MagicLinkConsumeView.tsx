import { useEffect } from 'react';
import { useNavigate, useSearch } from '@tanstack/react-router';
import { useMutation } from '@tanstack/react-query';
import { Spinner, ErrorCallout } from '@baseflo/ui';
import { useGateway } from '../../../providers/GatewayProvider.js';

export function MagicLinkConsumeView() {
  const search = useSearch({ from: '/auth/magic-link' }) as { token?: string };
  const gateway = useGateway();
  const navigate = useNavigate();

  const consume = useMutation({
    mutationFn: async (token: string) => gateway.auth.consumeMagicLink({ token }),
    onSuccess: (session) => {
      const target = session.activeOrgId
        ? { to: '/o/$orgSlug', params: { orgSlug: session.organizations[0]?.organizationSlug ?? '' } }
        : { to: '/welcome' };
      navigate(target as never);
    },
  });

  useEffect(() => {
    if (search.token) consume.mutate(search.token);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search.token]);

  if (!search.token) {
    return (
      <ErrorCallout
        title="Missing token"
        message="The link you used didn't include a token. Request a new one."
      />
    );
  }

  if (consume.isError) {
    return (
      <ErrorCallout
        title="Link couldn't be verified"
        message="It may have expired or already been used. Request a fresh one."
        action={{ label: 'Back to sign in', onClick: () => navigate({ to: '/sign-in' }) }}
      />
    );
  }

  return (
    <div className="flex flex-col items-center gap-3 py-8 text-center">
      <Spinner />
      <p className="text-sm text-fg-muted">Signing you in…</p>
    </div>
  );
}
