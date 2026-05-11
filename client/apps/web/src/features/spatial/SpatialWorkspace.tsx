import { useState, type ReactNode } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { cn } from '@baseflo/ui/lib/utils';
import { SpatialNav } from './SpatialNav.js';
import { AgentDock } from './AgentDock.js';
import { CommandPalette } from './CommandPalette.js';
import { useCommandPalette } from './useCommandPalette.js';
import { PulseDot } from '@baseflo/ui';

export type ZoneId =
  | 'command-center'
  | 'sources'
  | 'entities'
  | 'schema'
  | 'insights'
  | 'actions'
  | 'connect';

interface SpatialWorkspaceProps {
  orgSlug: string;
  orgName: string;
  projectSlug: string;
  projectId?: string | null;
  versionId: string;
  children: ReactNode;
  activeZone: ZoneId;
  onZoneChange: (zone: ZoneId) => void;
}

const zoneTransitions = {
  initial: { opacity: 0, scale: 0.98, y: 12 },
  animate: { opacity: 1, scale: 1, y: 0 },
  exit: { opacity: 0, scale: 1.02, y: -12 },
};

export function SpatialWorkspace({
  orgSlug: _orgSlug,
  orgName,
  projectSlug,
  projectId,
  versionId,
  children,
  activeZone,
  onZoneChange,
}: SpatialWorkspaceProps) {
  const [showPalette, setShowPalette] = useState(false);
  const { query, setQuery, suggestions } = useCommandPalette();

  return (
    <div className="flex h-screen w-screen flex-col overflow-hidden bg-bg">
      {/* Top bar — Mission Control Header */}
      <header className="flex h-12 shrink-0 items-center justify-between border-b border-border bg-surface/80 px-4 backdrop-blur">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <div className="flex h-6 w-6 items-center justify-center rounded-md bg-accent">
              <span className="text-[10px] font-bold text-fg-on-accent">B</span>
            </div>
            <span className="text-sm font-semibold text-fg">Baseflo</span>
          </div>
          <span className="text-fg-subtle">/</span>
          <span className="text-sm font-medium text-fg-muted">{orgName}</span>
          <span className="text-fg-subtle">/</span>
          <span className="text-sm font-medium text-fg">{projectSlug}</span>
          <span className="text-fg-subtle">/</span>
          <span className="rounded bg-surface-2 px-1.5 py-0.5 font-mono text-[10px] text-fg-subtle">
            {versionId === 'pending' ? 'DRAFT' : versionId.slice(0, 7)}
          </span>
        </div>

        <div className="flex items-center gap-4">
          {/* Active Agent Status */}
          <div className="hidden items-center gap-2 sm:flex">
            <PulseDot tone="success" active />
            <span className="text-[11px] font-medium uppercase tracking-wider text-success">
              System Online
            </span>
          </div>

          {/* Spotlight Search Trigger */}
          <button
            onClick={() => setShowPalette(true)}
            className={cn(
              'group flex items-center gap-2 rounded-lg border border-border bg-surface-2 px-3 py-1.5 text-xs text-fg-muted transition-all',
              'hover:border-accent/40 hover:bg-accent-soft hover:text-fg hover:shadow-[0_0_12px_hsl(var(--color-accent)/0.15)]',
            )}
          >
            <svg
              width="14"
              height="14"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2.5"
              strokeLinecap="round"
              strokeLinejoin="round"
              className="opacity-60 group-hover:opacity-100"
            >
              <circle cx="11" cy="11" r="8" />
              <path d="m21 21-4.3-4.3" />
            </svg>
            <span className="hidden sm:inline">Ask Baseflo…</span>
            <kbd className="ml-1 hidden rounded bg-surface px-1.5 py-0.5 font-mono text-[10px] text-fg-subtle sm:inline">
              ⌘K
            </kbd>
          </button>
        </div>
      </header>

      {/* Main spatial layout */}
      <div className="relative flex flex-1 overflow-hidden">
        {/* Atmospheric background layers */}
        <div className="pointer-events-none absolute inset-0 bg-atmospheric opacity-60" />
        <div className="pointer-events-none absolute inset-0 bg-grid-dots opacity-40" />

        {/* Spatial navigation sidebar */}
        <SpatialNav activeZone={activeZone} onZoneChange={onZoneChange} />

        {/* Zone content */}
        <main className="relative flex-1 overflow-auto">
          <AnimatePresence mode="wait">
            <motion.div
              key={activeZone}
              variants={zoneTransitions}
              initial="initial"
              animate="animate"
              exit="exit"
              transition={{ duration: 0.25, ease: [0.4, 0, 0.2, 1] }}
              className="relative min-h-full p-6"
            >
              {children}
            </motion.div>
          </AnimatePresence>
        </main>
      </div>

      {/* Agent dock */}
      <AgentDock projectId={projectId} />

      {/* Command palette */}
      <CommandPalette
        open={showPalette}
        onClose={() => setShowPalette(false)}
        query={query}
        onQueryChange={setQuery}
        suggestions={suggestions}
      />
    </div>
  );
}
