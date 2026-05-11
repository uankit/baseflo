import { createFileRoute } from '@tanstack/react-router';
import { UnsupportedView } from '../features/system/UnsupportedView.js';

export const Route = createFileRoute('/unsupported')({
  component: UnsupportedView,
});
