import { useEffect, useMemo, useState } from 'react';
import { IconSparkles, IconMessageSquare } from '@baseflo/ui/icons';
import { useBusinessLiveArtifacts } from '../api/useOperatingData.js';
import { useOperatingRunStream } from '../api/useOperatingRunStream.js';
import { EvidenceTable } from '../components/EvidenceTable.js';
import { VegaChart } from '../components/VegaChart.js';
import { RunProgress } from '../components/RunProgress.js';
import { ErrorPanel, PrimaryButton, ScreenFrame, SecondaryButton } from '../../common/components/StatePanels.js';
import { WhyPanel } from '../components/WhyPanel.js';
import type { VisualizationSpec } from 'vega-embed';

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
  const chartSpecs = result?.chart_specs ?? [];

  return (
    <ScreenFrame
      eyebrow="ask"
      title="Ask anything your data can answer"
      summary="Baseflo plans analysis graphs, executes them, then returns narrative answers with evidence you can verify."
    >
      <div className="grid gap-5 lg:grid-cols-[1fr_360px]">
        <section className="space-y-5">
          <form
            className="border border-ink/25 bg-paper-soft p-4 shadow-[3px_3px_0_rgba(28,25,20,0.1)]"
            onSubmit={(event) => {
              event.preventDefault();
              submit();
            }}
          >
            <label className="font-sans text-[11px] font-semibold uppercase tracking-[0.22em] text-ink/45" htmlFor="ask-question">
              your question
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
                <article
                  key={`${String(narrative.headline)}:${index}`}
                  className="border border-ink/25 bg-paper-soft p-5 shadow-[3px_3px_0_rgba(28,25,20,0.1)]"
                >
                  <div className="flex items-start gap-3">
                    <IconMessageSquare className="mt-1 h-5 w-5 shrink-0 text-flame" />
                    <div>
                      <h2 className="font-serif text-3xl font-bold italic text-ink">
                        {String(narrative.headline ?? 'Answer')}
                      </h2>
                      <p className="mt-3 text-base leading-7 text-ink/70">{String(narrative.summary ?? '')}</p>
                      {'why' in narrative ? <WhyPanel>{String(narrative.why)}</WhyPanel> : null}
                    </div>
                  </div>
                </article>
              ))}

              {chartSpecs.length > 0 ? (
                <div>
                  <p className="mb-2 font-sans text-[11px] font-semibold uppercase tracking-[0.22em] text-ink/45">
                    charts
                  </p>
                  <div className="grid gap-4 md:grid-cols-2">
                    {chartSpecs.map((spec, index) => {
                      const title = typeof spec.title === 'string' ? spec.title : `Chart ${index + 1}`;
                      const vegaSpec = (spec.vega_lite ?? spec.spec ?? spec) as Record<string, unknown>;
                      return (
                        <div key={index} className="border border-ink/20 bg-paper-soft p-3">
                          <VegaChart spec={vegaSpec as VisualizationSpec} title={title} />
                        </div>
                      );
                    })}
                  </div>
                </div>
              ) : null}

              {executions.length > 0 ? (
                <details className="border border-ink/25 bg-paper-soft">
                  <summary className="cursor-pointer p-4 text-sm font-semibold text-ink/60 hover:text-ink">
                    View evidence ({executions.length} source{executions.length > 1 ? 's' : ''})
                  </summary>
                  <div className="space-y-4 p-4 pt-0">
                    {executions.map((execution, index) => (
                      <div key={`${String(execution.graph_id)}:${index}`} className="border-t border-ink/10 pt-4">
                        <EvidenceTable rows={previewRows(execution)} />
                      </div>
                    ))}
                  </div>
                </details>
              ) : null}
            </section>
          ) : null}
        </section>

        <aside className="space-y-4">
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
