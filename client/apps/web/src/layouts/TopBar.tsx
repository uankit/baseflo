import { Link } from '@tanstack/react-router';
import {
  IconChevronDown,
  IconChevronRight,
  IconHelpCircle,
  IconLogOut,
  IconSettings,
} from '@baseflo/ui/icons';
import { Avatar, AvatarFallback, Button, PulseDot } from '@baseflo/ui';
import { DeploymentModeBadge, StatusPill } from '@baseflo/ui';
import type { DeploymentMode } from '@baseflo/contracts';
import { useAuth } from '../features/auth/hooks/useAuth.js';

interface TopBarProps {
  orgName?: string;
  orgSlug?: string;
  projectName?: string;
  versionLabel?: string;
  deploymentMode?: DeploymentMode;
  systemStatus?: 'nominal' | 'degraded' | 'down';
  agentsActive?: boolean;
}

export function TopBar({
  orgName,
  orgSlug,
  projectName,
  versionLabel,
  deploymentMode,
  systemStatus = 'nominal',
  agentsActive,
}: TopBarProps) {
  const { session, signOut } = useAuth();
  const initials = (session?.user.displayName ?? session?.user.email ?? '?')
    .split(/\s+/)
    .map((p) => p[0]?.toUpperCase() ?? '')
    .slice(0, 2)
    .join('');

  return (
    <header
      role="banner"
      className="sticky top-0 z-sticky flex h-14 items-center justify-between border-b border-border bg-surface/80 px-4 backdrop-blur-sm"
    >
      <nav aria-label="Breadcrumb" className="flex items-center gap-2">
        <Link
          to={orgSlug ? '/o/$orgSlug' : '/sign-in'}
          params={orgSlug ? { orgSlug } : undefined}
          className="rounded text-lg font-semibold tracking-tight text-fg hover:text-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-border-focus"
        >
          baseflo
        </Link>

        {orgName && (
          <>
            <IconChevronRight className="h-3.5 w-3.5 text-fg-subtle" aria-hidden="true" />
            <Link
              to={orgSlug ? '/o/$orgSlug' : '/sign-in'}
              params={orgSlug ? { orgSlug } : undefined}
              className="rounded text-sm font-medium text-fg-muted hover:text-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-border-focus"
            >
              {orgName}
            </Link>
          </>
        )}

        {projectName && (
          <>
            <IconChevronRight className="h-3.5 w-3.5 text-fg-subtle" aria-hidden="true" />
            <span className="text-sm font-medium text-fg">{projectName}</span>
            {versionLabel && (
              <span className="rounded bg-surface-2 px-2 py-0.5 text-xs font-mono text-fg-muted">
                {versionLabel}
              </span>
            )}
            {deploymentMode && <DeploymentModeBadge mode={deploymentMode} />}
          </>
        )}
      </nav>

      <div className="flex items-center gap-3">
        {agentsActive && (
          <div className="hidden items-center gap-1.5 rounded-full bg-accent-soft px-2.5 py-1 text-xs font-medium text-accent sm:flex">
            <PulseDot size={6} active tone="accent" />
            Agents active
          </div>
        )}

        <StatusPill status={systemStatus} />

        <button
          type="button"
          aria-label="Help"
          className="rounded p-1.5 text-fg-muted hover:text-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-border-focus"
        >
          <IconHelpCircle className="h-4 w-4" />
        </button>

        <details className="relative">
          <summary
            className="flex cursor-pointer list-none items-center gap-2 rounded-lg p-1 transition-colors hover:bg-surface-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-border-focus"
            aria-label="User menu"
          >
            <Avatar>
              <AvatarFallback>{initials || '?'}</AvatarFallback>
            </Avatar>
            <IconChevronDown className="h-3.5 w-3.5 text-fg-muted" />
          </summary>
          <div className="absolute right-0 mt-2 w-60 rounded-lg border border-border bg-surface p-1.5 shadow-lg">
            <div className="px-3 py-2 text-sm">
              <div className="font-medium text-fg">{session?.user.displayName ?? 'You'}</div>
              <div className="text-xs text-fg-muted">{session?.user.email}</div>
            </div>
            <div className="my-1 h-px bg-border" />
            {orgSlug && (
              <Link
                to="/o/$orgSlug/settings/$tab"
                params={{ orgSlug, tab: 'org' }}
                className="flex items-center gap-2 rounded-md px-3 py-2 text-sm text-fg hover:bg-surface-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-border-focus"
              >
                <IconSettings className="h-3.5 w-3.5 text-fg-muted" />
                Settings
              </Link>
            )}
            <Button
              variant="ghost"
              size="sm"
              className="w-full justify-start rounded-md px-3"
              onClick={() => signOut.mutate()}
            >
              <IconLogOut className="mr-2 h-3.5 w-3.5" /> Sign out
            </Button>
          </div>
        </details>
      </div>
    </header>
  );
}
