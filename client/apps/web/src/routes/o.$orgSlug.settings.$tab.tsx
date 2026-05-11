import { createFileRoute, useParams, useNavigate } from '@tanstack/react-router';
import { useQuery } from '@tanstack/react-query';
import { useGateway } from '../providers/GatewayProvider.js';
import { SettingsShell, type SettingsTabId, SETTINGS_TABS } from '../layouts/SettingsShell.js';
import {
  ApiKeysTab,
  BillingTab,
  OrgTab,
  SettingsAuditTab,
  TeamTab,
} from '../features/settings/SettingsTabs.js';

export const Route = createFileRoute('/o/$orgSlug/settings/$tab')({
  component: SettingsPage,
});

function SettingsPage() {
  const { orgSlug, tab } = useParams({ from: '/o/$orgSlug/settings/$tab' });
  const navigate = useNavigate();
  const gateway = useGateway();

  const orgQuery = useQuery({
    queryKey: ['org', orgSlug],
    queryFn: () => gateway.orgs.get(orgSlug),
  });

  const validTab: SettingsTabId | null = SETTINGS_TABS.some((t) => t.id === tab)
    ? (tab as SettingsTabId)
    : null;

  if (!validTab) {
    navigate({
      to: '/o/$orgSlug/settings/$tab',
      params: { orgSlug, tab: 'org' },
      replace: true,
    });
    return null;
  }

  return (
    <SettingsShell orgSlug={orgSlug} orgName={orgQuery.data?.name ?? '—'} activeTab={validTab}>
      {validTab === 'org' && <OrgTab orgSlug={orgSlug} />}
      {validTab === 'team' && <TeamTab orgSlug={orgSlug} />}
      {validTab === 'billing' && <BillingTab orgSlug={orgSlug} />}
      {validTab === 'api-keys' && <ApiKeysTab orgSlug={orgSlug} />}
      {validTab === 'audit' && <SettingsAuditTab orgSlug={orgSlug} />}
    </SettingsShell>
  );
}
