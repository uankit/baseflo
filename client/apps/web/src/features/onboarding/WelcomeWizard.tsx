import { useState, type ReactNode } from 'react';
import { useNavigate } from '@tanstack/react-router';
import { useMutation } from '@tanstack/react-query';
import { useForm } from 'react-hook-form';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Button,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  Input,
  Label,
  OnboardingStep,
  Badge,
  PulseDot,
} from '@baseflo/ui';
import {
  IconBolt,
  IconUsers,
  IconShield,
  IconTrendingUp,
  IconShieldCheck,
  IconDatabase,
  IconLayers,
  IconCommand,
  IconAnalytics,
  IconSparkles,
} from '@baseflo/ui/icons';
import { CreateOrgRequestSchema, type CreateOrgRequest } from '@baseflo/contracts';
import { zodResolver } from '../../lib/forms/zodResolver.js';
import { useGateway } from '../../providers/GatewayProvider.js';

const STEPS = ['Organization', 'Deployment', 'Path'] as const;

export function WelcomeWizard() {
  const [stepIndex, setStepIndex] = useState(0);
  const [orgSlug, setOrgSlug] = useState<string | null>(null);
  const [deploymentMode, setDeploymentMode] = useState<'hosted' | 'byo_db' | 'self_host'>(
    'hosted',
  );
  const navigate = useNavigate();
  const gateway = useGateway();

  const form = useForm<CreateOrgRequest>({
    resolver: zodResolver(CreateOrgRequestSchema),
    defaultValues: { name: '', region: 'us-east-1' },
  });

  const createOrg = useMutation({
    mutationFn: (req: CreateOrgRequest) => gateway.orgs.create(req),
    onSuccess: (org) => {
      setOrgSlug(org.slug);
      setStepIndex(1);
    },
  });

  const goPath = (path: 'icp_a' | 'icp_b') => {
    if (!orgSlug) return;
    navigate({
      to: path === 'icp_a' ? '/o/$orgSlug/projects/new' : '/o/$orgSlug/start',
      params: { orgSlug },
    });
  };

  return (
    <div className="relative min-h-full bg-atmospheric bg-grid-dots py-12">
      <div className="mx-auto w-full max-w-2xl px-4">
        <motion.header
          initial={{ opacity: 0, y: -8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="mb-8 flex flex-col items-center gap-3 text-center"
        >
          <div className="flex items-center gap-2">
            <PulseDot tone="accent" size={6} active />
            <span className="text-xs font-medium uppercase tracking-wider text-accent">
              Setup in progress
            </span>
          </div>
          <h1 className="font-serif text-3xl font-semibold leading-tight tracking-tight text-fg">
            Welcome to Baseflo.
          </h1>
          <p className="max-w-sm text-sm text-fg-muted">
            Your agents are standing by. A few quick choices and we&apos;ll have your unified workspace ready.
          </p>

          {/* Agent trust strip */}
          <div className="mt-1 flex items-center gap-2">
            {[
              { icon: IconBolt, color: 'text-accent', bg: 'bg-accent-soft', border: 'border-accent/20' },
              { icon: IconUsers, color: 'text-purple-600', bg: 'bg-purple-50', border: 'border-purple-200' },
              { icon: IconShield, color: 'text-emerald-600', bg: 'bg-emerald-50', border: 'border-emerald-200' },
              { icon: IconTrendingUp, color: 'text-amber-600', bg: 'bg-amber-50', border: 'border-amber-200' },
            ].map((a, i) => (
              <motion.div
                key={i}
                initial={{ opacity: 0, scale: 0.8 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ delay: 0.2 + i * 0.08 }}
                className={`flex h-7 w-7 items-center justify-center rounded-full border ${a.border} ${a.bg} ${a.color}`}
              >
                <a.icon size={14} />
              </motion.div>
            ))}
            <span className="ml-1 text-[10px] text-fg-subtle">4 agents ready</span>
          </div>
        </motion.header>

        <motion.div
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.15 }}
          className="mb-8 flex items-center justify-center gap-6"
          role="navigation"
          aria-label="Onboarding steps"
        >
          {STEPS.map((label, i) => (
            <OnboardingStep
              key={label}
              index={i + 1}
              total={STEPS.length}
              label={label}
              status={i < stepIndex ? 'done' : i === stepIndex ? 'active' : 'pending'}
            />
          ))}
        </motion.div>

        <AnimatePresence mode="wait">
          {stepIndex === 0 && (
            <motion.div
              key="step-0"
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              transition={{ duration: 0.35, ease: [0.2, 0, 0, 1] }}
            >
              <Card className="overflow-hidden border-border/80 shadow-lg">
                <CardHeader className="bg-surface-2/50">
                  <div className="mb-2 flex items-center gap-2">
                    <span className="flex h-7 w-7 items-center justify-center rounded-full border border-purple-200 bg-purple-50 text-purple-600">
                      <IconUsers size={14} />
                    </span>
                    <CardTitle>Create your organization</CardTitle>
                  </div>
                  <CardDescription>
                    Your billing entity. You can add teammates after.
                  </CardDescription>
                </CardHeader>
                <CardContent className="pt-6">
                  <form
                    className="flex flex-col gap-4"
                    onSubmit={form.handleSubmit((values) => createOrg.mutate(values))}
                    noValidate
                  >
                    <div className="flex flex-col gap-1.5">
                      <Label htmlFor="org-name">Organization name</Label>
                      <Input
                        id="org-name"
                        placeholder="Acme Crochet"
                        aria-invalid={form.formState.errors.name ? 'true' : 'false'}
                        {...form.register('name')}
                      />
                      {form.formState.errors.name && (
                        <p className="text-sm text-danger">{form.formState.errors.name.message}</p>
                      )}
                    </div>
                    <div className="flex flex-col gap-1.5">
                      <Label htmlFor="org-region">Region</Label>
                      <select
                        id="org-region"
                        className="h-10 rounded-md border border-border bg-surface px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-border-focus"
                        {...form.register('region')}
                      >
                        <option value="us-east-1">US East (Virginia)</option>
                        <option value="eu-west-1">EU West (Ireland)</option>
                      </select>
                    </div>
                    <Button type="submit" disabled={createOrg.isPending} className="mt-1">
                      {createOrg.isPending ? 'Creating…' : 'Continue'}
                    </Button>
                  </form>
                </CardContent>
              </Card>
            </motion.div>
          )}

          {stepIndex === 1 && (
            <motion.div
              key="step-1"
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              transition={{ duration: 0.35, ease: [0.2, 0, 0, 1] }}
            >
              <Card className="overflow-hidden border-border/80 shadow-lg">
                <CardHeader className="bg-surface-2/50">
                  <div className="mb-2 flex items-center gap-2">
                    <span className="flex h-7 w-7 items-center justify-center rounded-full border border-emerald-200 bg-emerald-50 text-emerald-600">
                      <IconShield size={14} />
                    </span>
                    <CardTitle>Choose your deployment mode</CardTitle>
                  </div>
                  <CardDescription>
                    Where your data lives. You can change this per project later.
                  </CardDescription>
                </CardHeader>
                <CardContent className="flex flex-col gap-3 pt-6">
                  <ModeOption
                    title="Hosted Cloud"
                    description="Encrypted in our managed Postgres with your own KMS key. Default."
                    selected={deploymentMode === 'hosted'}
                    onSelect={() => setDeploymentMode('hosted')}
                    badge="Standard"
                    badgeTone="neutral"
                    icon={<IconShieldCheck size={18} className="text-accent" />}
                    power={1}
                  />
                  <ModeOption
                    title="Bring your own database"
                    description="Connect your own Postgres (Neon, Supabase, RDS). Engine on us; data on you."
                    selected={deploymentMode === 'byo_db'}
                    onSelect={() => setDeploymentMode('byo_db')}
                    badge="Pro"
                    badgeTone="accent"
                    icon={<IconDatabase size={18} className="text-accent" />}
                    power={2}
                  />
                  <ModeOption
                    title="Self-host Docker"
                    description="Run our image on your infrastructure. Engine + data on you."
                    selected={deploymentMode === 'self_host'}
                    onSelect={() => setDeploymentMode('self_host')}
                    badge="Business"
                    badgeTone="accent"
                    icon={<IconLayers size={18} className="text-accent" />}
                    power={3}
                  />
                  <div className="flex items-center justify-between pt-2">
                    <Button variant="ghost" onClick={() => setStepIndex(0)}>
                      Back
                    </Button>
                    <Button onClick={() => setStepIndex(2)}>Continue</Button>
                  </div>
                </CardContent>
              </Card>
            </motion.div>
          )}

          {stepIndex === 2 && (
            <motion.div
              key="step-2"
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              transition={{ duration: 0.35, ease: [0.2, 0, 0, 1] }}
            >
              <Card className="overflow-hidden border-border/80 shadow-lg">
                <CardHeader className="bg-surface-2/50">
                  <div className="mb-2 flex items-center gap-2">
                    <span className="flex h-7 w-7 items-center justify-center rounded-full border border-amber-200 bg-amber-50 text-amber-600">
                      <IconTrendingUp size={14} />
                    </span>
                    <CardTitle>Pick your path</CardTitle>
                  </div>
                  <CardDescription>How do you want to start?</CardDescription>
                </CardHeader>
                <CardContent className="grid gap-3 pt-6 sm:grid-cols-2">
                  <PathOption
                    title="I'm building an app"
                    description="Backend, APIs, SDKs, CLI for your indie/team build."
                    cta="Start as developer"
                    icon={<IconCommand size={20} className="text-accent" />}
                    onSelect={() => goPath('icp_a')}
                  />
                  <PathOption
                    title="I run a business"
                    description="Connect Stripe, Sheets, Excel and see your business in one view."
                    cta="Connect my tools"
                    icon={<IconAnalytics size={20} className="text-accent" />}
                    onSelect={() => goPath('icp_b')}
                  />
                </CardContent>
              </Card>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}

function ModeOption({
  title,
  description,
  selected,
  onSelect,
  badge,
  badgeTone,
  icon,
  power,
}: {
  title: string;
  description: string;
  selected: boolean;
  onSelect: () => void;
  badge?: string;
  badgeTone?: 'neutral' | 'accent';
  icon: ReactNode;
  power: number;
}) {
  return (
    <button
      type="button"
      onClick={onSelect}
      aria-pressed={selected}
      className={`group relative flex flex-col gap-2 rounded-xl border p-4 text-left transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-border-focus ${
        selected
          ? 'border-accent bg-accent-soft shadow-md shadow-accent/10'
          : 'border-border bg-surface hover:border-accent/40 hover:bg-surface-2 hover:shadow-sm'
      }`}
    >
      {/* Power indicator */}
      <div className="absolute right-4 top-4 flex gap-0.5">
        {Array.from({ length: 3 }).map((_, i) => (
          <span
            key={i}
            className={`h-1 w-3 rounded-full transition-colors ${
              i < power ? 'bg-accent' : 'bg-border'
            }`}
          />
        ))}
      </div>

      <div className="flex items-center gap-3">
        <span
          className={`flex h-9 w-9 items-center justify-center rounded-lg border transition-colors ${
            selected ? 'border-accent/30 bg-accent-soft' : 'border-border bg-surface-2 group-hover:border-accent/20'
          }`}
        >
          {icon}
        </span>
        <div className="flex flex-col gap-0.5">
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium text-fg">{title}</span>
            {badge && (
              <Badge variant={badgeTone === 'accent' && selected ? 'accent' : 'neutral'}>
                {badge}
              </Badge>
            )}
          </div>
        </div>
      </div>
      <span className="text-sm text-fg-muted">{description}</span>
    </button>
  );
}

function PathOption({
  title,
  description,
  cta,
  icon,
  onSelect,
}: {
  title: string;
  description: string;
  cta: string;
  icon: ReactNode;
  onSelect: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onSelect}
      className="group flex flex-col gap-4 rounded-xl border border-border bg-surface p-5 text-left transition-all hover:border-accent hover:bg-accent-soft hover:shadow-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-border-focus"
    >
      <span className="flex h-10 w-10 items-center justify-center rounded-lg border border-border bg-surface-2 text-accent transition-colors group-hover:border-accent/30 group-hover:bg-accent-soft">
        {icon}
      </span>
      <div className="flex flex-col gap-1">
        <span className="text-sm font-semibold text-fg">{title}</span>
        <span className="text-sm text-fg-muted">{description}</span>
      </div>
      <span className="mt-auto flex items-center gap-1 text-sm font-medium text-accent">
        {cta}
        <IconSparkles size={14} className="transition-transform group-hover:scale-110" />
      </span>
    </button>
  );
}
