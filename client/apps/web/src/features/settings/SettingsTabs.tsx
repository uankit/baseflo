import { useState, type ReactNode } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useForm } from 'react-hook-form';
import { format } from 'date-fns';
import {
  Badge,
  Button,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  Checkbox,
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  EmptyState,
  ErrorCallout,
  Input,
  Label,
  LoadingSkeletonRow,
  Progress,
  RoleBadge,
  Spinner,
  useToast,
  PlanBadge,
  DeploymentModeBadge,
} from '@baseflo/ui';
import {
  IconCopy,
  IconSettings,
  IconUsers,
  IconDatabase,
  IconLock,
  IconShield,
  IconLayers,
  IconSparkles,
  IconZap,
  IconCommand,
} from '@baseflo/ui/icons';
import {
  CreateApiKeyRequestSchema,
  InviteRequestSchema,
  type ApiKeyScope,
  type CreateApiKeyRequest,
  type InviteRequest,
} from '@baseflo/contracts';
import { zodResolver } from '../../lib/forms/zodResolver.js';
import { useGateway } from '../../providers/GatewayProvider.js';
import { AuditLogView } from '../audit/AuditLogView.js';

// ── shared header component ─────────────────────────────────────────────────
function TabHeader({
  icon,
  title,
  description,
  action,
}: {
  icon: ReactNode;
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex items-start justify-between gap-4 rounded-xl border border-border/60 bg-surface p-5 shadow-sm">
      <div className="flex items-start gap-3">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-accent-soft text-accent">
          {icon}
        </div>
        <div className="flex flex-col gap-0.5">
          <h2 className="text-base font-semibold text-fg">{title}</h2>
          <p className="text-sm text-fg-muted">{description}</p>
        </div>
      </div>
      {action && <div className="shrink-0">{action}</div>}
    </div>
  );
}

// ── Org tab ─────────────────────────────────────────────────────────────────
export function OrgTab({ orgSlug }: { orgSlug: string }) {
  const gateway = useGateway();
  const orgQuery = useQuery({
    queryKey: ['org', orgSlug],
    queryFn: () => gateway.orgs.get(orgSlug),
  });

  if (orgQuery.isPending) return <LoadingSkeletonRow />;
  if (orgQuery.isError) return <ErrorCallout title="Couldn't load" message="Try again." />;
  const org = orgQuery.data;

  return (
    <div className="flex flex-col gap-6">
      <TabHeader
        icon={<IconSettings className="h-5 w-5" />}
        title="Organization"
        description="Your workspace identity, plan, and region settings."
      />
      <Card className="transition-all duration-normal hover:shadow-md">
        <CardHeader>
          <CardTitle>Details</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-4 sm:grid-cols-2">
          <Field label="Name" value={org.name} />
          <Field label="Slug" value={org.slug} mono />
          <Field
            label="Plan"
            value={<PlanBadge plan={org.plan} />}
          />
          <Field label="Region" value={org.region} mono />
          <Field
            label="Created"
            value={format(new Date(org.createdAt), 'MMM d, yyyy')}
          />
          <Field label="Status" value={<Badge variant="success">{org.status}</Badge>} />
        </CardContent>
      </Card>
    </div>
  );
}

// ── Team tab ────────────────────────────────────────────────────────────────
export function TeamTab({ orgSlug }: { orgSlug: string }) {
  const gateway = useGateway();
  const queryClient = useQueryClient();
  const toast = useToast();
  const [inviteOpen, setInviteOpen] = useState(false);

  const membersQuery = useQuery({
    queryKey: ['org', orgSlug, 'members'],
    queryFn: () => gateway.orgs.members(orgSlug),
  });

  const form = useForm<InviteRequest>({
    resolver: zodResolver(InviteRequestSchema),
    defaultValues: { email: '', role: 'editor' },
  });

  const invite = useMutation({
    mutationFn: (req: InviteRequest) => gateway.orgs.invite(orgSlug, req),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['org', orgSlug, 'members'] });
      setInviteOpen(false);
      form.reset();
      toast.push({ title: 'Invite created', variant: 'success' });
    },
  });

  return (
    <div className="flex flex-col gap-6">
      <TabHeader
        icon={<IconUsers className="h-5 w-5" />}
        title="Members"
        description="Roles control what each member can do. Audit log shows every action."
        action={<Button onClick={() => setInviteOpen(true)}>Invite member</Button>}
      />
      <Card className="overflow-hidden transition-all duration-normal hover:shadow-md">
        <CardContent className="p-0">
          {membersQuery.isPending ? (
            <LoadingSkeletonRow />
          ) : membersQuery.isError ? (
            <ErrorCallout title="Couldn't load members" />
          ) : (
            <ul className="divide-y divide-border">
              {membersQuery.data.map((m) => (
                <li
                  key={m.id}
                  className="group flex items-center justify-between gap-3 p-4 text-sm transition-colors hover:bg-surface-2"
                >
                  <div className="flex flex-col">
                    <span className="font-medium text-fg">
                      {m.displayName ?? m.email}
                    </span>
                    <span className="text-xs text-fg-muted">{m.email}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <RoleBadge role={m.role} />
                    {!m.acceptedAt && <Badge variant="warning">Pending</Badge>}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>

      {inviteOpen && (
        <Dialog open onOpenChange={(o) => !o && setInviteOpen(false)}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Invite a teammate</DialogTitle>
              <DialogDescription>
                Creates a pending membership for this organization.
              </DialogDescription>
            </DialogHeader>
            <form
              className="flex flex-col gap-4"
              onSubmit={form.handleSubmit((v) => invite.mutate(v))}
              noValidate
            >
              <div className="flex flex-col gap-1">
                <Label htmlFor="invite-email">Email</Label>
                <Input
                  id="invite-email"
                  type="email"
                  {...form.register('email')}
                  aria-invalid={form.formState.errors.email ? 'true' : 'false'}
                />
                {form.formState.errors.email && (
                  <p className="text-sm text-danger">{form.formState.errors.email.message}</p>
                )}
              </div>
              <div className="flex flex-col gap-1">
                <Label htmlFor="invite-role">Role</Label>
                <select
                  id="invite-role"
                  className="h-10 rounded-md border border-border bg-surface px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-border-focus"
                  {...form.register('role')}
                >
                  <option value="admin">Admin — connector mgmt, refinement, exports, team</option>
                  <option value="editor">Editor — read/write data, refinement, exports</option>
                  <option value="viewer">Viewer — read-only</option>
                </select>
              </div>
              {invite.isError && (
                <ErrorCallout title="Couldn't send invite" message="Try again." />
              )}
              <DialogFooter>
                <Button type="button" variant="ghost" onClick={() => setInviteOpen(false)}>
                  Cancel
                </Button>
                <Button type="submit" disabled={invite.isPending}>
                  {invite.isPending ? <Spinner className="mr-2" /> : null}Send invite
                </Button>
              </DialogFooter>
            </form>
          </DialogContent>
        </Dialog>
      )}
    </div>
  );
}

// ── Billing tab ─────────────────────────────────────────────────────────────
export function BillingTab({ orgSlug }: { orgSlug: string }) {
  const gateway = useGateway();
  const billingQuery = useQuery({
    queryKey: ['billing', orgSlug],
    queryFn: () => gateway.billing.subscription(orgSlug),
  });

  if (billingQuery.isPending) return <LoadingSkeletonRow />;
  if (billingQuery.isError) return <ErrorCallout title="Couldn't load billing" />;
  const b = billingQuery.data;

  return (
    <div className="flex flex-col gap-6">
      <TabHeader
        icon={<IconDatabase className="h-5 w-5" />}
        title="Billing"
        description="Plan details, payment method, and usage meters."
      />
      <Card className="transition-all duration-normal hover:shadow-md">
        <CardHeader className="flex-row items-center justify-between">
          <div>
            <CardTitle>Plan</CardTitle>
            <CardDescription>
              Current plan: <PlanBadge plan={b.plan} />
            </CardDescription>
          </div>
        </CardHeader>
        <CardContent className="grid gap-4 sm:grid-cols-2">
          <Field label="Status" value={<Badge variant="success">{b.status}</Badge>} />
          <Field
            label="Renews"
            value={
              b.currentPeriodEnd
                ? format(new Date(b.currentPeriodEnd), 'MMM d, yyyy')
                : '—'
            }
          />
          <Field
            label="Card on file"
            value={b.paymentMethodLast4 ? `•••• ${b.paymentMethodLast4}` : 'None'}
            mono
          />
        </CardContent>
      </Card>
      <Card className="transition-all duration-normal hover:shadow-md">
        <CardHeader>
          <CardTitle>Usage</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          {b.meters.map((m) => {
            const ratio = m.limit ? Math.min(100, (m.used / m.limit) * 100) : 0;
            return (
              <div key={m.metric} className="flex flex-col gap-1">
                <div className="flex items-center justify-between text-sm">
                  <span>{m.label}</span>
                  <span className="tabular-nums text-fg-muted">
                    {m.used.toLocaleString()} {m.limit ? `/ ${m.limit.toLocaleString()}` : ''}
                  </span>
                </div>
                {m.limit && <Progress value={ratio} />}
              </div>
            );
          })}
        </CardContent>
      </Card>
    </div>
  );
}

// ── API keys tab ────────────────────────────────────────────────────────────
const ALL_SCOPES: ApiKeyScope[] = ['read:all', 'write:all', 'events:write', 'refinements:propose'];

export function ApiKeysTab({ orgSlug }: { orgSlug: string }) {
  const gateway = useGateway();
  const queryClient = useQueryClient();
  const toast = useToast();
  const [createOpen, setCreateOpen] = useState(false);
  const [revealedSecret, setRevealedSecret] = useState<string | null>(null);

  const keysQuery = useQuery({
    queryKey: ['api-keys', orgSlug],
    queryFn: () => gateway.apiKeys.list(orgSlug),
  });

  const form = useForm<CreateApiKeyRequest>({
    resolver: zodResolver(CreateApiKeyRequestSchema),
    defaultValues: { name: '', scopes: ['read:all'] },
  });

  const create = useMutation({
    mutationFn: (req: CreateApiKeyRequest) => gateway.apiKeys.create(orgSlug, req),
    onSuccess: ({ secret }) => {
      setRevealedSecret(secret);
      queryClient.invalidateQueries({ queryKey: ['api-keys', orgSlug] });
      form.reset();
    },
  });

  const revoke = useMutation({
    mutationFn: (id: string) => gateway.apiKeys.revoke(orgSlug, id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['api-keys', orgSlug] });
      toast.push({ title: 'Key revoked', variant: 'info' });
    },
  });

  return (
    <div className="flex flex-col gap-6">
      <TabHeader
        icon={<IconLock className="h-5 w-5" />}
        title="API keys"
        description="Programmatic access. Secrets are shown once at creation; we don't store them in plaintext."
        action={<Button onClick={() => setCreateOpen(true)}>New API key</Button>}
      />
      <Card className="overflow-hidden transition-all duration-normal hover:shadow-md">
        <CardContent className="p-0">
          {keysQuery.isPending ? (
            <LoadingSkeletonRow />
          ) : keysQuery.isError ? (
            <ErrorCallout title="Couldn't load keys" />
          ) : keysQuery.data.length === 0 ? (
            <div className="p-6">
              <EmptyState
                icon={<IconShield className="h-8 w-8 text-fg-subtle" />}
                title="No API keys yet"
                description="Mint one for the SDK or the CLI."
                action={{ label: 'New API key', onClick: () => setCreateOpen(true) }}
              />
            </div>
          ) : (
            <ul className="divide-y divide-border">
              {keysQuery.data.map((k) => (
                <li
                  key={k.id}
                  className="group flex items-center justify-between gap-3 p-4 text-sm transition-colors hover:bg-surface-2"
                >
                  <div className="flex flex-col">
                    <span className="font-medium text-fg">{k.name}</span>
                    <span className="font-mono text-xs text-fg-muted">{k.prefix}…</span>
                  </div>
                  <div className="flex items-center gap-3">
                    <div className="flex flex-wrap gap-1">
                      {k.scopes.map((s) => (
                        <Badge key={s} variant="neutral">
                          {s}
                        </Badge>
                      ))}
                    </div>
                    <span className="text-xs text-fg-muted">
                      {k.lastUsedAt
                        ? `Last used ${format(new Date(k.lastUsedAt), 'MMM d')}`
                        : 'Never used'}
                    </span>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => revoke.mutate(k.id)}
                      disabled={revoke.isPending}
                    >
                      Revoke
                    </Button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>

      {createOpen && (
        <Dialog open onOpenChange={(o) => !o && (setCreateOpen(false), setRevealedSecret(null))}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Create API key</DialogTitle>
              <DialogDescription>
                Pick scopes you need. You can revoke at any time.
              </DialogDescription>
            </DialogHeader>
            {revealedSecret ? (
              <div className="flex flex-col gap-3">
                <p className="text-sm text-warning">
                  Copy this now. You won't see it again.
                </p>
                <div className="flex items-center gap-2 rounded-md border border-border bg-surface-2 p-3 font-mono text-xs">
                  <span className="flex-1 break-all">{revealedSecret}</span>
                  <Button
                    size="sm"
                    variant="secondary"
                    onClick={() => {
                      navigator.clipboard.writeText(revealedSecret);
                      toast.push({ title: 'Copied', variant: 'success' });
                    }}
                  >
                    <IconCopy className="mr-1 h-3.5 w-3.5" /> Copy
                  </Button>
                </div>
                <DialogFooter>
                  <Button
                    onClick={() => {
                      setCreateOpen(false);
                      setRevealedSecret(null);
                    }}
                  >
                    Done
                  </Button>
                </DialogFooter>
              </div>
            ) : (
              <form
                className="flex flex-col gap-4"
                onSubmit={form.handleSubmit((v) => create.mutate(v))}
                noValidate
              >
                <div className="flex flex-col gap-1">
                  <Label htmlFor="key-name">Name</Label>
                  <Input id="key-name" {...form.register('name')} placeholder="Production CI" />
                </div>
                <div className="flex flex-col gap-2">
                  <Label>Scopes</Label>
                  <div className="grid gap-2">
                    {ALL_SCOPES.map((scope) => {
                      const checked = form.watch('scopes').includes(scope);
                      return (
                        <label
                          key={scope}
                          className="flex items-center gap-2 rounded border border-border p-2 text-sm transition-colors hover:bg-surface-2"
                        >
                          <Checkbox
                            checked={checked}
                            onCheckedChange={(v) => {
                              const cur = form.getValues('scopes');
                              if (v) form.setValue('scopes', [...new Set([...cur, scope])]);
                              else
                                form.setValue(
                                  'scopes',
                                  cur.filter((s) => s !== scope),
                                );
                            }}
                          />
                          <span className="font-mono">{scope}</span>
                        </label>
                      );
                    })}
                  </div>
                </div>
                {create.isError && (
                  <ErrorCallout title="Couldn't create key" message="Try again." />
                )}
                <DialogFooter>
                  <Button type="button" variant="ghost" onClick={() => setCreateOpen(false)}>
                    Cancel
                  </Button>
                  <Button type="submit" disabled={create.isPending}>
                    {create.isPending ? <Spinner className="mr-2" /> : null}Create
                  </Button>
                </DialogFooter>
              </form>
            )}
          </DialogContent>
        </Dialog>
      )}
    </div>
  );
}

// ── Deployment mode tab ────────────────────────────────────────────────────
export function DeploymentModeTab() {
  return (
    <div className="flex flex-col gap-6">
      <TabHeader
        icon={<IconLayers className="h-5 w-5" />}
        title="Deployment modes"
        description="Each project can run on a different mode. Change a project's mode from its workspace settings."
      />
      <Card>
        <CardContent className="grid gap-3 sm:grid-cols-2">
          <ModeCard
            mode="hosted"
            title="Hosted Cloud"
            description="Encrypted in our managed Postgres with your own KMS key."
            icon={<IconSparkles className="h-4 w-4" />}
          />
          <ModeCard
            mode="byo_db"
            title="Bring your own DB"
            description="Connect a Postgres you control (Neon, Supabase, RDS, on-prem)."
            icon={<IconDatabase className="h-4 w-4" />}
          />
          <ModeCard
            mode="self_host"
            title="Self-host Docker"
            description="Run our image on your infrastructure. Engine + data on you."
            icon={<IconCommand className="h-4 w-4" />}
          />
          <ModeCard
            mode="local_dev"
            title="Local dev"
            description="`baseflo dev` spins up a local stack for development."
            icon={<IconZap className="h-4 w-4" />}
          />
        </CardContent>
      </Card>
    </div>
  );
}

function ModeCard({
  mode,
  title,
  description,
  icon,
}: {
  mode: 'hosted' | 'byo_db' | 'self_host' | 'local_dev';
  title: string;
  description: string;
  icon: ReactNode;
}) {
  return (
    <div className="group relative overflow-hidden rounded-lg border border-border bg-surface p-4 transition-all duration-normal hover:border-border-focus/30 hover:shadow-md">
      <div className="absolute inset-x-0 top-0 h-0.5 bg-gradient-to-r from-accent/40 via-accent/20 to-transparent opacity-0 transition-opacity duration-normal group-hover:opacity-100" />
      <div className="flex items-center gap-2">
        <DeploymentModeBadge mode={mode} />
        <span className="text-sm font-semibold text-fg">{title}</span>
        <span className="ml-auto text-fg-subtle opacity-0 transition-opacity duration-normal group-hover:opacity-100">
          {icon}
        </span>
      </div>
      <p className="mt-1 text-sm text-fg-muted">{description}</p>
    </div>
  );
}

// ── Audit tab (org-wide) ──────────────────────────────────────────────────
export function SettingsAuditTab({ orgSlug }: { orgSlug: string }) {
  return <AuditLogView orgSlug={orgSlug} />;
}

// ── shared bits ───────────────────────────────────────────────────────────
function Field({
  label,
  value,
  mono,
}: {
  label: string;
  value: ReactNode;
  mono?: boolean;
}) {
  return (
    <div className="flex flex-col gap-1">
      <Label className="text-xs uppercase tracking-wide text-fg-subtle">{label}</Label>
      <div className={mono ? 'font-mono text-sm text-fg' : 'text-sm text-fg'}>{value}</div>
    </div>
  );
}
