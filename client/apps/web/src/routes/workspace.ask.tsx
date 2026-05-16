import { createFileRoute } from '@tanstack/react-router';
import { z } from 'zod';
import { AskScreen } from '../features/operating/screens/AskScreen.js';

export const Route = createFileRoute('/workspace/ask')({
  validateSearch: z.object({
    q: z.string().optional(),
  }),
  component: AskRoute,
});

function AskRoute() {
  const search = Route.useSearch();
  return <AskScreen initialQuestion={search.q} />;
}
