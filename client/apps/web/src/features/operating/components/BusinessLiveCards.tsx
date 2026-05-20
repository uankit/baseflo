import { Link } from '@tanstack/react-router';
import { IconArrowRight, IconLightbulb, IconBarChart3, IconDatabase, IconLayers } from '@baseflo/ui/icons';
import type {
  BusinessSurface,
  BusinessViewMetric,
  BusinessViewSection,
  CandidateView,
  SourceStructurePackage,
} from '../model/schemas.js';
import { labelize } from '../../common/model/format.js';
import { TagList, WhyPanel } from './WhyPanel.js';
import { MetricCard } from './MetricCard.js';
import { CohortCard } from './CohortCard.js';
import { ActionPackCard } from './ActionPackCard.js';
import { VegaChart } from './VegaChart.js';
import type { VisualizationSpec } from 'vega-embed';

export function MetricStrip({ metrics }: { metrics: BusinessViewMetric[] }) {
  if (!metrics.length) return null;
  return (
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
      {metrics.map((metric) => (
        <MetricCard key={`${metric.label}:${metric.value}`} metric={metric} />
      ))}
    </div>
  );
}

export function SourceStructurePanel({ pkg }: { pkg: SourceStructurePackage | null }) {
  if (!pkg) return null;
  const ready = pkg.routing.filter((route) => route.route === 'deterministic_ready').length;
  const review = pkg.routing.length - ready;
  const topWorkbenches = pkg.workbenches.slice(0, 6);
  const reviewAssets = pkg.assets.filter((asset) => asset.requires_human_confirmation).slice(0, 3);

  return (
    <section className="border border-ink/20 bg-paper-soft p-4">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex min-w-0 items-start gap-3">
          <IconDatabase className="mt-1 h-4 w-4 shrink-0 text-ink/35" />
          <div>
            <p className="font-sans text-[11px] font-semibold uppercase tracking-[0.22em] text-ink/45">
              data layer
            </p>
            <h2 className="mt-1 text-lg font-semibold text-ink">
              {pkg.assets.length} assets · {pkg.workbenches.length} workbenches · {Math.round(pkg.confidence * 100)}% confidence
            </h2>
          </div>
        </div>
        <dl className="grid grid-cols-3 gap-3 text-right">
          <div>
            <dt className="font-mono text-[10px] uppercase tracking-[0.14em] text-ink/40">ready</dt>
            <dd className="font-serif text-2xl font-bold italic text-ink">{ready}</dd>
          </div>
          <div>
            <dt className="font-mono text-[10px] uppercase tracking-[0.14em] text-ink/40">review</dt>
            <dd className="font-serif text-2xl font-bold italic text-flame">{review}</dd>
          </div>
          <div>
            <dt className="font-mono text-[10px] uppercase tracking-[0.14em] text-ink/40">agent</dt>
            <dd className="text-sm font-semibold text-ink">{pkg.agentic_status.replace(/_/g, ' ')}</dd>
          </div>
        </dl>
      </div>

      {topWorkbenches.length ? (
        <div className="mt-4 grid gap-2 md:grid-cols-2 xl:grid-cols-3">
          {topWorkbenches.map((workbench) => (
            <Link
              key={workbench.workbench_id}
              to="/workspace/register"
              className="flex items-center justify-between border border-ink/15 bg-white/35 px-3 py-2 hover:border-flame"
            >
              <span className="flex min-w-0 items-center gap-2">
                <IconLayers className="h-3.5 w-3.5 shrink-0 text-ink/35" />
                <span className="truncate text-sm font-semibold text-ink">{workbench.title}</span>
              </span>
              <span className="font-mono text-[10px] uppercase tracking-[0.12em] text-ink/40">
                {workbench.views.length} views
              </span>
            </Link>
          ))}
        </div>
      ) : null}

      {reviewAssets.length ? (
        <div className="mt-4 border-t border-ink/10 pt-3">
          <p className="font-mono text-[10px] uppercase tracking-[0.14em] text-ink/40">
            structure review
          </p>
          <div className="mt-2 space-y-1">
            {reviewAssets.map((asset) => (
              <div key={asset.asset_id ?? asset.asset_key} className="flex items-center justify-between gap-3 text-sm">
                <span className="truncate text-ink/70">{asset.label}</span>
                <span className="shrink-0 font-mono text-[10px] uppercase tracking-[0.12em] text-flame">
                  {Math.round(asset.confidence * 100)}%
                </span>
              </div>
            ))}
          </div>
        </div>
      ) : null}
    </section>
  );
}

export function BusinessSectionCard({
  section,
  surface,
  charts = [],
}: {
  section: BusinessViewSection;
  surface?: BusinessSurface;
  charts?: Array<{ chart_id: string; title: string; vega_lite: Record<string, unknown> }>;
}) {
  const candidateViews = surface?.candidate_views ?? [];
  const cohorts = surface?.cohorts ?? [];
  const actions = surface?.action_packs ?? [];
  const surfaceCharts = charts.filter((c) =>
    section.chart_refs.includes(c.chart_id),
  );

  return (
    <article className="border border-ink/25 bg-paper-soft p-5 shadow-[3px_3px_0_rgba(28,25,20,0.12)]">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="font-mono text-[11px] uppercase tracking-[0.16em] text-ink/40">
            {labelize(section.kind)}
          </p>
          <h2 className="mt-2 font-serif text-3xl font-bold italic leading-tight text-ink">
            {section.title}
          </h2>
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

      {section.metrics.length ? (
        <div className="mt-5">
          <MetricStrip metrics={section.metrics.slice(0, 4)} />
        </div>
      ) : null}

      {surfaceCharts.length ? (
        <div className="mt-5 grid gap-4 md:grid-cols-2">
          {surfaceCharts.map((chart) => (
            <div key={chart.chart_id} className="border border-ink/15 bg-white/40 p-3">
              <VegaChart
                spec={chart.vega_lite as VisualizationSpec}
                title={chart.title}
              />
            </div>
          ))}
        </div>
      ) : null}

      {cohorts.length ? (
        <div className="mt-5">
          <p className="mb-2 font-sans text-[11px] font-semibold uppercase tracking-[0.22em] text-ink/45">
            cohorts
          </p>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {cohorts.map((cohort) => (
              <CohortCard key={cohort.cohort_id} cohort={cohort} />
            ))}
          </div>
        </div>
      ) : null}

      {actions.length ? (
        <div className="mt-5">
          <p className="mb-2 font-sans text-[11px] font-semibold uppercase tracking-[0.22em] text-ink/45">
            action packs
          </p>
          <div className="grid gap-3 sm:grid-cols-2">
            {actions.map((action) => (
              <ActionPackCard key={action.action_pack_id} action={action} />
            ))}
          </div>
        </div>
      ) : null}

      <div className="mt-5 grid gap-4 lg:grid-cols-[1fr_0.8fr]">
        <WhyPanel title="why built">{section.why_built}</WhyPanel>
        <WorkbenchPanel views={candidateViews.length} cohorts={cohorts.length} actions={actions.length} />
      </div>

      {candidateViews.length ? (
        <div className="mt-5 grid gap-3 md:grid-cols-2">
          {candidateViews.slice(0, 4).map((view) => (
            <CandidateViewCard key={view.view_id} view={view} />
          ))}
        </div>
      ) : null}

      {section.drilldowns.length ? (
        <div className="mt-5">
          <p className="mb-2 font-sans text-[11px] font-semibold uppercase tracking-[0.22em] text-ink/45">
            drilldowns
          </p>
          <div className="flex flex-wrap gap-2">
            {section.drilldowns.map((d) => (
              <Link
                key={d.drilldown_id}
                to="/workspace/ask"
                search={{ q: d.question }}
                className="border border-ink/20 bg-paper px-3 py-1.5 text-xs font-semibold text-ink/65 hover:border-flame hover:text-flame"
              >
                {d.label}
              </Link>
            ))}
          </div>
        </div>
      ) : null}
    </article>
  );
}

function WorkbenchPanel({ views, cohorts, actions }: { views: number; cohorts: number; actions: number }) {
  return (
    <div className="border border-ink/20 bg-paper p-4">
      <p className="font-sans text-[11px] font-semibold uppercase tracking-[0.22em] text-ink/45">
        workbench
      </p>
      <dl className="mt-3 grid grid-cols-3 gap-2 text-center">
        <div>
          <dt className="text-[11px] uppercase tracking-[0.14em] text-ink/40">views</dt>
          <dd className="font-serif text-2xl font-bold italic">{views}</dd>
        </div>
        <div>
          <dt className="text-[11px] uppercase tracking-[0.14em] text-ink/40">cohorts</dt>
          <dd className="font-serif text-2xl font-bold italic">{cohorts}</dd>
        </div>
        <div>
          <dt className="text-[11px] uppercase tracking-[0.14em] text-ink/40">actions</dt>
          <dd className="font-serif text-2xl font-bold italic">{actions}</dd>
        </div>
      </dl>
    </div>
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
            {view.expected_output}
          </p>
        </div>
      </div>
    </div>
  );
}

export function ChartGallery({
  charts,
}: {
  charts: Array<{ chart_id: string; title: string; vega_lite: Record<string, unknown> }>;
}) {
  if (!charts.length) return null;
  return (
    <section className="space-y-4">
      <div className="flex items-center gap-2">
        <IconBarChart3 className="h-4 w-4 text-ink/40" />
        <p className="font-sans text-[11px] font-semibold uppercase tracking-[0.22em] text-ink/45">
          chart gallery
        </p>
      </div>
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {charts.map((chart) => (
          <div key={chart.chart_id} className="border border-ink/20 bg-paper-soft p-3">
            <VegaChart
              spec={chart.vega_lite as VisualizationSpec}
              title={chart.title}
            />
          </div>
        ))}
      </div>
    </section>
  );
}
