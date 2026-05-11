import { useEffect, useReducer, useState, useRef } from 'react';
import { useNavigate, useParams } from '@tanstack/react-router';
import {
  Badge,
  Button,
  Counter,
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  ErrorCallout,
  Label,
  PulseDot,
  Spinner,
  Textarea,
} from '@baseflo/ui';
import {
  IconArrowRight,
  IconCheck,
  IconWarning,
  IconWrench,
  IconX,
  IconSparkles,
  IconShieldCheck,
  IconZap,
  IconBolt,
} from '@baseflo/ui/icons';
import { cn } from '@baseflo/ui/lib/utils';
import type { SagaEvent } from '@baseflo/contracts';
import { useGateway } from '../../providers/GatewayProvider.js';
import {
  initialSagaState,
  reduceSaga,
  type ConnectionState,
  type SagaState,
  type StageState,
} from './sagaState.js';

/**
 * The headline agentic surface. Replaces the build-log feel with a vertical
 * engine canvas: one card per agent stage, the running stage surrounded by a
 * pulse ring, live token / latency tickers, and freshly-landed artifacts
 * sliding in. On `workspace.ready` we slot a full-bleed hero reveal with three
 * counters animating up.
 *
 * Design language: docs/06-design.md §4.8 (state-bearing motion, editorial
 * serif on reveal moments). Event handling: docs/04-database-schema.md §4.13.
 */
export function SagaViewerView() {
  const params = useParams({
    from: '/o/$orgSlug/p/$projectSlug/saga/$conversationId',
  });
  const gateway = useGateway();
  const navigate = useNavigate();
  const [state, dispatch] = useReducer(applyAction, initialSagaState);

  useEffect(() => {
    dispatch({ type: 'connection', state: 'connecting' });
    const subscription = gateway.sagas.subscribe(params.conversationId, {
      onEvent: (event) => dispatch({ type: 'event', event }),
      onOpen: () => dispatch({ type: 'connection', state: 'live' }),
      onClose: () => dispatch({ type: 'connection', state: 'closed' }),
      onError: () => dispatch({ type: 'connection', state: 'reconnecting' }),
    });
    return () => subscription.close();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params.conversationId]);

  const onCancel = async () => {
    try {
      await gateway.sagas.cancel(params.conversationId);
    } catch {
      // ignore
    }
  };

  const onAnswerClarification = async (questionId: string, answer: string) => {
    await gateway.sagas.answerClarification(params.conversationId, questionId, answer);
    dispatch({
      type: 'event',
      event: {
        conversationId: params.conversationId,
        sequence: state.lastSequence + 1,
        kind: 'clarification.answered',
        createdAt: new Date().toISOString(),
        payload: { questionId, answer },
      },
    });
  };

  const onWorkspaceReady = () => {
    if (!state.ready?.versionId) return;
    navigate({
      to: '/o/$orgSlug/p/$projectSlug/v/$versionId',
      params: {
        orgSlug: params.orgSlug,
        projectSlug: params.projectSlug,
        versionId: state.ready.versionId,
      },
    });
  };

  if (state.error) {
    const isCancelled = state.error.code === 'BF-JOB-003';
    return (
      <div className="mx-auto max-w-2xl py-16">
        <ErrorCallout
          title={isCancelled ? 'Build cancelled' : 'The build hit a hard error'}
          message={state.error.message}
          severity={isCancelled ? 'warning' : 'error'}
          action={{ label: 'Start over', onClick: () => window.history.back() }}
        />
      </div>
    );
  }

  if (state.ready) {
    return (
      <WorkspaceReadyHero
        stages={state.stages}
        artifacts={state.artifacts}
        onOpen={onWorkspaceReady}
      />
    );
  }

  return (
    <div className="rounded-xl bg-atmospheric bg-grid-dots p-6 lg:p-8">
      <div className="grid grid-cols-1 gap-8 lg:grid-cols-12">
        <EngineCanvas state={state} onCancel={onCancel} className="lg:col-span-8" />
        <ArtifactsRail state={state} className="lg:col-span-4" />

        {state.clarification && state.clarification.questions.length > 0 && (
          <ClarificationDialog
            questions={state.clarification.questions}
            onAnswer={onAnswerClarification}
          />
        )}
      </div>
    </div>
  );
}

// ── Reducer wrapper ─────────────────────────────────────────────────────────
function applyAction(
  state: SagaState,
  action:
    | { type: 'event'; event: SagaEvent }
    | { type: 'connection'; state: ConnectionState },
): SagaState {
  if (action.type === 'event') return reduceSaga(state, action.event);
  return { ...state, connection: action.state };
}

// ── Mission timer hook ──────────────────────────────────────────────────────
function useMissionTimer(stages: StageState[]) {
  const [elapsedMs, setElapsedMs] = useState(0);
  const startRef = useRef<number | null>(null);

  useEffect(() => {
    const running = stages.some((s) => s.status === 'running');
    if (running && startRef.current === null) {
      startRef.current = Date.now() - elapsedMs;
    }
    if (!running && stages.length > 0 && !startRef.current) {
      startRef.current = Date.now();
    }
  }, [elapsedMs, stages]);

  useEffect(() => {
    const id = window.setInterval(() => {
      if (startRef.current !== null) {
        setElapsedMs(Date.now() - startRef.current);
      }
    }, 100);
    return () => window.clearInterval(id);
  }, []);

  const secs = Math.floor(elapsedMs / 1000);
  const mins = Math.floor(secs / 60);
  const display = `${mins.toString().padStart(2, '0')}:${(secs % 60).toString().padStart(2, '0')}`;
  return display;
}

// ── Engine canvas (the vertical flow) ───────────────────────────────────────
function EngineCanvas({
  state,
  onCancel,
  className,
}: {
  state: SagaState;
  onCancel: () => void;
  className?: string;
}) {
  const timer = useMissionTimer(state.stages);
  return (
    <section className={className} aria-label="Engine progress">
      <header className="mb-6 flex items-end justify-between">
        <div>
          <div className="mb-1 flex items-center gap-2">
            <IconZap className="h-3.5 w-3.5 text-accent" />
            <p className="text-xs font-bold uppercase tracking-widest text-accent">
              Launch Control
            </p>
          </div>
          <h1 className="font-serif text-3xl font-semibold leading-tight text-fg">
            {currentLabel(state)}
          </h1>
        </div>
        <div className="flex items-center gap-3">
          <span className="hidden rounded-lg border border-border bg-surface px-3 py-1.5 font-mono text-xs text-fg-subtle sm:inline-block">
            T+ {timer}
          </span>
          <ConnectionPill state={state.connection} />
        </div>
      </header>

      <ol className="relative flex flex-col gap-3" role="list">
        {state.stages.length === 0 && (
          <li className="rounded-lg border border-dashed border-border bg-surface px-4 py-10 text-center text-sm text-fg-muted">
            Waiting for the engine to dispatch the first agent…
          </li>
        )}
        {state.stages.map((stage, i) => (
          <StageCard
            key={stage.id}
            stage={stage}
            isLast={i === state.stages.length - 1}
            index={i}
          />
        ))}
      </ol>

      {state.connection !== 'closed' && state.connection !== 'terminal' && (
        <div className="mt-6 flex justify-end">
          <Button variant="ghost" size="sm" onClick={onCancel}>
            Abort mission
          </Button>
        </div>
      )}
    </section>
  );
}

function currentLabel(state: SagaState): string {
  for (let i = state.stages.length - 1; i >= 0; i -= 1) {
    const stage = state.stages[i];
    if (stage?.status === 'running') return stage.label;
  }
  if (state.stages.length === 0) return 'Starting up';
  return 'Working…';
}

// ── Single stage card ───────────────────────────────────────────────────────
function StageCard({
  stage,
  isLast,
  index,
}: {
  stage: StageState;
  isLast: boolean;
  index: number;
}) {
  const isActive = stage.status === 'running' || stage.status === 'repairing';
  const isComplete = stage.status === 'passed' || stage.status === 'warning';
  return (
    <li
      className={cn(
        'relative rounded-lg border bg-surface p-4 transition-all duration-normal',
        'animate-[slide-in-top_var(--duration-slow)_var(--ease-baseflo)]',
        isActive
          ? 'border-accent shadow-[0_0_24px_-4px_hsl(var(--color-accent)/0.25)]'
          : 'border-border',
        isComplete && !isActive && 'border-l-4 border-l-success',
        isActive && 'border-l-4 border-l-accent',
      )}
      style={{ animationDelay: `${index * 40}ms` }}
    >
      <div className="flex items-start gap-3">
        <StageIcon stage={stage} />
        <div className="flex-1">
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <span className="text-sm font-semibold text-fg">{stage.label}</span>
              <span className="font-mono text-xs text-fg-subtle">{stage.agentName}</span>
            </div>
            <StageStatusText stage={stage} />
          </div>

          {(stage.status === 'running' || stage.status === 'passed') && (
            <TokenLine stage={stage} />
          )}

          {stage.warnings.length > 0 && (
            <ul className="mt-2 flex flex-col gap-1">
              {stage.warnings.map((w, i) => (
                <li key={i} className="flex items-start gap-1 text-xs text-warning">
                  <IconWarning className="mt-0.5 h-3 w-3 shrink-0" />
                  <span>{w}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
      {!isLast && (
        <span
          aria-hidden="true"
          className={cn(
            'absolute left-[26px] top-full h-3 w-px',
            isComplete ? 'bg-success/50' : 'bg-border',
          )}
        />
      )}
    </li>
  );
}

function StageIcon({ stage }: { stage: StageState }) {
  if (stage.status === 'running') {
    return (
      <span
        aria-label="Running"
        className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-accent-soft shadow-[0_0_12px_hsl(var(--color-accent)/0.35)]"
      >
        <PulseDot tone="accent" size={8} />
      </span>
    );
  }
  if (stage.status === 'passed') {
    return (
      <span
        aria-label="Done"
        className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-success/10 text-success"
      >
        <IconCheck className="h-3.5 w-3.5" strokeWidth={3} />
      </span>
    );
  }
  if (stage.status === 'warning') {
    return (
      <span
        aria-label="With warnings"
        className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-warning/10 text-warning"
      >
        <IconWarning className="h-3.5 w-3.5" strokeWidth={2.5} />
      </span>
    );
  }
  if (stage.status === 'failed') {
    return (
      <span
        aria-label="Failed"
        className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-danger/10 text-danger"
      >
        <IconX className="h-3.5 w-3.5" strokeWidth={3} />
      </span>
    );
  }
  if (stage.status === 'repairing') {
    return (
      <span
        aria-label="Repairing"
        className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-warning/10 text-warning"
      >
        <IconWrench className="h-3.5 w-3.5" />
      </span>
    );
  }
  return (
    <span
      aria-label="Pending"
      className="mt-1.5 ml-2.5 h-1.5 w-1.5 shrink-0 rounded-full bg-fg-subtle"
    />
  );
}

function StageStatusText({ stage }: { stage: StageState }) {
  if (stage.status === 'running') {
    return (
      <span className="inline-flex items-center gap-1 text-xs text-accent">
        <IconBolt className="h-3 w-3" />
        Working…
      </span>
    );
  }
  if (stage.status === 'passed') {
    return (
      <span className="font-mono text-xs text-fg-muted">
        {stage.durationMs ? `${(stage.durationMs / 1000).toFixed(1)}s` : '—'}
      </span>
    );
  }
  if (stage.status === 'warning') {
    return <span className="text-xs text-warning">With warnings</span>;
  }
  if (stage.status === 'failed') {
    return <span className="text-xs text-danger">Failed</span>;
  }
  if (stage.status === 'repairing') {
    return <span className="text-xs text-warning">Repair attempt</span>;
  }
  return <span className="text-xs text-fg-subtle">Queued</span>;
}

function TokenLine({ stage }: { stage: StageState }) {
  const tokensIn = stage.inputTokens ?? null;
  const tokensOut = stage.outputTokens ?? null;
  if (tokensIn === null && tokensOut === null) return null;
  return (
    <div className="mt-1.5 flex items-center gap-3 font-mono text-[11px] text-fg-subtle">
      {tokensIn !== null && (
        <span>
          <Counter
            value={tokensIn}
            durationMs={stage.status === 'running' ? 600 : 800}
            animate
          />{' '}
          in
        </span>
      )}
      {tokensOut !== null && (
        <span>
          <Counter
            value={tokensOut}
            durationMs={stage.status === 'running' ? 600 : 800}
            animate
          />{' '}
          out
        </span>
      )}
    </div>
  );
}

// ── Connection pill (top-right) ─────────────────────────────────────────────
function ConnectionPill({ state }: { state: ConnectionState }) {
  const config: Record<
    ConnectionState,
    { label: string; tone: 'accent' | 'success' | 'warning' | 'info'; active: boolean }
  > = {
    connecting: { label: 'Connecting', tone: 'info', active: true },
    live: { label: 'Live', tone: 'success', active: true },
    reconnecting: { label: 'Reconnecting', tone: 'warning', active: true },
    closed: { label: 'Stream closed', tone: 'info', active: false },
    terminal: { label: 'Stream ended', tone: 'warning', active: false },
  };
  const c = config[state];
  return (
    <span
      className={cn(
        'inline-flex items-center gap-2 rounded-full border bg-surface px-3 py-1.5 text-xs font-semibold shadow-sm',
        c.active
          ? 'border-accent/40 shadow-[0_0_12px_-2px_hsl(var(--color-accent)/0.2)]'
          : 'border-border',
      )}
    >
      <PulseDot tone={c.tone} size={7} active={c.active} />
      <span className="text-fg">{c.label}</span>
    </span>
  );
}

// ── Artifacts rail ──────────────────────────────────────────────────────────
function ArtifactsRail({
  state,
  className,
}: {
  state: SagaState;
  className?: string;
}) {
  return (
    <aside
      className={cn('flex flex-col gap-3', className)}
      aria-label="Emerging artifacts"
    >
      <header className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <IconSparkles className="h-3.5 w-3.5 text-accent" />
          <p className="text-xs font-bold uppercase tracking-widest text-fg-subtle">
            Discoveries
          </p>
        </div>
        <Badge variant="accent">
          <Counter value={state.artifacts.length} animate={false} /> found
        </Badge>
      </header>
      {state.artifacts.length === 0 ? (
        <div className="rounded-lg border border-dashed border-border bg-surface/80 px-4 py-10 text-center text-sm text-fg-muted">
          <IconSparkles className="mx-auto mb-2 h-5 w-5 text-fg-subtle/50" />
          Schema, KPIs, and dashboards land here as agents finish their missions.
        </div>
      ) : (
        <ul className="flex flex-col gap-2" role="list">
          {state.artifacts.map((a) => (
            <li
              key={a.id}
              className={cn(
                'rounded-md border border-border bg-surface p-3',
                'animate-[slide-in-right_var(--duration-slow)_var(--ease-baseflo)]',
                'shadow-sm transition-shadow hover:shadow-md',
              )}
            >
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium text-fg">{a.label}</span>
                <Badge variant="info" className="text-[10px]">
                  {a.kind}
                </Badge>
              </div>
              {a.preview && <p className="mt-1 text-xs text-fg-muted">{a.preview}</p>}
            </li>
          ))}
        </ul>
      )}
    </aside>
  );
}

// ── Workspace.ready hero reveal ─────────────────────────────────────────────
function WorkspaceReadyHero({
  stages,
  artifacts,
  onOpen,
}: {
  stages: StageState[];
  artifacts: SagaState['artifacts'];
  onOpen: () => void;
}) {
  const stageCount = stages.filter((stage) =>
    stage.status === 'passed' || stage.status === 'warning',
  ).length;
  const warningCount = stages.reduce((total, stage) => total + stage.warnings.length, 0);
  const artifactCount = artifacts.length;

  return (
    <div
      className="mx-auto flex max-w-3xl flex-col items-center gap-10 rounded-xl bg-atmospheric bg-grid-dots py-16 text-center animate-[fade-in_var(--duration-slow)_var(--ease-baseflo)]"
      role="status"
      aria-live="polite"
    >
      <Badge variant="success" className="px-3 py-1 text-sm">
        <IconShieldCheck className="h-3.5 w-3.5" strokeWidth={2.5} />
        Mission accomplished — Workspace ready
      </Badge>

      <div className="flex flex-col gap-4">
        <h1 className="font-serif text-5xl font-semibold leading-[1.05] tracking-tight text-fg">
          Your workspace is ready.
        </h1>
        <p className="mx-auto max-w-xl text-base text-fg-muted">
          Generated from the live build pipeline. Open it to inspect the schema,
          connector state, and workspace data.
        </p>
      </div>

      <div className="grid w-full max-w-2xl grid-cols-1 gap-4 px-6 sm:grid-cols-3">
        <HeroStat value={stageCount} label="agents completed" tone="accent" delayMs={0} />
        <HeroStat
          value={artifactCount}
          label="discoveries made"
          tone="success"
          delayMs={150}
        />
        <HeroStat
          value={warningCount}
          label="validation warnings"
          tone="info"
          delayMs={300}
        />
      </div>

      <Button onClick={onOpen} size="lg" className="shadow-lg shadow-accent/20">
        Open workspace
        <IconArrowRight className="ml-1 h-4 w-4" />
      </Button>
    </div>
  );
}

function HeroStat({
  value,
  label,
  tone,
  delayMs = 0,
  sub,
}: {
  value: number;
  label: string;
  tone: 'accent' | 'success' | 'info';
  delayMs?: number;
  sub?: string;
}) {
  const [armed, setArmed] = useState(false);
  useEffect(() => {
    const t = window.setTimeout(() => setArmed(true), delayMs);
    return () => window.clearTimeout(t);
  }, [delayMs]);

  const toneClass = {
    accent: 'text-accent',
    success: 'text-success',
    info: 'text-info',
  }[tone];

  return (
    <div className="flex flex-col items-center gap-1 rounded-lg border border-border bg-surface p-6 shadow-sm">
      <span className={cn('font-serif text-5xl font-semibold tabular-nums', toneClass)}>
        <Counter value={armed ? value : 0} durationMs={1000} />
      </span>
      <span className="text-sm text-fg-muted">{label}</span>
      {sub && <span className="text-xs text-fg-subtle">{sub}</span>}
    </div>
  );
}

// ── Clarification dialog ────────────────────────────────────────────────────
function ClarificationDialog({
  questions,
  onAnswer,
}: {
  questions: Array<{
    id: string;
    prompt: string;
    choices?: string[];
    allowFreeText?: boolean;
  }>;
  onAnswer: (questionId: string, answer: string) => Promise<void>;
}) {
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState(false);

  const submit = async () => {
    setSubmitting(true);
    try {
      for (const q of questions) {
        const value = answers[q.id];
        if (value) await onAnswer(q.id, value);
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open={true}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle className="font-serif text-2xl">A few quick questions</DialogTitle>
          <DialogDescription>
            The architects need a little more context. This isn't an error.
          </DialogDescription>
        </DialogHeader>
        <div className="flex flex-col gap-4">
          {questions.slice(0, 3).map((q) => (
            <div key={q.id} className="flex flex-col gap-2">
              <Label className="text-fg">{q.prompt}</Label>
              {q.choices && (
                <div className="flex flex-wrap gap-2">
                  {q.choices.map((choice) => (
                    <button
                      key={choice}
                      type="button"
                      onClick={() => setAnswers((p) => ({ ...p, [q.id]: choice }))}
                      className={cn(
                        'rounded-full border px-3 py-1 text-xs transition-colors',
                        answers[q.id] === choice
                          ? 'border-accent bg-accent-soft'
                          : 'border-border hover:bg-surface-2',
                      )}
                    >
                      {choice}
                    </button>
                  ))}
                </div>
              )}
              {q.allowFreeText !== false && (
                <Textarea
                  rows={2}
                  value={answers[q.id] ?? ''}
                  onChange={(e) => setAnswers((p) => ({ ...p, [q.id]: e.target.value }))}
                  placeholder="Or write your own…"
                />
              )}
            </div>
          ))}
        </div>
        <DialogFooter>
          <Button onClick={submit} disabled={submitting}>
            {submitting ? <Spinner className="mr-2" /> : null}Continue
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
