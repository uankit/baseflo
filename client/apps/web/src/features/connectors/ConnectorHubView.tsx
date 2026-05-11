import { useMemo, useState } from 'react';
import { useNavigate, useParams } from '@tanstack/react-router';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { motion } from 'framer-motion';
import {
  Button,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
  StatusChip,
  EmptyState,
  ErrorCallout,
  LoadingSkeletonCard,
  Spinner,
  useToast,
} from '@baseflo/ui';
import {
  IconConnectors,
  IconPlus,
  IconTrash,
  IconDatabase,
  IconZap,
  IconShieldCheck,
  IconSparkles,
} from '@baseflo/ui/icons';
import type { Connector, ConnectorKind } from '@baseflo/contracts';
import { useGateway } from '../../providers/GatewayProvider.js';
import { ConnectorInstallDialog } from './ConnectorInstallDialog.js';

const CATALOG: Array<{ kind: ConnectorKind; label: string; description: string; auth: string; specialty: string }> = [
  { kind: 'postgres', label: 'Postgres', description: 'Direct connection to your database.', auth: 'Connection string', specialty: 'Structured Records' },
  { kind: 'csv', label: 'CSV', description: 'Upload one-off datasets as files.', auth: 'File upload', specialty: 'Batch Import' },
  { kind: 'excel', label: 'Excel', description: 'Import .xlsx workbooks.', auth: 'File upload', specialty: 'Spreadsheet Data' },
  { kind: 'google_sheets', label: 'Google Sheets', description: 'Live read with Drive Push notifications.', auth: 'OAuth', specialty: 'Live Sync' },
  { kind: 'shopify', label: 'Shopify', description: 'Customers, orders, products + webhooks.', auth: 'OAuth', specialty: 'E-commerce' },
  { kind: 'stripe', label: 'Stripe', description: 'Charges, customers, subscriptions, refunds.', auth: 'API key', specialty: 'Payments' },
];

export function ConnectorHubView() {
  const params = useParams({ from: '/o/$orgSlug/p/$projectSlug/v/$versionId' });
  const gateway = useGateway();
  const queryClient = useQueryClient();
  const toast = useToast();
  const [installKind, setInstallKind] = useState<ConnectorKind | null>(null);
  const navigate = useNavigate();

  const projectQuery = useQuery({
    queryKey: ['project', params.orgSlug, params.projectSlug],
    queryFn: () => gateway.projects.get(params.orgSlug, params.projectSlug),
  });

  const projectId = projectQuery.data?.id ?? null;

  const connectorsQuery = useQuery({
    queryKey: ['connectors', projectId],
    queryFn: () => gateway.connectors.list(projectId!),
    enabled: !!projectId,
  });

  const startSaga = useMutation({
    mutationFn: () =>
      gateway.sagas.start(
        projectId!,
        projectQuery.data?.description ?? 'Build my workspace from connected sources.',
      ),
    onSuccess: (resp) => {
      navigate({
        to: '/o/$orgSlug/p/$projectSlug/saga/$conversationId',
        params: {
          orgSlug: params.orgSlug,
          projectSlug: params.projectSlug,
          conversationId: resp.conversationId,
        },
      });
    },
  });

  const revoke = useMutation({
    mutationFn: (id: string) => gateway.connectors.revoke(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['connectors', projectId] });
      toast.push({ title: 'Connector revoked', variant: 'info' });
    },
  });

  const installed = useMemo(() => connectorsQuery.data ?? [], [connectorsQuery.data]);
  const installedKinds = useMemo(() => new Set(installed.map((c) => c.kind)), [installed]);

  if (projectQuery.isPending || connectorsQuery.isPending) {
    return (
      <div className="grid gap-4 lg:grid-cols-2">
        <LoadingSkeletonCard />
        <LoadingSkeletonCard />
      </div>
    );
  }

  if (projectQuery.isError || connectorsQuery.isError) {
    return (
      <ErrorCallout
        title="Couldn't load connectors"
        message="Try again. If it keeps happening, contact support."
        action={{ label: 'Retry', onClick: () => connectorsQuery.refetch() }}
      />
    );
  }

  return (
    <div className="flex flex-col gap-8">
      {/* Mission Header */}
      <motion.header
        initial={{ opacity: 0, y: -8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.35 }}
        className="relative overflow-hidden rounded-2xl border border-border bg-surface p-6"
      >
        <div className="absolute inset-0 bg-atmospheric opacity-40" />
        <div className="absolute inset-0 bg-grid-dots opacity-20" />
        <div className="relative flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex flex-col gap-1">
            <div className="flex items-center gap-2">
              <IconConnectors size={16} className="text-accent" />
              <span className="text-[10px] font-bold uppercase tracking-[0.15em] text-fg-subtle">
                Assembly Bay
              </span>
            </div>
            <h1 className="text-xl font-semibold text-fg">Assemble your intelligence team</h1>
            <p className="text-sm text-fg-muted">
              Each source is a specialist. Add as many as you want — we'll reconcile them into a unified schema.
            </p>
          </div>
          <Button
            disabled={installed.length === 0 || startSaga.isPending}
            onClick={() => startSaga.mutate()}
            className="relative overflow-hidden transition-all hover:shadow-[0_0_20px_hsl(var(--color-accent)/0.25)]"
          >
            {startSaga.isPending ? <Spinner className="mr-2" /> : <IconZap size={14} className="mr-2" />}
            {installed.length === 0 ? 'Add a source first' : 'Launch mission'}
          </Button>
        </div>
      </motion.header>

      {installed.length === 0 ? (
        <EmptyState
          icon={<IconConnectors className="h-10 w-10" />}
          title="Add your first source"
          description="Pick from the catalog below. Each one tells you what authentication it needs."
        />
      ) : (
        <motion.section
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35, delay: 0.1 }}
        >
          <div className="mb-3 flex items-center gap-2">
            <IconShieldCheck size={14} className="text-success" />
            <h2 className="text-xs font-semibold uppercase tracking-wider text-fg-subtle">
              Active Squad ({installed.length})
            </h2>
          </div>
          <ul className="grid gap-3 sm:grid-cols-2">
            {installed.map((c, i) => (
              <motion.li
                key={c.id}
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.3, delay: 0.15 + i * 0.05 }}
              >
                <InstalledCard
                  connector={c}
                  onRevoke={() => revoke.mutate(c.id)}
                  revoking={revoke.isPending}
                />
              </motion.li>
            ))}
          </ul>
        </motion.section>
      )}

      {/* Specialist Catalog */}
      <motion.section
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.35, delay: 0.15 }}
      >
        <div className="mb-3 flex items-center gap-2">
          <IconDatabase size={14} className="text-accent" />
          <h2 className="text-xs font-semibold uppercase tracking-wider text-fg-subtle">
            Specialist Catalog
          </h2>
        </div>
        <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {CATALOG.map((c, i) => {
            const already = installedKinds.has(c.kind);
            return (
              <motion.li
                key={c.kind}
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.3, delay: 0.2 + i * 0.04 }}
              >
                <Card
                  className={
                    already
                      ? 'border-success/20 bg-success/[0.02]'
                      : 'transition-all hover:border-accent/20 hover:shadow-[0_0_16px_hsl(var(--color-accent)/0.06)]'
                  }
                >
                  <CardHeader>
                    <div className="flex items-center justify-between">
                      <CardTitle>{c.label}</CardTitle>
                      {already && (
                        <span className="flex items-center gap-1 rounded-full bg-success/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-success">
                          <IconSparkles size={10} />
                          Active
                        </span>
                      )}
                    </div>
                    <CardDescription>{c.description}</CardDescription>
                  </CardHeader>
                  <CardContent className="flex items-center justify-between">
                    <div className="flex flex-col gap-1">
                      <span className="text-[10px] font-semibold uppercase tracking-wider text-accent">
                        {c.specialty}
                      </span>
                      <span className="text-xs text-fg-muted">Auth: {c.auth}</span>
                    </div>
                    <Button
                      size="sm"
                      variant={already ? 'ghost' : 'secondary'}
                      onClick={() => setInstallKind(c.kind)}
                      disabled={already}
                    >
                      <IconPlus className="mr-1 h-3.5 w-3.5" /> {already ? 'Connected' : 'Recruit'}
                    </Button>
                  </CardContent>
                </Card>
              </motion.li>
            );
          })}
        </ul>
      </motion.section>

      {installKind && projectId && (
        <ConnectorInstallDialog
          kind={installKind}
          projectId={projectId}
          open={true}
          onOpenChange={(open) => {
            if (!open) setInstallKind(null);
          }}
          onInstalled={() => {
            queryClient.invalidateQueries({ queryKey: ['connectors', projectId] });
            setInstallKind(null);
            toast.push({ title: 'Source connected', variant: 'success' });
          }}
        />
      )}
    </div>
  );
}

function InstalledCard({
  connector,
  onRevoke,
  revoking,
}: {
  connector: Connector;
  onRevoke: () => void;
  revoking: boolean;
}) {
  return (
    <Card className="group relative overflow-hidden border-border transition-all hover:border-success/30 hover:shadow-[0_0_16px_hsl(var(--color-success)/0.08)]">
      <div className="absolute top-0 left-0 h-full w-[3px] bg-success/40 transition-all group-hover:bg-success/60" />
      <CardHeader className="pl-5">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-accent-soft">
              <IconDatabase size={14} className="text-accent" />
            </div>
            <CardTitle className="capitalize">{connector.displayName}</CardTitle>
          </div>
          <StatusChip value={connector.status} />
        </div>
        <CardDescription className="capitalize pl-9">{connector.kind}</CardDescription>
      </CardHeader>
      <CardContent className="flex items-center justify-between pl-5 text-xs text-fg-muted">
        <div className="flex items-center gap-2">
          <span className="h-1.5 w-1.5 rounded-full bg-success shadow-[0_0_4px_hsl(var(--color-success)/0.5)]" />
          <span>
            {connector.rowCountEstimate
              ? `${connector.rowCountEstimate.toLocaleString()} rows`
              : 'Pending sync'}
          </span>
        </div>
        <div className="flex gap-2">
          <Button size="sm" variant="ghost" onClick={onRevoke} disabled={revoking} aria-label="Revoke">
            <IconTrash className="h-3.5 w-3.5 text-danger" />
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
