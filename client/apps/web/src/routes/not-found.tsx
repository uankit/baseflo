import { createFileRoute } from '@tanstack/react-router';

export const Route = createFileRoute('/not-found')({
  component: NotFoundPage,
});

function NotFoundPage() {
  return (
    <div className="flex h-screen items-center justify-center bg-gray-950 text-gray-500">
      <div className="text-center">
        <h1 className="text-2xl font-semibold text-white">404</h1>
        <p className="mt-2">Page not found</p>
        <a href="/" className="mt-4 inline-block text-sm text-gray-300 underline">Go home</a>
      </div>
    </div>
  );
}
