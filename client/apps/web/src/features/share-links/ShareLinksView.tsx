import { useState } from 'react';
import { useParams } from '@tanstack/react-router';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { format } from 'date-fns';
import {
  Badge,
  Button,
  Card,
  CardContent,
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  EmptyState,
  ErrorCallout,
  Label,
  Spinner,
  useToast,
} from '@baseflo/ui';
import { IconCopy, IconTrash } from '@baseflo/ui/icons';
import type { CreateShareLinkRequest, SharePermission } from '@baseflo/contracts';
import { useGateway } from '../../providers/GatewayProvider.js';

export function ShareLinksView() {
  const params = useParams({
    from: '/o/$orgSlug/p/$projectSlug/v/$versionId',
  });
  const gateway = useGateway();
  const queryClient = useQueryClient();
  const toast = useToast();
  const [open, setOpen] = useState(false);

  const projectQuery = useQuery({
    queryKey: ['project', params.orgSlug, params.projectSlug],
    queryFn: () => gateway.projects.get(params.orgSlug, params.projectSlug),
  });
  const projectId = projectQuery.data?.id ?? null;

  const linksQuery = useQuery({
    queryKey: ['share-links', projectId],
    queryFn: () => gateway.shareLinks.list(projectId!),
    enabled: !!projectId,
  });

  const revoke = useMutation({
    mutationFn: (id: string) => gateway.shareLinks.revoke(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['share-links', projectId] });
      toast.push({ title: 'Share link revoked', variant: 'info' });
    },
  });

  return (
    <div className="flex flex-col gap-6">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-fg">Share links</h1>
          <p className="text-sm text-fg-muted">
            Read-only public views. PII, audit, and traces are always redacted.
          </p>
        </div>
        <Button onClick={() => setOpen(true)}>Create link</Button>
      </header>

      <Card>
        <CardContent className="p-0">
          {linksQuery.isPending ? (
            <p className="p-4 text-sm text-fg-muted">Loading…</p>
          ) : linksQuery.isError ? (
            <ErrorCallout title="Couldn't load share links" message="Try again." />
          ) : linksQuery.data.length === 0 ? (
            <EmptyState
              title="No share links yet"
              description="Create one for investors, stakeholders, or your own bookmark."
              action={{ label: 'Create link', onClick: () => setOpen(true) }}
            />
          ) : (
            <ul className="divide-y divide-border">
              {linksQuery.data.map((link) => (
                <li key={link.id} className="flex items-center justify-between gap-4 p-4">
                  <div className="flex flex-col gap-1">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-sm">{link.url}</span>
                      <button
                        type="button"
                        onClick={() => {
                          navigator.clipboard.writeText(link.url);
                          toast.push({ title: 'Copied', variant: 'success' });
                        }}
                        aria-label="Copy URL"
                        className="rounded p-1 text-fg-muted hover:text-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-border-focus"
                      >
                        <IconCopy className="h-3.5 w-3.5" />
                      </button>
                    </div>
                    <div className="flex items-center gap-2 text-xs text-fg-muted">
                      <Badge variant="neutral">{permLabel(link.permissions)}</Badge>
                      {link.hasPassword && <Badge variant="info">Password</Badge>}
                      <span>
                        {link.expiresAt
                          ? `Expires ${format(new Date(link.expiresAt), 'MMM d, yyyy')}`
                          : 'No expiry'}
                      </span>
                      {link.notes && <span>· {link.notes}</span>}
                    </div>
                  </div>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => revoke.mutate(link.id)}
                    disabled={revoke.isPending}
                    aria-label="Revoke"
                  >
                    <IconTrash className="h-3.5 w-3.5 text-danger" />
                  </Button>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>

      {open && projectId && (
        <CreateShareLinkDialog
          projectId={projectId}
          versionId={params.versionId}
          onClose={() => setOpen(false)}
          onCreated={() => {
            queryClient.invalidateQueries({ queryKey: ['share-links', projectId] });
            setOpen(false);
            toast.push({ title: 'Share link created', variant: 'success' });
          }}
        />
      )}
    </div>
  );
}

function CreateShareLinkDialog({
  projectId,
  versionId,
  onClose,
  onCreated,
}: {
  projectId: string;
  versionId: string;
  onClose: () => void;
  onCreated: () => void;
}) {
  const gateway = useGateway();
  const [permissions, setPermissions] = useState<SharePermission>('full_read_only');
  const [expiresInHours, setExpiresInHours] = useState<number | null>(168);

  const create = useMutation({
    mutationFn: () => {
      const req: CreateShareLinkRequest = {
        versionId,
        permissions,
        expiresInHours,
      };
      return gateway.shareLinks.create(projectId, req);
    },
    onSuccess: onCreated,
  });

  return (
    <Dialog open={true} onOpenChange={(o) => !o && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Create share link</DialogTitle>
          <DialogDescription>
            Anyone with this link can view the workspace read-only.
          </DialogDescription>
        </DialogHeader>
        <div className="flex flex-col gap-4">
          <div className="flex flex-col gap-1">
            <Label>Permissions</Label>
            <div className="grid gap-2">
              {(['overview_only', 'overview_kpis', 'full_read_only'] as const).map((p) => (
                <button
                  key={p}
                  type="button"
                  onClick={() => setPermissions(p)}
                  aria-pressed={permissions === p}
                  className={`rounded-md border p-3 text-left text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-border-focus ${
                    permissions === p
                      ? 'border-accent bg-accent-soft'
                      : 'border-border bg-surface hover:bg-surface-2'
                  }`}
                >
                  {permLabel(p)}
                </button>
              ))}
            </div>
          </div>
          <div className="flex flex-col gap-1">
            <Label>Expires</Label>
            <select
              className="h-10 rounded-md border border-border bg-surface px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-border-focus"
              value={String(expiresInHours)}
              onChange={(e) =>
                setExpiresInHours(e.target.value === 'null' ? null : Number(e.target.value))
              }
            >
              <option value="24">24 hours</option>
              <option value="168">7 days</option>
              <option value="720">30 days</option>
              <option value="null">No expiry</option>
            </select>
          </div>
          {create.isError && (
            <ErrorCallout title="Couldn't create" message="Try again." />
          )}
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={() => create.mutate()} disabled={create.isPending}>
            {create.isPending ? <Spinner className="mr-2" /> : null}Create
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function permLabel(p: SharePermission): string {
  switch (p) {
    case 'overview_only':
      return 'Overview only';
    case 'overview_kpis':
      return 'Overview + KPIs';
    case 'full_read_only':
      return 'Full read-only';
  }
}
