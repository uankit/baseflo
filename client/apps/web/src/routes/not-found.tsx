import { createFileRoute, Link } from '@tanstack/react-router';

export const Route = createFileRoute('/not-found')({
  component: NotFoundPage,
});

function NotFoundPage() {
  return (
    <div className="flex h-screen items-center justify-center bg-paper text-ink">
      <div className="text-center">
        <h1 className="font-serif text-5xl font-bold italic text-ink">404</h1>
        <p className="mt-3 text-base text-ink/60">This page does not exist.</p>
        <Link
          to="/workspace/business"
          className="mt-5 inline-block border border-ink bg-ink px-4 py-2 text-sm font-semibold uppercase tracking-wider text-paper transition hover:bg-flame hover:border-flame"
        >
          go to business live
        </Link>
      </div>
    </div>
  );
}
