import { createFileRoute } from '@tanstack/react-router';
import { FounderOverview } from '../os/components/FounderOverview';

export const Route = createFileRoute('/os/overview')({
  component: FounderOverview,
});
