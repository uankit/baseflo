import { createFileRoute } from '@tanstack/react-router';
import { AppShell } from '../layouts/AppShell.js';
import { WelcomeWizard } from '../features/onboarding/WelcomeWizard.js';

export const Route = createFileRoute('/welcome')({
  component: WelcomePage,
});

function WelcomePage() {
  return (
    <AppShell>
      <WelcomeWizard />
    </AppShell>
  );
}
