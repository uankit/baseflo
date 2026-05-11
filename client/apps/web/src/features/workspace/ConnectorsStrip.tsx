import { useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Badge, SyncPulse } from '@baseflo/ui';
import { cn } from '@baseflo/ui/lib/utils';
import type { Connector } from '@baseflo/contracts';
import { useGateway } from '../../providers/GatewayProvider.js';

interface ConnectorsStripProps {
  projectId: string;
}

/**
 * A live status row for connected sources. Always visible in the workspace
 * top region. Each connector chip surfaces:
 *   - kind label (Stripe, Postgres, Sheets, …)
 *   - status (connected / error / expired / revoked)
 *   - relative last-sync time, ticking once a minute
 *   - a sync-pulse dot when the connector synced in the last 60s
 *
 * No hover required to see this — it's the trust signal that says "your data
 * is current right now."
 */
export function ConnectorsStrip({ projectId }: ConnectorsStripProps) {
  const gateway = useGateway();
  const query = useQuery({
    queryKey: ['connectors', projectId],
    queryFn: () => gateway.connectors.list(projectId),
    refetchInterval: 60_000,
  });

  // Tick-now drives the relative timestamps (e.g. "14s ago") without
  // re-querying the network.
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    const id = window.setInterval(() => setNow(Date.now()), 30_000);
    return () => window.clearInterval(id);
  }, []);

  if (query.isPending || query.isError || !query.data || query.data.length === 0) {
    return null;
  }

  return (
    <ul
      role="list"
      aria-label="Connected sources"
      className="flex flex-wrap items-center gap-2"
    >
      {query.data.map((c) => (
        <ConnectorChip key={c.id} connector={c} now={now} />
      ))}
    </ul>
  );
}

function ConnectorChip({ connector, now }: { connector: Connector; now: number }) {
  const lastSyncMs = connector.lastSyncAt ? Date.parse(connector.lastSyncAt) : null;
  const ageSec = lastSyncMs ? Math.max(0, Math.round((now - lastSyncMs) / 1000)) : null;
  const isFresh = ageSec !== null && ageSec < 60;

  return (
    <li>
      <Badge
        variant={
          connector.status === 'connected'
            ? 'success'
            : connector.status === 'error'
              ? 'danger'
              : connector.status === 'expired'
                ? 'warning'
                : 'neutral'
        }
        className={cn('gap-2 px-3 py-1', !isFresh && 'opacity-90')}
      >
        <span className="capitalize">{connector.kind}</span>
        <span className="font-mono text-[10px] text-fg-muted">
          {ageSec === null ? 'never' : formatRelativeAge(ageSec)}
        </span>
        {isFresh && <SyncPulse />}
      </Badge>
    </li>
  );
}

function formatRelativeAge(sec: number): string {
  if (sec < 60) return `${sec}s ago`;
  const m = Math.floor(sec / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  const d = Math.floor(h / 24);
  return `${d}d ago`;
}
