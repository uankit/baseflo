import { createFileRoute } from '@tanstack/react-router';
import { BriefScreen } from '../features/operating/screens/BriefScreen.js';

export const Route = createFileRoute('/workspace/brief')({
  component: BriefScreen,
});
