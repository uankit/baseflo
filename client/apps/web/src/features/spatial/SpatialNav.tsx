import type { ElementType } from 'react';
import { cn } from '@baseflo/ui/lib/utils';
import {
  IconCommand,
  IconConnectors,
  IconDatabase,
  IconGitMerge,
  IconLayers,
  IconLightbulb,
  IconZap,
} from '@baseflo/ui/icons';
import type { ZoneId } from './SpatialWorkspace.js';

const ZONES: { id: ZoneId; label: string; icon: ElementType }[] = [
  { id: 'command-center', label: 'Command Center', icon: IconCommand },
  { id: 'sources', label: 'Sources', icon: IconDatabase },
  { id: 'entities', label: 'Entities', icon: IconGitMerge },
  { id: 'schema', label: 'Schema', icon: IconLayers },
  { id: 'insights', label: 'Insights', icon: IconLightbulb },
  { id: 'actions', label: 'Actions', icon: IconZap },
  { id: 'connect', label: 'Connect', icon: IconConnectors },
];

interface SpatialNavProps {
  activeZone: ZoneId;
  onZoneChange: (zone: ZoneId) => void;
}

export function SpatialNav({ activeZone, onZoneChange }: SpatialNavProps) {
  return (
    <nav
      role="navigation"
      aria-label="Workspace zones"
      className="relative z-10 flex w-16 flex-col items-center gap-1 border-r border-border bg-surface/90 py-4 backdrop-blur"
    >
      {/* System label */}
      <div className="mb-2 flex flex-col items-center gap-1">
        <div className="h-1 w-6 rounded-full bg-accent/20" />
        <span className="text-[8px] font-bold uppercase tracking-[0.15em] text-fg-subtle">
          Zones
        </span>
      </div>

      {ZONES.map((zone) => {
        const isActive = zone.id === activeZone;
        const Icon = zone.icon;
        return (
          <button
            key={zone.id}
            onClick={() => onZoneChange(zone.id)}
            title={zone.label}
            className={cn(
              'group relative flex h-11 w-11 items-center justify-center rounded-xl transition-all duration-200',
              isActive
                ? 'bg-accent text-fg-on-accent shadow-[0_0_16px_hsl(var(--color-accent)/0.35)]'
                : 'text-fg-muted hover:bg-surface-2 hover:text-fg',
            )}
          >
            <Icon size={18} strokeWidth={isActive ? 2.5 : 2} />

            {/* Active glow ring */}
            {isActive && (
              <span className="absolute inset-0 rounded-xl ring-1 ring-inset ring-accent/40" />
            )}

            {/* Active indicator bar */}
            {isActive && (
              <span className="absolute -left-[1px] top-1/2 h-5 w-[3px] -translate-y-1/2 rounded-r-full bg-accent shadow-[0_0_8px_hsl(var(--color-accent)/0.6)]" />
            )}

            {/* Tooltip */}
            <span className="pointer-events-none absolute left-full ml-3 rounded-lg border border-border bg-surface px-2.5 py-1.5 text-xs font-medium text-fg opacity-0 shadow-lg transition-opacity group-hover:opacity-100">
              {zone.label}
            </span>
          </button>
        );
      })}

      {/* Bottom accent line */}
      <div className="mt-auto flex flex-col items-center gap-1 pt-2">
        <div className="h-8 w-[1px] bg-border" />
        <div className="h-1.5 w-1.5 rounded-full bg-fg-subtle/40" />
      </div>
    </nav>
  );
}
