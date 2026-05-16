import { createFileRoute } from '@tanstack/react-router';
import { InboxScreen } from '../features/operating/screens/InboxScreen.js';

export const Route = createFileRoute('/workspace/inbox')({
  component: InboxScreen,
});
