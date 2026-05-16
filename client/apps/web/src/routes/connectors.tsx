import { Link, createFileRoute, redirect } from '@tanstack/react-router';
import { ConnectorSetup } from '../features/connectors/ConnectorSetup.js';
import { ScreenFrame, SecondaryButton } from '../features/common/components/StatePanels.js';

export const Route = createFileRoute('/connectors')({
  beforeLoad: async ({ context, location }) => {
    try {
      await context.gateway.auth.me();
    } catch {
      throw redirect({
        to: '/sign-in',
        search: { redirect: location.href },
      });
    }
  },
  component: ConnectorsPage,
});

function ConnectorsPage() {
  return (
    <div className="min-h-screen bg-paper text-ink">
      <ScreenFrame
        eyebrow="connectors"
        title="Connect the data Baseflo should learn from"
        summary="After selection, each resource is canonicalized, profiled, and fed into the operating pipeline."
        action={
          <Link to="/workspace/sources">
            <SecondaryButton>back to sources</SecondaryButton>
          </Link>
        }
      >
        <ConnectorSetup />
      </ScreenFrame>
    </div>
  );
}
