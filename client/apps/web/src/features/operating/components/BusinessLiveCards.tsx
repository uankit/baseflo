import { Link } from '@tanstack/react-router';
import { IconArrowRight, IconLightbulb } from '@baseflo/ui/icons';
import type {
  BusinessSurface,
  BusinessViewMetric,
  BusinessViewSection,
  CandidateView,
} from '../model/schemas.js';
import { labelize, percent } from '../../common/model/format.js';
import { TagList, WhyPanel } from './WhyPanel.js';

export function MetricStrip({ metrics }: { metrics: BusinessViewMetric[] }) {
  if (!metrics.length) return null;
  return (
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
      {metrics.map((metric) => (
        <div key={`${metric.label}:${metric.value}`} className="border border-ink/20 bg-paper-soft p-4">
          <p className="font-sans text-[11px] font-semibold uppercase tracking-[0.18em] text-ink/45">
            {metric.label}
          </p>
          <div className="mt-2 flex items-baseline gap-2">
            <strong className="font-serif text-3xl font-bold italic text-ink">{metric.value}</strong>
            {metric.unit ? <span className="text-sm text-ink/45">{metric.unit}</span> : null}
          </div>
          <p className="mt-2 text-xs leading-5 text-ink/55">{metric.why}</p>
        </div>
      ))}
    </div>
  );
}

export function BusinessSectionCard({
  section,
  surface,
}: {
  section: BusinessViewSection;
  surface?: BusinessSurface;
}) {
  const candidateViews = surface?.candidate_views ?? [];
  const cohorts = surface?.cohorts ?? [];
  const actions = surface?.action_packs ?? [];
  return (
    <article className="border border-ink/25 bg-paper-soft p-5 shadow-[3px_3px_0_rgba(28,25,20,0.12)]">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="font-mono text-[11px] uppercase tracking-[0.16em] text-ink/40">
            {labelize(section.kind)} · {percent(section.confidence)} conf
          </p>
          <h2 className="mt-2 font-serif text-3xl font-bold italic leading-tight text-ink">{section.title}</h2>
        </div>
        <Link
          to="/workspace/ask"
          search={{ q: section.suggested_questions[0] }}
          className="inline-flex shrink-0 items-center gap-1 border border-ink/40 px-2 py-1 text-xs font-semibold text-ink/70 hover:border-flame hover:text-flame"
        >
          ask
          <IconArrowRight className="h-3 w-3" />
        </Link>
      </div>
      <p className="mt-3 text-sm leading-6 text-ink/70">{section.description}</p>
      <div className="mt-4">
        <TagList tags={section.tags} />
      </div>

      <div className="mt-5">
        <MetricStrip metrics={section.metrics.slice(0, 4)} />
      </div>

      <div className="mt-5 grid gap-4 lg:grid-cols-[1fr_0.8fr]">
        <WhyPanel title="why built">{section.why_built}</WhyPanel>
        <div className="border border-ink/20 bg-paper p-4">
          <p className="font-sans text-[11px] font-semibold uppercase tracking-[0.22em] text-ink/45">
            workbench
          </p>
          <dl className="mt-3 grid grid-cols-3 gap-2 text-center">
            <div>
              <dt className="text-[11px] uppercase tracking-[0.14em] text-ink/40">views</dt>
              <dd className="font-serif text-2xl font-bold italic">{candidateViews.length}</dd>
            </div>
            <div>
              <dt className="text-[11px] uppercase tracking-[0.14em] text-ink/40">cohorts</dt>
              <dd className="font-serif text-2xl font-bold italic">{cohorts.length}</dd>
            </div>
            <div>
              <dt className="text-[11px] uppercase tracking-[0.14em] text-ink/40">actions</dt>
              <dd className="font-serif text-2xl font-bold italic">{actions.length}</dd>
            </div>
          </dl>
        </div>
      </div>

      {candidateViews.length ? (
        <div className="mt-5 grid gap-3 md:grid-cols-2">
          {candidateViews.slice(0, 4).map((view) => (
            <CandidateViewCard key={view.view_id} view={view} />
          ))}
        </div>
      ) : null}
    </article>
  );
}

export function CandidateViewCard({ view }: { view: CandidateView }) {
  return (
    <div className="border border-ink/15 bg-white/35 p-3">
      <div className="flex items-start gap-2">
        <IconLightbulb className="mt-0.5 h-4 w-4 shrink-0 text-flame" />
        <div>
          <p className="text-sm font-semibold text-ink">{view.title}</p>
          <p className="mt-1 text-xs leading-5 text-ink/60">{view.question}</p>
          <p className="mt-2 font-mono text-[10px] uppercase tracking-[0.14em] text-ink/35">
            {view.algorithm} · {view.expected_output} · {percent(view.priority)}
          </p>
        </div>
      </div>
    </div>
  );
}
