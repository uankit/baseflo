import { useState } from 'react';
import { IconArrowRight, IconSparkles } from '@baseflo/ui/icons';
import { useChat } from '../chat/useChat.js';
import {
  asRecordArray,
  asString,
  asStringArray,
  businessBrief,
  insightActions,
  topInsights,
  useOperatingBrief,
} from './operatingData.js';
import {
  EmptyPaper,
  EvidenceTable,
  InferenceRow,
  LoadingPaper,
  PageKicker,
  PrimaryButton,
  SectionTitle,
  compactRow,
} from './OperatingUI.js';

export function OperatingAsk() {
  const { messages, sendMessage, isLoading } = useChat();
  const [input, setInput] = useState('');
  const briefQuery = useOperatingBrief();
  const brief = briefQuery.data;
  const business = businessBrief(brief);
  const questions = asStringArray(brief?.business ? brief.business.recommended_questions : []);
  const insights = topInsights(brief);

  const submit = (value: string) => {
    const question = value.trim();
    if (!question || isLoading) return;
    void sendMessage(question);
    setInput('');
  };

  if (briefQuery.isLoading) return <LoadingPaper label="Preparing Ask…" />;

  const starters = questions.length
    ? questions
    : [
        'Which products need attention first?',
        'What changed since the last sync?',
        'Draft the best next action from the top read.',
      ];

  return (
    <div className="grid min-h-[calc(100vh-53px)] bg-paper text-ink xl:grid-cols-[430px_minmax(0,1fr)]">
      <section className="flex min-h-[calc(100vh-53px)] flex-col border-r border-ink/20 bg-paper-soft">
        <div className="border-b border-ink/18 p-5">
          <PageKicker>Ask · investigation canvas</PageKicker>
          <h1 className="mt-2 font-serif text-[38px] font-bold italic leading-none">Compare, explain, draft</h1>
        </div>

        <div className="min-h-0 flex-1 space-y-4 overflow-auto p-4">
          {messages.length === 0 ? (
            <div className="space-y-3">
              {starters.slice(0, 5).map((question, index) => (
                <button
                  key={`${question}-${index}`}
                  type="button"
                  onClick={() => submit(question)}
                  className="block w-full border border-ink/35 bg-paper p-3 text-left font-sans text-[13px] leading-5 text-ink/70 transition hover:border-ink hover:bg-white"
                >
                  <span className="flex gap-2">
                    <IconSparkles className="mt-0.5 h-4 w-4 shrink-0 text-flame" />
                    {question}
                  </span>
                </button>
              ))}
            </div>
          ) : null}

          {messages.map((message) => (
            <div key={message.id} className={message.role === 'user' ? 'text-right' : 'text-left'}>
              <div
                className={`inline-block max-w-[95%] border px-4 py-3 font-sans text-sm leading-6 ${
                  message.role === 'user'
                    ? 'border-ink bg-ink text-paper'
                    : 'border-ink/45 bg-paper text-ink shadow-[2px_2px_0_rgba(28,25,20,0.18)]'
                }`}
              >
                <p className="whitespace-pre-wrap">{message.content}</p>
                {message.role === 'assistant' && message.toolCalls ? (
                  <div className="mt-3 font-mono text-[10px] uppercase tracking-[0.12em] text-ink/35">
                    {message.toolCalls} data call{message.toolCalls === 1 ? '' : 's'}
                  </div>
                ) : null}
              </div>
              {message.artifacts?.length ? (
                <div className="mt-3 space-y-2 text-left">
                  {message.artifacts.map((artifact, index) => (
                    <ArtifactBlock key={index} artifact={artifact} />
                  ))}
                </div>
              ) : null}
            </div>
          ))}

          {isLoading ? (
            <div className="border border-ink/25 bg-paper p-3 font-sans text-sm text-ink/55">
              Reading connected data…
            </div>
          ) : null}
        </div>

        <form
          onSubmit={(event) => {
            event.preventDefault();
            submit(input);
          }}
          className="border-t border-ink/18 bg-paper p-4"
        >
          <div className="flex gap-2">
            <input
              value={input}
              onChange={(event) => setInput(event.target.value)}
              placeholder="Ask a comparison, cause, cohort, or next move"
              className="h-10 min-w-0 flex-1 border border-ink/60 bg-white px-3 font-sans text-sm outline-none focus:border-flame"
            />
            <PrimaryButton disabled={!input.trim() || isLoading} icon={<IconArrowRight className="h-3.5 w-3.5" />}>
              send
            </PrimaryButton>
          </div>
        </form>
      </section>

      <main className="min-h-0 overflow-auto p-5 md:p-8">
        <header className="mb-6 border-b-2 border-ink pb-5">
          <PageKicker>Ready evidence</PageKicker>
          <h2 className="mt-2 max-w-[900px] font-serif text-[44px] font-bold italic leading-[1.03] md:text-[58px]">
            {asString(business.title, 'Ask from the current operating state')}
          </h2>
        </header>

        <section className="space-y-4">
          <SectionTitle>Open investigation units</SectionTitle>
          {insights.length ? (
            insights.slice(0, 5).map((insight) => (
              <InferenceRow
                key={asString(insight.id, asString(insight.title))}
                insight={insight}
                actions={insightActions(insight, brief)}
                onOpen={() => submit(`Explain this read: ${asString(insight.title)}`)}
              />
            ))
          ) : (
            <EmptyPaper title="Nothing to investigate yet" body="Ask becomes sharper once the first scan produces inferences." />
          )}
        </section>
      </main>
    </div>
  );
}

function ArtifactBlock({ artifact }: { artifact: Record<string, unknown> }) {
  const rows = asRecordArray(artifact.rows).concat(asRecordArray(artifact.result_preview));
  return (
    <div className="border border-ink/35 bg-paper p-3 shadow-[2px_2px_0_rgba(28,25,20,0.14)]">
      <div className="font-mono text-[10px] uppercase tracking-[0.14em] text-ink/40">
        {asString(artifact.type, 'Artifact')}
      </div>
      <div className="mt-1 font-sans text-sm font-bold text-ink">
        {asString(artifact.title, rows[0] ? compactRow(rows[0], 3) : 'Generated artifact')}
      </div>
      {rows.length ? <div className="mt-3"><EvidenceTable rows={rows} compact /></div> : null}
    </div>
  );
}
