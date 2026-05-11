import { createFileRoute, Outlet } from '@tanstack/react-router';
import { AppShell } from '../layouts/AppShell.js';

export const Route = createFileRoute('/p/$projectId')({
  component: ProjectLayout,
});

function ProjectLayout() {
  return (
    <AppShell>
      <Outlet />
    </AppShell>
  );
}
