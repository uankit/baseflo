import { createFileRoute } from '@tanstack/react-router';
import { BusinessLiveScreen } from '../features/operating/screens/BusinessLiveScreen.js';

export const Route = createFileRoute('/workspace/business')({
  component: BusinessLiveScreen,
});
