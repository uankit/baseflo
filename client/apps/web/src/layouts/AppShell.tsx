import type { ReactNode } from 'react';
import { TopBar } from './TopBar.js';

interface AppShellProps {
  orgName?: string;
  orgSlug?: string;
  agentsActive?: boolean;
  children: ReactNode;
}

export function AppShell({ orgName, orgSlug, agentsActive, children }: AppShellProps) {
  return (
    <div className="flex min-h-screen flex-col bg-bg">
      <TopBar orgName={orgName} orgSlug={orgSlug} agentsActive={agentsActive} />
      <main role="main" className="flex-1 pb-12">
        {children}
      </main>
    </div>
  );
}
