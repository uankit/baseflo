import { Link } from '@tanstack/react-router';
import type { ReactNode } from 'react';
import { cn } from '@baseflo/ui/lib/utils';
import { TopBar } from './TopBar.js';

const TABS = [
  { id: 'org', label: 'Organization' },
  { id: 'team', label: 'Team' },
  { id: 'billing', label: 'Billing' },
  { id: 'api-keys', label: 'API keys' },
  { id: 'audit', label: 'Audit log' },
] as const;

export type SettingsTabId = (typeof TABS)[number]['id'];

interface SettingsShellProps {
  orgSlug: string;
  orgName: string;
  activeTab: SettingsTabId;
  children: ReactNode;
}

export function SettingsShell({ orgSlug, orgName, activeTab, children }: SettingsShellProps) {
  return (
    <div className="flex min-h-full flex-col bg-bg">
      <TopBar orgSlug={orgSlug} orgName={orgName} />
      <div className="mx-auto flex w-full max-w-6xl flex-1 gap-8 px-6 py-8">
        <aside
          role="navigation"
          aria-label="Settings sections"
          className="w-56 shrink-0"
        >
          <h1 className="mb-4 text-xl font-semibold text-fg">Settings</h1>
          <nav className="flex flex-col gap-1">
            {TABS.map((tab) => (
              <Link
                key={tab.id}
                to="/o/$orgSlug/settings/$tab"
                params={{ orgSlug, tab: tab.id }}
                className={cn(
                  'rounded-md px-3 py-2 text-sm transition-colors',
                  tab.id === activeTab
                    ? 'bg-surface-2 font-medium text-fg'
                    : 'text-fg-muted hover:bg-surface-2 hover:text-fg',
                )}
              >
                {tab.label}
              </Link>
            ))}
          </nav>
        </aside>
        <main role="main" className="flex-1">
          {children}
        </main>
      </div>
    </div>
  );
}

export const SETTINGS_TABS = TABS;
