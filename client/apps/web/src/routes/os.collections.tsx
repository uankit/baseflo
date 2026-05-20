import { createFileRoute } from '@tanstack/react-router';

export const Route = createFileRoute('/os/collections')({
  component: CollectionsPage,
});

function CollectionsPage() {
  return (
    <div className="p-8 text-center">
      <h1 className="text-xl font-bold text-ink">Collections</h1>
      <p className="text-ink/60 mt-2">Coming soon — manage pending bills and send reminders.</p>
    </div>
  );
}
