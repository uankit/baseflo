import { createFileRoute } from '@tanstack/react-router';
import { PublicShareView } from '../features/share-page/PublicShareView.js';

export const Route = createFileRoute('/s/$shareToken')({
  component: PublicShareView,
});
