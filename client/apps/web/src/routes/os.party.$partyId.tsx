import { createFileRoute } from '@tanstack/react-router';
import { PartyDrillDown } from '../os/components/PartyDrillDown';

export const Route = createFileRoute('/os/party/$partyId')({
  component: PartyDrillDown,
});
