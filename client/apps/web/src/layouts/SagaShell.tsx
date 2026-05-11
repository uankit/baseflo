import type { ReactNode } from 'react';
import { Link } from '@tanstack/react-router';
import { IconArrowLeft } from '@baseflo/ui/icons';
import { Button } from '@baseflo/ui';
import { TopBar } from './TopBar.js';

interface SagaShellProps {
  orgSlug: string;
  orgName: string;
  projectSlug: string;
  projectName: string;
  onCancel?: () => void;
  children: ReactNode;
}

export function SagaShell({
  orgSlug,
  orgName,
  projectName,
  onCancel,
  children,
}: SagaShellProps) {
  return (
    <div className="flex min-h-full flex-col bg-bg">
      <TopBar orgSlug={orgSlug} orgName={orgName} projectName={projectName} />
      <div className="flex items-center justify-between border-b border-border bg-surface px-4 py-3">
        <Link
          to="/o/$orgSlug"
          params={{ orgSlug }}
          className="inline-flex items-center gap-1 text-sm text-fg-muted hover:text-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-border-focus rounded px-2 py-1"
        >
          <IconArrowLeft className="h-3.5 w-3.5" /> Back to {orgName}
        </Link>
        <span className="text-sm text-fg-muted">
          Building <span className="text-fg">{projectName}</span>
        </span>
        {onCancel && (
          <Button variant="ghost" size="sm" onClick={onCancel}>
            Cancel
          </Button>
        )}
      </div>
      <main role="main" className="flex-1 overflow-y-auto">
        <div className="mx-auto h-full w-full max-w-7xl px-6 py-6">{children}</div>
      </main>
    </div>
  );
}
