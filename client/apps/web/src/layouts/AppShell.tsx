import React from 'react';
import { IconDatabase, IconLogOut, IconSparkles, IconZap } from '@baseflo/ui/icons';

interface AppShellProps {
  children: React.ReactNode;
  activeTab?: 'sources' | 'brief' | 'ask' | 'inbox';
  onTabChange?: (tab: 'sources' | 'brief' | 'ask' | 'inbox') => void;
  lastSyncedLabel?: string;
  openInsights?: number;
  proposedActions?: number;
  onSignOut?: () => void;
  isSigningOut?: boolean;
}

const tabs: Array<{ id: 'brief' | 'inbox' | 'ask' | 'sources'; label: string }> = [
  { id: 'brief', label: 'Brief' },
  { id: 'inbox', label: 'Inbox' },
  { id: 'ask', label: 'Ask' },
  { id: 'sources', label: 'Sources' },
];

export function AppShell({
  children,
  activeTab = 'brief',
  onTabChange,
  lastSyncedLabel,
  openInsights = 0,
  proposedActions = 0,
  onSignOut,
  isSigningOut = false,
}: AppShellProps) {
  return (
    <div className="flex min-h-screen flex-col bg-paper text-ink selection:bg-flame/25">
      <header className="sticky top-0 z-50 flex shrink-0 items-center justify-between gap-4 border-b border-ink/20 bg-paper/95 px-5 py-3 backdrop-blur">
        <div className="flex min-w-0 items-baseline gap-5">
          <button
            type="button"
            className="flex items-baseline gap-2"
            onClick={() => onTabChange?.('brief')}
          >
            <span className="font-serif text-[22px] font-bold italic tracking-tight">
              baseflo<span className="text-flame">.</span>
            </span>
          </button>

          <nav className="hidden items-center gap-1 md:flex">
            {tabs.map((tab) => (
              <button
                key={tab.id}
                onClick={() => onTabChange?.(tab.id)}
                className={`px-3 py-1.5 font-serif text-[17px] italic transition ${
                  activeTab === tab.id
                    ? 'bg-ink text-paper shadow-[2px_2px_0_rgba(220,84,37,0.9)]'
                    : 'text-ink/55 hover:bg-white/60 hover:text-ink'
                }`}
              >
                {tab.label}
              </button>
            ))}
          </nav>
        </div>

        <div className="flex shrink-0 items-center gap-3 font-sans text-[11px] tracking-wide text-ink/60">
          <span className="hidden items-center gap-1.5 sm:flex">
            <IconSparkles className="h-3.5 w-3.5 text-flame" />
            <strong className="text-ink">{openInsights}</strong> reads
          </span>
          <span className="hidden items-center gap-1.5 sm:flex">
            <IconZap className="h-3.5 w-3.5 text-flame" />
            <strong className="text-ink">{proposedActions}</strong> actions
          </span>
          <span className="hidden h-4 w-px bg-ink/20 sm:block" />
          <span className="flex items-center gap-1.5">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-600" aria-hidden />
            <span className="font-semibold uppercase tracking-wider text-ink">live</span>
          </span>
          {lastSyncedLabel ? (
            <span className="hidden text-ink/45 sm:inline">· {lastSyncedLabel}</span>
          ) : null}
          <IconDatabase className="hidden h-3.5 w-3.5 text-ink/35 lg:block" />
          {onSignOut ? (
            <>
              <span className="hidden h-4 w-px bg-ink/20 sm:block" />
              <button
                type="button"
                onClick={onSignOut}
                disabled={isSigningOut}
                className="inline-flex items-center gap-1.5 border border-ink/30 px-2 py-1 font-semibold uppercase tracking-wider text-ink transition hover:border-flame hover:text-flame disabled:cursor-wait disabled:opacity-50"
                aria-label="Sign out"
              >
                <IconLogOut className="h-3.5 w-3.5" />
                <span className="hidden sm:inline">{isSigningOut ? 'leaving' : 'logout'}</span>
              </button>
            </>
          ) : null}
        </div>
      </header>

      <main className="flex-1 w-full overflow-auto">
        {children}
      </main>
    </div>
  );
}
