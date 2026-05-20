import { Link, Outlet, useLocation } from '@tanstack/react-router';
import { useAvailableWorkbenches } from '../api/workbenchClient';

const navItems = [
  { to: '/os/overview', label: 'Overview', icon: '□' },
  { to: '/os/collections', label: 'Collections', icon: '₹' },
];

export function OsShell() {
  const location = useLocation();
  const { data: wbData } = useAvailableWorkbenches();

  return (
    <div className="min-h-screen bg-paper">
      {/* Top bar */}
      <header className="sticky top-0 z-50 bg-white border-b-2 border-ink">
        <div className="max-w-7xl mx-auto px-4 h-14 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="text-lg font-bold text-ink tracking-tight">Baseflo OS</span>
            <span className="text-xs px-2 py-0.5 bg-moss/10 text-moss font-semibold rounded">
              LIVE
            </span>
          </div>
          <div className="flex items-center gap-4">
            <nav className="flex gap-1">
              {navItems.map((item) => (
                <Link
                  key={item.to}
                  to={item.to}
                  className={`px-3 py-1.5 text-sm font-medium rounded-md transition-colors ${
                    location.pathname.startsWith(item.to)
                      ? 'bg-ink text-paper'
                      : 'text-ink/70 hover:bg-paper'
                  }`}
                >
                  <span className="mr-1">{item.icon}</span>
                  {item.label}
                </Link>
              ))}
            </nav>
            <div className="h-6 w-px bg-ink/20" />
            <Link
              to="/workspace/business"
              className="text-xs text-ink/50 hover:text-ink transition-colors"
            >
              Classic View →
            </Link>
          </div>
        </div>
      </header>

      {/* Main content */}
      <main className="py-4">
        <Outlet />
      </main>
    </div>
  );
}
