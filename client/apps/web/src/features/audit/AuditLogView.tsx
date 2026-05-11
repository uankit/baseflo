import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { format } from 'date-fns';
import {
  Badge,
  Card,
  CardContent,
  EmptyState,
  ErrorCallout,
  LoadingSkeletonRow,
} from '@baseflo/ui';
import type { AuditAction } from '@baseflo/contracts';
import { useGateway } from '../../providers/GatewayProvider.js';

interface Props {
  orgSlug: string;
  projectId?: string;
}

export function AuditLogView({ orgSlug, projectId }: Props) {
  const gateway = useGateway();
  const [actionFilter, setActionFilter] = useState<AuditAction | ''>('');

  const auditQuery = useQuery({
    queryKey: ['audit', orgSlug, projectId, actionFilter],
    queryFn: () =>
      gateway.audit.list(orgSlug, {
        projectId,
        ...(actionFilter ? { action: actionFilter as AuditAction } : {}),
      }),
  });

  return (
    <div className="flex flex-col gap-4">
      <header>
        <h1 className="text-xl font-semibold text-fg">Audit log</h1>
        <p className="text-sm text-fg-muted">
          Append-only. Showing the last year. Export as CSV from Settings → Audit.
        </p>
      </header>

      <div className="flex items-center gap-3">
        <select
          value={actionFilter}
          onChange={(e) => setActionFilter(e.target.value as AuditAction | '')}
          className="h-10 rounded-md border border-border bg-surface px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-border-focus"
          aria-label="Filter by action"
        >
          <option value="">All actions</option>
          <option value="auth.login">auth.login</option>
          <option value="auth.logout">auth.logout</option>
          <option value="connector.connect">connector.connect</option>
          <option value="connector.revoke">connector.revoke</option>
          <option value="pii.reveal">pii.reveal</option>
          <option value="export">export</option>
          <option value="refinement.apply">refinement.apply</option>
          <option value="share.create">share.create</option>
          <option value="share.revoke">share.revoke</option>
        </select>
      </div>

      <Card>
        <CardContent className="p-0">
          {auditQuery.isPending ? (
            <div>
              {[0, 1, 2, 3].map((i) => (
                <LoadingSkeletonRow key={i} />
              ))}
            </div>
          ) : auditQuery.isError ? (
            <ErrorCallout title="Couldn't load audit log" message="Try again." />
          ) : auditQuery.data.events.length === 0 ? (
            <EmptyState title="No audit events match" />
          ) : (
            <ul className="divide-y divide-border">
              {auditQuery.data.events.map((event) => (
                <li
                  key={event.id}
                  className="flex items-center justify-between gap-4 p-4 text-sm"
                >
                  <div className="flex flex-col gap-1">
                    <div className="flex items-center gap-2">
                      <Badge variant={event.action === 'pii.reveal' ? 'warning' : 'neutral'}>
                        {event.action}
                      </Badge>
                      <span className="text-fg-muted">{event.actorLabel}</span>
                      <span className="text-fg-muted">→</span>
                      <span className="font-mono text-xs text-fg">{event.targetLabel}</span>
                    </div>
                    {event.ipAddress && (
                      <span className="text-xs text-fg-subtle">{event.ipAddress}</span>
                    )}
                  </div>
                  <span className="text-xs text-fg-muted tabular-nums">
                    {format(new Date(event.createdAt), 'MMM d, h:mm:ss a')}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
