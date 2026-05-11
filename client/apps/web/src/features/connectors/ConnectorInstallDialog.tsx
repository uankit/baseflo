import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { useForm } from 'react-hook-form';
import {
  Button,
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  ErrorCallout,
  Input,
  Label,
  Spinner,
  Switch,
} from '@baseflo/ui';
import {
  PostgresInstallPayloadSchema,
  StripeInstallPayloadSchema,
  type ConnectorKind,
  type PostgresInstallPayload,
  type StripeInstallPayload,
} from '@baseflo/contracts';
import { zodResolver } from '../../lib/forms/zodResolver.js';
import { useGateway } from '../../providers/GatewayProvider.js';

/**
 * One dialog per connector kind, each wired to its real backend route:
 *
 *   postgres → POST /api/v1/connectors/postgres/install (DSN, validates SELECT 1)
 *   stripe   → POST /api/v1/connectors/stripe/install (API key, validates /v1/account)
 *   csv|excel→ multipart POST /api/v1/connectors/upload
 *   shopify  → window.location.assign('/api/v1/oauth/shopify/install?...&shop_domain=...')
 *   google_sheets → window.location.assign('/api/v1/oauth/google_sheets/install?...&spreadsheet_id=...')
 */

interface Props {
  kind: ConnectorKind;
  projectId: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onInstalled: () => void;
}

export function ConnectorInstallDialog(props: Props) {
  const { kind } = props;
  if (kind === 'postgres') return <PostgresInstall {...props} />;
  if (kind === 'stripe') return <StripeInstall {...props} />;
  if (kind === 'csv' || kind === 'excel') return <FileUploadInstall {...props} />;
  if (kind === 'shopify') return <ShopifyOAuthInstall {...props} />;
  if (kind === 'google_sheets') return <SheetsOAuthInstall {...props} />;
  return null;
}

// ── Postgres ───────────────────────────────────────────────────────────────
function PostgresInstall({ projectId, open, onOpenChange, onInstalled }: Props) {
  const gateway = useGateway();
  const form = useForm<PostgresInstallPayload>({
    resolver: zodResolver(PostgresInstallPayloadSchema),
    defaultValues: { displayName: 'Production Postgres', connectionString: '' },
  });

  const install = useMutation({
    mutationFn: (payload: PostgresInstallPayload) =>
      gateway.connectors.installPostgres(
        projectId,
        payload.connectionString,
        payload.displayName,
      ),
    onSuccess: onInstalled,
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Connect Postgres</DialogTitle>
          <DialogDescription>
            Read-only connection string. We test it with `SELECT 1` and store it
            envelope-encrypted.
          </DialogDescription>
        </DialogHeader>
        <form
          className="flex flex-col gap-4"
          onSubmit={form.handleSubmit((v) => install.mutate(v))}
          noValidate
        >
          <div className="flex flex-col gap-1">
            <Label htmlFor="pg-name">Display name</Label>
            <Input id="pg-name" {...form.register('displayName')} />
          </div>
          <div className="flex flex-col gap-1">
            <Label htmlFor="pg-conn">Connection string</Label>
            <Input
              id="pg-conn"
              type="password"
              placeholder="postgres://user:pass@host:5432/db"
              {...form.register('connectionString')}
            />
            {form.formState.errors.connectionString && (
              <p className="text-sm text-danger">
                {form.formState.errors.connectionString.message}
              </p>
            )}
          </div>
          {install.isError && (
            <ErrorCallout
              title="Couldn't connect"
              message="Check the DSN and that the host is reachable from this server."
            />
          )}
          <DialogFooter>
            <Button type="button" variant="ghost" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={install.isPending}>
              {install.isPending ? <Spinner className="mr-2" /> : null}
              Test &amp; connect
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

// ── Stripe ─────────────────────────────────────────────────────────────────
function StripeInstall({ projectId, open, onOpenChange, onInstalled }: Props) {
  const gateway = useGateway();
  const form = useForm<StripeInstallPayload>({
    resolver: zodResolver(StripeInstallPayloadSchema),
    defaultValues: { displayName: 'Stripe', apiKey: '', testMode: false },
  });

  const install = useMutation({
    mutationFn: (payload: StripeInstallPayload) =>
      gateway.connectors.installStripe(projectId, payload.apiKey),
    onSuccess: onInstalled,
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Connect Stripe</DialogTitle>
          <DialogDescription>
            Use a restricted key with read access where possible. We validate it
            against Stripe's `/v1/account` before persisting.
          </DialogDescription>
        </DialogHeader>
        <form
          className="flex flex-col gap-4"
          onSubmit={form.handleSubmit((v) => install.mutate(v))}
          noValidate
        >
          <div className="flex flex-col gap-1">
            <Label htmlFor="stripe-name">Display name</Label>
            <Input id="stripe-name" {...form.register('displayName')} />
          </div>
          <div className="flex flex-col gap-1">
            <Label htmlFor="stripe-key">API key</Label>
            <Input
              id="stripe-key"
              type="password"
              placeholder="sk_…"
              {...form.register('apiKey')}
            />
          </div>
          <div className="flex items-center gap-2">
            <Switch
              checked={form.watch('testMode')}
              onCheckedChange={(v) => form.setValue('testMode', v as boolean)}
              id="stripe-test"
            />
            <Label htmlFor="stripe-test">Use test-mode key</Label>
          </div>
          {install.isError && (
            <ErrorCallout
              title="Stripe rejected the key"
              message="Check that the key is correct and not revoked."
            />
          )}
          <DialogFooter>
            <Button type="button" variant="ghost" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={install.isPending}>
              {install.isPending ? <Spinner className="mr-2" /> : null}Connect
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

// ── File upload (CSV / Excel) ─────────────────────────────────────────────
function FileUploadInstall({ kind, projectId, open, onOpenChange, onInstalled }: Props) {
  const gateway = useGateway();
  const [file, setFile] = useState<File | null>(null);
  const [displayName, setDisplayName] = useState('');

  const install = useMutation({
    mutationFn: () => {
      if (!file) throw new Error('No file selected');
      return gateway.connectors.uploadInstall(
        projectId,
        kind as 'csv' | 'excel',
        file,
        displayName || file.name,
      );
    },
    onSuccess: onInstalled,
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Upload {kind === 'csv' ? 'CSV' : 'Excel'}</DialogTitle>
          <DialogDescription>
            We introspect column types and sample rows on upload.
          </DialogDescription>
        </DialogHeader>
        <div className="flex flex-col gap-4">
          <div className="flex flex-col gap-1">
            <Label htmlFor="file-name">Display name</Label>
            <Input
              id="file-name"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              placeholder={file?.name ?? `My ${kind} dataset`}
            />
          </div>
          <label
            htmlFor="file-input"
            className="flex cursor-pointer flex-col items-center gap-2 rounded-md border border-dashed border-border bg-surface-2 px-6 py-10 text-center hover:bg-surface focus-within:ring-2 focus-within:ring-border-focus"
          >
            <span className="text-sm font-medium">
              {file ? file.name : `Drop a ${kind === 'csv' ? '.csv' : '.xlsx'} file here`}
            </span>
            <span className="text-xs text-fg-muted">or click to browse</span>
            <input
              id="file-input"
              type="file"
              accept={kind === 'csv' ? '.csv' : '.xlsx,.xlsm'}
              className="sr-only"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            />
          </label>
          {install.isError && (
            <ErrorCallout
              title="Upload failed"
              message={
                install.error instanceof Error
                  ? install.error.message
                  : 'Try again with a smaller file.'
              }
            />
          )}
        </div>
        <DialogFooter>
          <Button type="button" variant="ghost" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={() => install.mutate()} disabled={!file || install.isPending}>
            {install.isPending ? <Spinner className="mr-2" /> : null}
            Upload &amp; connect
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ── Shopify OAuth ─────────────────────────────────────────────────────────
function ShopifyOAuthInstall({ projectId, open, onOpenChange }: Props) {
  const [shopDomain, setShopDomain] = useState('');

  const start = () => {
    const trimmed = shopDomain.trim();
    if (!trimmed.endsWith('.myshopify.com')) return;
    const url = `/api/v1/oauth/shopify/install?project_id=${encodeURIComponent(
      projectId,
    )}&shop_domain=${encodeURIComponent(trimmed)}`;
    // Backend issues the redirect to Shopify's authorize URL.
    window.location.assign(url);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Connect Shopify</DialogTitle>
          <DialogDescription>
            We send you to Shopify to grant access. After approval you'll come back here.
          </DialogDescription>
        </DialogHeader>
        <div className="flex flex-col gap-4">
          <div className="flex flex-col gap-1">
            <Label htmlFor="shop-domain">Store domain</Label>
            <Input
              id="shop-domain"
              placeholder="your-store.myshopify.com"
              value={shopDomain}
              onChange={(e) => setShopDomain(e.target.value)}
            />
            <p className="text-xs text-fg-muted">
              Must end with `.myshopify.com`.
            </p>
          </div>
        </div>
        <DialogFooter>
          <Button type="button" variant="ghost" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={start} disabled={!shopDomain.endsWith('.myshopify.com')}>
            Continue with Shopify
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ── Google Sheets OAuth ───────────────────────────────────────────────────
function SheetsOAuthInstall({ projectId, open, onOpenChange }: Props) {
  const [spreadsheetId, setSpreadsheetId] = useState('');

  const start = () => {
    const trimmed = spreadsheetId.trim();
    if (trimmed.length < 10) return;
    const returnTo = `${window.location.origin}${window.location.pathname}`;
    const url = `/api/v1/oauth/google_sheets/install?project_id=${encodeURIComponent(
      projectId,
    )}&spreadsheet_id=${encodeURIComponent(trimmed)}&redirect=true&return_to=${encodeURIComponent(
      returnTo,
    )}`;
    window.location.assign(url);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Connect Google Sheets</DialogTitle>
          <DialogDescription>
            Paste the spreadsheet id (the long string in the sheet URL between
            `/d/` and `/edit`).
          </DialogDescription>
        </DialogHeader>
        <div className="flex flex-col gap-4">
          <div className="flex flex-col gap-1">
            <Label htmlFor="spreadsheet-id">Spreadsheet ID</Label>
            <Input
              id="spreadsheet-id"
              placeholder="1AbC2dEfG3hIjK4lMnOpQrStUvWxYz0123456789"
              value={spreadsheetId}
              onChange={(e) => setSpreadsheetId(e.target.value)}
            />
          </div>
        </div>
        <DialogFooter>
          <Button type="button" variant="ghost" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={start} disabled={spreadsheetId.length < 10}>
            Continue with Google
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
