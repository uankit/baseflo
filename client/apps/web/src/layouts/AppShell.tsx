import React from 'react';
import { useAuth } from '../features/auth/hooks/useAuth.js';

interface AppShellProps {
  children: React.ReactNode;
}

export function AppShell({ children }: AppShellProps) {
  const { user, signOut } = useAuth();

  return (
    <div className="flex h-screen bg-gray-950 text-gray-100">
      {/* Sidebar */}
      <aside className="flex w-56 flex-col border-r border-gray-800 bg-gray-950">
        <div className="flex h-14 items-center px-4">
          <span className="text-lg font-semibold tracking-tight text-white">Baseflo</span>
        </div>

        <nav className="flex-1 px-3 py-2 space-y-1">
          <a
            href="/"
            className="flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium text-gray-300 hover:bg-gray-900 hover:text-white"
          >
            <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" /></svg>
            Insights
          </a>
          <a
            href="/connectors"
            className="flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium text-gray-300 hover:bg-gray-900 hover:text-white"
          >
            <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4" /></svg>
            Connectors
          </a>
        </nav>

        <div className="border-t border-gray-800 p-3">
          <div className="flex items-center justify-between">
            <div className="text-xs text-gray-400 truncate">
              {user?.email}
            </div>
            <button
              onClick={() => signOut.mutate()}
              className="text-xs text-gray-500 hover:text-gray-300"
            >
              Log out
            </button>
          </div>
        </div>
      </aside>

      {/* Main */}
      <main className="flex-1 overflow-auto">
        {children}
      </main>
    </div>
  );
}
