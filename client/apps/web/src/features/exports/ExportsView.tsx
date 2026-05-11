import { useState } from 'react';
import { useParams } from '@tanstack/react-router';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { format } from 'date-fns';
import {
  Badge,
  Button,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  Checkbox,
  LoadingSkeletonRow,
  ErrorCallout,
  Spinner,
  StatusChip,
  useToast,
} from '@baseflo/ui';
import { IconDownload, IconShieldAlert } from '@baseflo/ui/icons';
import type { ExportFormat } from '@baseflo/contracts';
import { useGateway } from '../../providers/GatewayProvider.js';

const FORMATS: Array<{ id: ExportFormat; label: string; description: string }> = [
  { id: 'csv', label: 'CSV per table', description: 'One file per table with headers.' },
  { id: 'sql', label: 'Postgres SQL', description: 'DDL + INSERT statements; runnable on a fresh DB.' },
  { id: 'json', label: 'JSON', description: 'Full project blob: IR + KPIs + connectors (no tokens).' },
  { id: 'full', label: 'Full archive (.tar.gz)', description: 'Everything bundled.' },
];

export function ExportsView() {
  const params = useParams({
    from: '/o/$orgSlug/p/$projectSlug/v/$versionId',
  });
  const gateway = useGateway();
  const queryClient = useQueryClient();
  const toast = useToast();
  const [exportFormat, setExportFormat] = useState<ExportFormat>('csv');
  const [includePII, setIncludePII] = useState(false);

  const projectQuery = useQuery({
    queryKey: ['project', params.orgSlug, params.projectSlug],
    queryFn: () => gateway.projects.get(params.orgSlug, params.projectSlug),
  });
  const projectId = projectQuery.data?.id ?? null;

  const historyQuery = useQuery({
    queryKey: ['exports', projectId],
    queryFn: () => gateway.exports.list(projectId!),
    enabled: !!projectId,
  });

  const request = useMutation({
    mutationFn: () => gateway.exports.request(params.versionId, { format: exportFormat, includePII }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['exports', projectId] });
      toast.push({ title: 'Export requested', description: 'It will be ready soon.', variant: 'info' });
    },
  });

  return (
    <div className="flex flex-col gap-6">
      <header>
        <h1 className="text-xl font-semibold text-fg">Exports</h1>
        <p className="text-sm text-fg-muted">
          One-click full export. Take everything and leave at any time — brand promise.
        </p>
      </header>

      <Card>
        <CardHeader>
          <CardTitle>Request export</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <div className="grid gap-3 sm:grid-cols-2">
            {FORMATS.map((f) => (
              <button
                key={f.id}
                type="button"
                onClick={() => setExportFormat(f.id)}
                aria-pressed={exportFormat === f.id}
                className={`flex flex-col items-start gap-1 rounded-md border p-4 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-border-focus ${
                  exportFormat === f.id
                    ? 'border-accent bg-accent-soft'
                    : 'border-border bg-surface hover:bg-surface-2'
                }`}
              >
                <span className="text-sm font-medium text-fg">{f.label}</span>
                <span className="text-xs text-fg-muted">{f.description}</span>
              </button>
            ))}
          </div>
          <div
            className={`flex items-start gap-2 rounded-md border p-3 text-sm ${
              includePII ? 'border-warning/40 bg-warning/10' : 'border-border bg-surface'
            }`}
          >
            <Checkbox
              aria-label="Include PII columns"
              checked={includePII}
              onCheckedChange={(v) => setIncludePII(v === true)}
            />
            <span className="flex flex-col gap-1">
              <span className="flex items-center gap-1 font-medium">
                <IconShieldAlert className="h-3.5 w-3.5" /> Include PII columns
              </span>
              <span className="text-xs text-fg-muted">
                Audit-logged. Org admins receive a notification email.
              </span>
            </span>
          </div>
          {request.isError && (
            <ErrorCallout title="Couldn't request export" message="Try again." />
          )}
          <Button onClick={() => request.mutate()} disabled={request.isPending}>
            {request.isPending ? <Spinner className="mr-2" /> : null}
            Request export
          </Button>
        </CardContent>
      </Card>

      <section>
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-fg-subtle">
          History
        </h2>
        <Card>
          <CardContent className="p-0">
            {historyQuery.isPending ? (
              <LoadingSkeletonRow />
            ) : historyQuery.isError ? (
              <ErrorCallout title="Couldn't load history" message="Try again." />
            ) : historyQuery.data.length === 0 ? (
              <p className="p-4 text-sm text-fg-muted">No exports yet.</p>
            ) : (
              <ul className="divide-y divide-border">
                {historyQuery.data.map((e) => (
                  <li
                    key={e.id}
                    className="flex items-center justify-between gap-4 p-4 text-sm"
                  >
                    <div className="flex items-center gap-3">
                      <Badge variant="neutral" className="uppercase">
                        {e.format}
                      </Badge>
                      <StatusChip value={e.status} />
                      {e.includesPII && (
                        <Badge variant="warning">+PII</Badge>
                      )}
                      <span className="text-xs text-fg-muted">
                        {format(new Date(e.createdAt), 'MMM d, h:mm a')}
                      </span>
                    </div>
                    {e.fileUrl && e.status === 'ready' && (
                      <Button size="sm" variant="secondary" asChild>
                        <a href={e.fileUrl} target="_blank" rel="noreferrer">
                          <IconDownload className="mr-1 h-3.5 w-3.5" /> Download
                        </a>
                      </Button>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      </section>
    </div>
  );
}
