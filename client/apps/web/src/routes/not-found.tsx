import { createFileRoute } from '@tanstack/react-router';
import { NotFoundView } from '../features/system/NotFoundView.js';

export const Route = createFileRoute('/not-found')({
  component: NotFoundView,
});
