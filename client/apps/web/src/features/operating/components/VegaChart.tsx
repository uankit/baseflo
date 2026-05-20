import { useEffect, useRef } from 'react';
import embed from 'vega-embed';
import type { VisualizationSpec } from 'vega-embed';

export interface VegaChartProps {
  spec: VisualizationSpec | Record<string, unknown>;
  className?: string;
  title?: string;
}

export function VegaChart({ spec, className, title }: VegaChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const embedRef = useRef<Promise<{ finalize: () => void }> | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;
    const el = containerRef.current;

    void (async () => {
      try {
        const result = await embed(el, spec as VisualizationSpec, {
          actions: false,
          renderer: 'svg',
          config: {
            background: 'transparent',
            view: { stroke: 'transparent' },
            axis: {
              domainColor: 'rgba(28,25,20,0.15)',
              tickColor: 'rgba(28,25,20,0.15)',
              labelColor: 'rgba(28,25,20,0.55)',
              labelFont: 'ui-sans-serif, system-ui, sans-serif',
              labelFontSize: 10,
              titleColor: 'rgba(28,25,20,0.55)',
              titleFontSize: 11,
              gridColor: 'rgba(28,25,20,0.08)',
            },
            legend: {
              labelColor: 'rgba(28,25,20,0.6)',
              labelFontSize: 11,
              titleColor: 'rgba(28,25,20,0.7)',
              titleFontSize: 12,
            },
            title: {
              color: 'rgba(28,25,20,0.8)',
              font: 'ui-serif, Georgia, serif',
              fontSize: 14,
              fontWeight: 700,
            },
            bar: { fill: 'rgba(28,25,20,0.8)' },
            line: { stroke: 'rgba(28,25,20,0.8)', strokeWidth: 2 },
            point: { fill: 'rgba(28,25,20,0.8)', stroke: 'transparent' },
            arc: { fill: 'rgba(28,25,20,0.8)' },
            rule: { stroke: 'rgba(28,25,20,0.25)' },
            text: { color: 'rgba(28,25,20,0.6)', fontSize: 11 },
          },
        });
        embedRef.current = Promise.resolve(result);
      } catch {
        // vega-embed handles its own errors; we just avoid crashing
      }
    })();

    return () => {
      void embedRef.current?.then((view) => view.finalize()).catch(() => undefined);
    };
  }, [spec]);

  return (
    <div className={className}>
      {title ? (
        <p className="mb-2 font-sans text-[11px] font-semibold uppercase tracking-[0.22em] text-ink/45">
          {title}
        </p>
      ) : null}
      <div ref={containerRef} />
    </div>
  );
}
