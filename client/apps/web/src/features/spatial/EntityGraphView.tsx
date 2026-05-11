import { useEffect, useRef, useMemo } from 'react';
import { motion } from 'framer-motion';
import { Badge } from '@baseflo/ui';
import { IconGitMerge, IconDatabase, IconSparkles } from '@baseflo/ui/icons';

interface EntityNode {
  id: string;
  name: string;
  kind: string;
  x: number;
  y: number;
  sources: string[];
}

interface EntityGraphViewProps {
  entities: Array<{
    canonicalId: string;
    entityKind: string;
    displayName: string;
    sources: Array<{
      source: string;
      confidence: number;
    }>;
  }>;
}

const SOURCE_COLORS: Record<string, string> = {
  stripe: '#6366f1',
  shopify: '#10b981',
  postgres: '#f59e0b',
  csv: '#6b7280',
  excel: '#059669',
  google_sheets: '#0ea5e9',
};

export function EntityGraphView({ entities }: EntityGraphViewProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  const nodes = useMemo(() => {
    const n: EntityNode[] = [];
    const count = entities.length;
    entities.forEach((e, i) => {
      const angle = (i / count) * Math.PI * 2;
      const radius = 120 + Math.random() * 60;
      n.push({
        id: e.canonicalId,
        name: e.displayName,
        kind: e.entityKind,
        x: 300 + Math.cos(angle) * radius,
        y: 200 + Math.sin(angle) * radius,
        sources: e.sources.map((s) => s.source),
      });
    });
    return n;
  }, [entities]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || nodes.length === 0) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    canvas.width = 600 * dpr;
    canvas.height = 400 * dpr;
    ctx.scale(dpr, dpr);

    // Subtle grid background
    ctx.strokeStyle = 'rgba(148, 163, 184, 0.08)';
    ctx.lineWidth = 1;
    const gridSize = 40;
    for (let gx = 0; gx <= 600; gx += gridSize) {
      ctx.beginPath();
      ctx.moveTo(gx, 0);
      ctx.lineTo(gx, 400);
      ctx.stroke();
    }
    for (let gy = 0; gy <= 400; gy += gridSize) {
      ctx.beginPath();
      ctx.moveTo(0, gy);
      ctx.lineTo(600, gy);
      ctx.stroke();
    }

    // Draw edges as constellation lines
    ctx.strokeStyle = 'rgba(148, 163, 184, 0.25)';
    ctx.lineWidth = 1;
    ctx.setLineDash([4, 4]);
    for (let i = 0; i < nodes.length; i++) {
      const ni = nodes[i]!;
      for (let j = i + 1; j < nodes.length; j++) {
        const nj = nodes[j]!;
        const shared = ni.sources.filter((s) => nj.sources.includes(s));
        if (shared.length > 0) {
          ctx.beginPath();
          ctx.moveTo(ni.x, ni.y);
          ctx.lineTo(nj.x, nj.y);
          ctx.stroke();
        }
      }
    }
    ctx.setLineDash([]);

    // Draw nodes
    nodes.forEach((node) => {
      // Outer glow for star effect
      const gradient = ctx.createRadialGradient(
        node.x,
        node.y,
        0,
        node.x,
        node.y,
        40,
      );
      gradient.addColorStop(0, 'rgba(99, 102, 241, 0.15)');
      gradient.addColorStop(1, 'rgba(99, 102, 241, 0)');
      ctx.fillStyle = gradient;
      ctx.beginPath();
      ctx.arc(node.x, node.y, 40, 0, Math.PI * 2);
      ctx.fill();

      // Main node body
      ctx.beginPath();
      ctx.arc(node.x, node.y, 24, 0, Math.PI * 2);
      ctx.fillStyle = '#1e293b';
      ctx.fill();
      ctx.strokeStyle = '#475569';
      ctx.lineWidth = 2;
      ctx.stroke();

      // Source indicator arcs (vibrant)
      node.sources.forEach((source, idx) => {
        const color = SOURCE_COLORS[source] || '#94a3b8';
        ctx.beginPath();
        ctx.arc(
          node.x,
          node.y,
          28,
          (idx / node.sources.length) * Math.PI * 2 - Math.PI / 2,
          ((idx + 1) / node.sources.length) * Math.PI * 2 - Math.PI * 0.4,
        );
        ctx.strokeStyle = color;
        ctx.lineWidth = 3;
        ctx.stroke();
      });

      // Label
      ctx.fillStyle = '#f8fafc';
      ctx.font = '600 11px sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText(node.name.slice(0, 12), node.x, node.y + 4);
    });
  }, [nodes]);

  if (entities.length === 0) {
    return (
      <div className="flex flex-col gap-4">
        <header className="rounded-xl bg-atmospheric bg-grid-dots px-6 py-8">
          <div className="flex items-center gap-2">
            <IconGitMerge className="h-5 w-5 text-accent" />
            <h2 className="font-serif text-2xl font-semibold text-fg">Constellation Map</h2>
          </div>
          <p className="mt-1 text-sm text-fg-muted">
            Reconciled entities across all connected sources, mapped as a celestial network.
          </p>
        </header>
        <div className="flex h-64 flex-col items-center justify-center gap-3 rounded-xl border border-dashed border-border bg-surface">
          <IconDatabase className="h-8 w-8 text-fg-subtle/40" />
          <p className="text-sm font-medium text-fg-muted">Uncharted territory</p>
          <p className="text-xs text-fg-subtle">No entities reconciled yet. The Recon agent will map them soon.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <header className="rounded-xl bg-atmospheric bg-grid-dots px-6 py-8">
        <div className="flex items-center gap-2">
          <IconGitMerge className="h-5 w-5 text-accent" />
          <h2 className="font-serif text-2xl font-semibold text-fg">Constellation Map</h2>
          <Badge variant="accent" className="ml-2">
            <IconSparkles className="mr-1 h-3 w-3" />
            {entities.length} entities
          </Badge>
        </div>
        <p className="mt-1 text-sm text-fg-muted">
          Reconciled entities across all connected sources. Each star is a unified entity; arcs show shared origins.
        </p>
      </header>

      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        className="relative rounded-xl border border-border bg-bg p-4"
      >
        <canvas
          ref={canvasRef}
          style={{ width: 600, height: 400 }}
          className="rounded-lg"
        />
        <div className="mt-3 flex flex-wrap gap-3 rounded-lg border border-border bg-surface p-3">
          <span className="text-[10px] font-bold uppercase tracking-widest text-fg-subtle">
            Map Key
          </span>
          {Object.entries(SOURCE_COLORS).map(([source, color]) => (
            <div key={source} className="flex items-center gap-1.5">
              <span className="h-2.5 w-2.5 rounded-full shadow-sm" style={{ backgroundColor: color }} />
              <span className="text-xs text-fg-muted capitalize">{source.replace('_', ' ')}</span>
            </div>
          ))}
        </div>
      </motion.div>
    </div>
  );
}
