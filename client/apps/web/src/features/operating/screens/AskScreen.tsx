import { useEffect, useMemo, useState } from 'react';
import { IconSparkles } from '@baseflo/ui/icons';
import { useBusinessLiveArtifacts } from '../api/useOperatingData.js';
import { useOperatingRunStream } from '../api/useOperatingRunStream.js';
import { EvidenceTable } from '../components/EvidenceTable.js';
import { RunProgress } from '../components/RunProgress.js';
import { ErrorPanel, PrimaryButton, ScreenFrame, SecondaryButton } from '../../common/components/StatePanels.js';
import { WhyPanel } from '../components/WhyPanel.js';

export function AskScreen({ initialQuestion }: { initialQuestion?: string }) {
  const [question, setQuestion] = useState(initialQuestion ?? '');
  const runner = useOperatingRunStream();
  const live = useBusinessLiveArtifacts();
  const suggestions = useMemo(() => {
    const sectionQuestions = live.businessView.data?.sections.flatMap((section) => section.suggested_questions) ?? [];
    const surfaceQuestions = live.businessSurfaces.data?.surfaces.flatMap((surface) =>
      surface.candidate_views.map((view) => view.question),
    ) ?? [];
    return [...sectionQuestions, ...surfaceQuestions].filter(Boolean).slice(0, 8);
  }, [live.businessSurfaces.data, live.businessView.data]);

  useEffect(() => {
    if (initialQuestion) setQuestion(initialQuestion);
  }, [initialQuestion]);

  const submit = () => {
    const trimmed = question.trim();
    if (!trimmed) return;
    void runner.start({ mode: 'ask', question: trimmed });
  };

  const result = runner.result;
  const narratives = result?.narratives ?? [];
  const executions = result?.executions ?? [];

  return (
    <ScreenFrame
      eyebrow="ask · live investigation"
      title="Ask anything your connected data can support"
      summary="Ask starts a fresh operating run. The answer comes from analysis graphs executed on canonical data, then narrated with evidence."
    >
      <div className="grid gap-5 lg:grid-cols-[1fr_360px]">
        <section className="space-y-5">
          <form
            className="border border-ink/25 bg-paper-soft p-4"
            onSubmit={(event) => {
              event.preventDefault();
              submit();
            }}
          >
            <label className="font-sans text-[11px] font-semibold uppercase tracking-[0.22em] text-ink/45" htmlFor="ask-question">
              question
            </label>
            <textarea
              id="ask-question"
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              rows={4}
              className="mt-3 w-full resize-none border border-ink/25 bg-paper px-3 py-3 text-base leading-7 text-ink outline-none focus:border-flame"
              placeholder="Compare pending amounts by party, show low inventory, explain sales by customer..."
            />
            <div className="mt-3 flex flex-wrap gap-2">
              <PrimaryButton type="submit" disabled={runner.isRunning || !question.trim()}>
                <IconSparkles className="mr-2 h-4 w-4" />
                run ask
              </PrimaryButton>
              <SecondaryButton onClick={() => setQuestion('')} disabled={runner.isRunning}>
                clear
              </SecondaryButton>
            </div>
          </form>

          <RunProgress events={runner.events} isRunning={runner.isRunning} error={runner.error} />
          {runner.error ? <ErrorPanel error={runner.error} /> : null}

          {result ? (
            <section className="space-y-5">
              {narratives.map((narrative, index) => (
                <article key={`${narrative.headline}:${index}`} className="border border-ink/25 bg-paper-soft p-5">
                  <p className="font-mono text-[11px] uppercase tracking-[0.16em] text-ink/40">
                    answer block {index + 1}
                  </p>
                  <h2 className="mt-2 font-serif text-3xl font-bold italic text-ink">{String(narrative.headline ?? 'Answer')}</h2>
                  <p className="mt-3 text-base leading-7 text-ink/70">{String(narrative.summary ?? '')}</p>
                  {'why' in narrative ? <WhyPanel>{String(narrative.why)}</WhyPanel> : null}
                </article>
              ))}
              {executions.map((execution, index) => (
                <article key={`${String(execution.graph_id)}:${index}`} className="border border-ink/25 bg-paper-soft p-5">
                  <p className="font-mono text-[11px] uppercase tracking-[0.16em] text-ink/40">
                    evidence · {String(execution.graph_id)}
                  </p>
                  <div className="mt-3">
                    <EvidenceTable rows={previewRows(execution)} />
                  </div>
                </article>
              ))}
            </section>
          ) : null}
        </section>

        <aside className="space-y-4">
          <WhyPanel title="how ask works">
            Baseflo does not answer from prose alone. It plans analysis graphs, executes them, then returns tables,
            charts, action proposals, and narrative blocks that cite the run evidence.
          </WhyPanel>
          {suggestions.length ? (
            <div className="border border-ink/20 bg-paper-soft p-4">
              <p className="font-sans text-[11px] font-semibold uppercase tracking-[0.22em] text-ink/45">
                suggested questions
              </p>
              <div className="mt-3 space-y-2">
                {suggestions.map((suggestion) => (
                  <button
                    key={suggestion}
                    type="button"
                    onClick={() => setQuestion(suggestion)}
                    className="block w-full border border-ink/15 bg-white/35 px-3 py-2 text-left text-xs leading-5 text-ink/65 hover:border-flame"
                  >
                    {suggestion}
                  </button>
                ))}
              </div>
            </div>
          ) : null}
        </aside>
      </div>
    </ScreenFrame>
  );
}

function previewRows(execution: Record<string, unknown>): Array<Record<string, unknown>> {
  const result = execution.result;
  if (!isRecord(result)) return [];
  const rows = result.result_preview;
  return Array.isArray(rows) ? rows.filter(isRecord) : [];
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}
