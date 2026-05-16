import { createFileRoute } from '@tanstack/react-router';
import { SourcesScreen } from '../features/operating/screens/SourcesScreen.js';

export const Route = createFileRoute('/workspace/sources')({
  component: SourcesScreen,
});
