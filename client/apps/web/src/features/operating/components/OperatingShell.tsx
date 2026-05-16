import { Link, Outlet, useNavigate, useRouterState } from '@tanstack/react-router';
import { IconDatabase, IconLogOut, IconSparkles, IconZap } from '@baseflo/ui/icons';
import { useAuth } from '../../auth/hooks/useAuth.js';
import { useActions, useInboxArtifacts } from '../api/useOperatingData.js';

const navItems = [
  { to: '/workspace/business', label: 'Business' },
  { to: '/workspace/brief', label: 'Brief' },
  { to: '/workspace/inbox', label: 'Inbox' },
  { to: '/workspace/ask', label: 'Ask' },
  { to: '/workspace/sources', label: 'Sources' },
] as const;

export function OperatingShell() {
  const { signOut, user } = useAuth();
  const navigate = useNavigate();
  const router = useRouterState();
  const inbox = useInboxArtifacts(50);
  const actions = useActions({ include_terminal: false, limit: 50 });

  const currentPath = router.location.pathname;
  const reads = inbox.data?.length ?? 0;
  const actionCount = actions.data?.length ?? 0;

  return (
    <div className="min-h-screen bg-paper text-ink selection:bg-flame/25">
      <header className="sticky top-0 z-50 border-b border-ink/20 bg-paper/95 backdrop-blur">
        <div className="flex items-center justify-between gap-4 px-5 py-3">
          <div className="flex min-w-0 items-baseline gap-5">
            <Link to="/workspace/business" className="flex items-baseline gap-2">
              <span className="font-serif text-[24px] font-bold italic tracking-tight">
                baseflo<span className="text-flame">.</span>
              </span>
            </Link>
            <nav className="hidden items-center gap-1 md:flex" aria-label="Workspace">
              {navItems.map((item) => {
                const active = currentPath === item.to;
                return (
                  <Link
                    key={item.to}
                    to={item.to}
                    className={`px-3 py-1.5 font-serif text-[17px] italic transition ${
                      active
                        ? 'bg-ink text-paper shadow-[2px_2px_0_rgba(220,84,37,0.9)]'
                        : 'text-ink/55 hover:bg-white/60 hover:text-ink'
                    }`}
                  >
                    {item.label}
                  </Link>
                );
              })}
            </nav>
          </div>

          <div className="flex shrink-0 items-center gap-3 font-sans text-[11px] tracking-wide text-ink/60">
            <span className="hidden items-center gap-1.5 sm:flex">
              <IconSparkles className="h-3.5 w-3.5 text-flame" />
              <strong className="text-ink">{reads}</strong> reads
            </span>
            <span className="hidden items-center gap-1.5 sm:flex">
              <IconZap className="h-3.5 w-3.5 text-flame" />
              <strong className="text-ink">{actionCount}</strong> actions
            </span>
            <span className="hidden h-4 w-px bg-ink/20 sm:block" />
            <span className="flex items-center gap-1.5">
              <span className="h-1.5 w-1.5 rounded-full bg-moss" aria-hidden />
              <span className="font-semibold uppercase tracking-wider text-ink">live</span>
            </span>
            <IconDatabase className="hidden h-3.5 w-3.5 text-ink/35 lg:block" />
            <span className="hidden max-w-[180px] truncate text-ink/45 lg:inline">
              {user?.organization.name}
            </span>
            <button
              type="button"
              onClick={() =>
                signOut.mutate(undefined, {
                  onSuccess: () => void navigate({ to: '/sign-in', replace: true }),
                })
              }
              disabled={signOut.isPending}
              className="inline-flex items-center gap-1.5 border border-ink/30 px-2 py-1 font-semibold uppercase tracking-wider text-ink transition hover:border-flame hover:text-flame disabled:cursor-wait disabled:opacity-50"
            >
              <IconLogOut className="h-3.5 w-3.5" />
              <span className="hidden sm:inline">{signOut.isPending ? 'leaving' : 'logout'}</span>
            </button>
          </div>
        </div>

        <nav className="flex gap-1 overflow-x-auto border-t border-ink/10 px-3 py-2 md:hidden" aria-label="Workspace mobile">
          {navItems.map((item) => (
            <Link
              key={item.to}
              to={item.to}
              className={`shrink-0 px-3 py-1 text-sm ${
                currentPath === item.to ? 'bg-ink text-paper' : 'text-ink/65'
              }`}
            >
              {item.label}
            </Link>
          ))}
        </nav>
      </header>
      <main>
        <Outlet />
      </main>
    </div>
  );
}
