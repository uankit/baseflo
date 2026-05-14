import { createFileRoute, useNavigate } from '@tanstack/react-router';
import { useState } from 'react';
import { useAuth } from '../features/auth/hooks/useAuth.js';
import { OperatingDashboard } from '../features/operating/OperatingDashboard.js';
import { OperatingAsk } from '../features/operating/OperatingAsk.js';
import { OperatingInbox } from '../features/operating/OperatingInbox.js';
import { OperatingConnectors } from '../features/operating/OperatingConnectors.js';
import { lastSyncedLabel, useOperatingBrief } from '../features/operating/operatingData.js';
import { AppShell } from '../layouts/AppShell.js';

export const Route = createFileRoute('/workspace')({
  component: WorkspacePage,
});

function WorkspacePage() {
  const [activeTab, setActiveTab] = useState<'sources' | 'brief' | 'ask' | 'inbox'>('brief');
  const navigate = useNavigate();
  const { signOut } = useAuth();
  const briefQuery = useOperatingBrief();
  const synced = lastSyncedLabel(briefQuery.data);
  const summary = briefQuery.data?.summary;

  const handleSignOut = async () => {
    await signOut.mutateAsync();
    navigate({ to: '/sign-in', replace: true });
  };

  return (
    <AppShell
      activeTab={activeTab}
      onTabChange={setActiveTab}
      lastSyncedLabel={synced}
      openInsights={summary?.open_insights ?? 0}
      proposedActions={summary?.proposed_actions ?? 0}
      onSignOut={handleSignOut}
      isSigningOut={signOut.isPending}
    >
      {activeTab === 'sources' ? (
        <OperatingConnectors />
      ) : activeTab === 'ask' ? (
        <OperatingAsk />
      ) : activeTab === 'inbox' ? (
        <OperatingInbox />
      ) : (
        <OperatingDashboard />
      )}
    </AppShell>
  );
}
