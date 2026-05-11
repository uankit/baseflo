import { useNavigate, useParams } from '@tanstack/react-router';
import { useMutation } from '@tanstack/react-query';
import { useForm } from 'react-hook-form';
import { motion } from 'framer-motion';
import {
  Button,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  Input,
  Label,
  Textarea,
  Badge,
  PulseDot,
} from '@baseflo/ui';
import {
  CreateProjectRequestSchema,
  type CreateProjectRequest,
} from '@baseflo/contracts';
import {
  IconBolt,
  IconUsers,
  IconShield,
  IconTrendingUp,
  IconCommand,
  IconDatabase,
  IconLayers,
  IconSparkles,
  IconZap,
  IconCheck,
} from '@baseflo/ui/icons';
import { zodResolver } from '../../lib/forms/zodResolver.js';
import { useGateway } from '../../providers/GatewayProvider.js';

const EXAMPLES = [
  { text: 'Customer 360 with churn risk and lifetime value.', icon: IconUsers },
  { text: 'Subscription billing dashboard with MRR and trial conversion.', icon: IconTrendingUp },
  { text: 'Bookings + payments for a yoga studio.', icon: IconDatabase },
  { text: 'Order fulfillment tracker with refunds and disputes.', icon: IconLayers },
];

const AGENTS = [
  { id: 'source', name: 'Source', icon: IconBolt, border: 'border-accent/30', bg: 'bg-accent-soft', text: 'text-accent' },
  { id: 'recon', name: 'Recon', icon: IconUsers, border: 'border-purple-300', bg: 'bg-purple-50', text: 'text-purple-600' },
  { id: 'schema', name: 'Schema', icon: IconShield, border: 'border-emerald-300', bg: 'bg-emerald-50', text: 'text-emerald-600' },
  { id: 'insight', name: 'Insight', icon: IconTrendingUp, border: 'border-amber-300', bg: 'bg-amber-50', text: 'text-amber-600' },
];

export function ProjectCreateView() {
  const { orgSlug } = useParams({ from: '/o/$orgSlug/projects/new' });
  const navigate = useNavigate();
  const gateway = useGateway();

  const form = useForm<CreateProjectRequest>({
    resolver: zodResolver(CreateProjectRequestSchema),
    defaultValues: { name: '', description: '', deploymentMode: 'hosted' },
  });

  const nameValue = form.watch('name');
  const descValue = form.watch('description');

  const createProject = useMutation({
    mutationFn: (req: CreateProjectRequest) => gateway.projects.create(orgSlug, req),
    onSuccess: (project) => {
      navigate({
        to: '/o/$orgSlug/p/$projectSlug/v/$versionId',
        params: { orgSlug, projectSlug: project.slug, versionId: 'pending' },
      });
    },
  });

  return (
    <div className="relative min-h-full bg-atmospheric bg-grid-dots py-12">
      <div className="mx-auto w-full max-w-2xl px-4">
        {/* Agent status strip */}
        <motion.div
          initial={{ opacity: 0, y: -8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="mb-6 flex items-center justify-center gap-3"
        >
          <div className="flex items-center gap-2 rounded-full border border-border/80 bg-surface/80 px-4 py-2 shadow-sm backdrop-blur-sm">
            <PulseDot tone="accent" size={6} active />
            <span className="text-xs font-medium uppercase tracking-wider text-fg-muted">
              Agents standing by
            </span>
            <div className="ml-1 flex items-center gap-1.5">
              {AGENTS.map((a) => (
                <div
                  key={a.id}
                  className={`flex h-6 w-6 items-center justify-center rounded-full border ${a.border} ${a.bg} ${a.text}`}
                  title={`${a.name} Agent`}
                >
                  <a.icon size={12} />
                </div>
              ))}
            </div>
          </div>
        </motion.div>

        {/* Hero header */}
        <motion.header
          initial={{ opacity: 0, y: -6 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.1 }}
          className="mb-8 flex flex-col items-center gap-2 text-center"
        >
          <div className="flex items-center gap-2">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg border border-accent/20 bg-accent-soft text-accent">
              <IconCommand size={16} />
            </span>
            <h1 className="font-serif text-3xl font-semibold leading-tight tracking-tight text-fg">
              Initialize a new system
            </h1>
          </div>
          <p className="max-w-md text-sm text-fg-muted">
            The architect agents are ready. A clear description is the blueprint they use to
            understand your business.
          </p>
        </motion.header>

        {/* System config card */}
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.2 }}
        >
          <Card className="overflow-hidden border-border/80 shadow-lg">
            <CardHeader className="bg-surface-2/50">
              <div className="mb-1 flex items-center gap-2">
                <span className="flex h-7 w-7 items-center justify-center rounded-full border border-accent/20 bg-accent-soft text-accent">
                  <IconSparkles size={14} />
                </span>
                <CardTitle>System configuration</CardTitle>
              </div>
              <CardDescription>
                Plain language is fine — the schema agent will infer structure from your words.
              </CardDescription>
            </CardHeader>
            <CardContent className="pt-6">
              <form
                className="flex flex-col gap-5"
                onSubmit={form.handleSubmit((values) => createProject.mutate(values))}
                noValidate
              >
                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="project-name" className="flex items-center gap-2">
                    System name
                    {nameValue && (
                      <IconCheck size={12} className="text-success" />
                    )}
                  </Label>
                  <Input
                    id="project-name"
                    placeholder="Growth dashboard"
                    aria-invalid={form.formState.errors.name ? 'true' : 'false'}
                    className={nameValue ? 'border-accent/40 bg-accent-soft/30' : ''}
                    {...form.register('name')}
                  />
                  {form.formState.errors.name && (
                    <p className="text-sm text-danger">{form.formState.errors.name.message}</p>
                  )}
                </div>

                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="project-description" className="flex items-center gap-2">
                    Mission brief
                    <Badge variant="accent">Required</Badge>
                    {descValue && (
                      <IconCheck size={12} className="text-success" />
                    )}
                  </Label>
                  <Textarea
                    id="project-description"
                    rows={4}
                    placeholder="A boutique yoga studio with bookings, packages, payments, and email."
                    className={descValue ? 'border-accent/40 bg-accent-soft/30' : ''}
                    {...form.register('description')}
                  />
                  <p className="text-xs text-fg-subtle">
                    This is what the agents read to understand your domain. Be specific.
                  </p>

                  <div className="mt-2 flex flex-wrap gap-2">
                    {EXAMPLES.map((ex) => {
                      const isActive = descValue === ex.text;
                      return (
                        <button
                          key={ex.text}
                          type="button"
                          className={`flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-border-focus ${
                            isActive
                              ? 'border-accent bg-accent-soft text-accent shadow-sm'
                              : 'border-border bg-surface text-fg-muted hover:bg-surface-2 hover:border-accent/30'
                          }`}
                          onClick={() => form.setValue('description', ex.text)}
                        >
                          <ex.icon size={12} />
                          {ex.text}
                        </button>
                      );
                    })}
                  </div>
                </div>

                <Button
                  type="submit"
                  disabled={createProject.isPending}
                  className="gap-2 shadow-md shadow-accent/20 transition-shadow hover:shadow-lg hover:shadow-accent/30"
                >
                  <IconZap size={14} />
                  {createProject.isPending ? 'Initializing…' : 'Initialize'}
                </Button>
              </form>
            </CardContent>
          </Card>
        </motion.div>

        {/* Post-card note */}
        <motion.p
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.5 }}
          className="mt-6 text-center text-sm text-fg-muted"
        >
          Already have a frontend? Once your workspace is ready, paste two lines into Cursor —
          see <code className="font-mono">Help → CLI quickstart</code>.
        </motion.p>
      </div>
    </div>
  );
}
