import { Link } from '@tanstack/react-router';
import { Button } from '@baseflo/ui';
import { IconSearch, IconCommand } from '@baseflo/ui/icons';

export function NotFoundView() {
  return (
    <div className="bg-atmospheric bg-grid-dots relative flex min-h-full flex-col items-center justify-center gap-6 px-4 py-12 text-center">
      <div className="animate-fade-in flex flex-col items-center gap-6">
        <div className="flex h-16 w-16 items-center justify-center rounded-2xl border border-border bg-surface shadow-sm">
          <IconSearch className="h-7 w-7 text-fg-muted" />
        </div>
        <div className="flex flex-col gap-2">
          <p className="text-xs font-medium uppercase tracking-wide text-fg-subtle">404</p>
          <h1 className="text-2xl font-semibold text-fg">Lost in the data stream</h1>
          <p className="mx-auto max-w-sm text-sm leading-relaxed text-fg-muted">
            Even our Recon agent couldn't find this page. The signal may have been dropped, or the
            route never existed.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Button asChild>
            <Link to="/">
              <IconCommand className="mr-1.5 h-4 w-4" />
              Back to baseflo
            </Link>
          </Button>
        </div>
      </div>
    </div>
  );
}
