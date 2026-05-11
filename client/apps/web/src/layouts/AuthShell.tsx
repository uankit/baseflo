import type { ReactNode } from 'react';
import { motion } from 'framer-motion';
import { PulseDot } from '@baseflo/ui';
import {
  IconBolt,
  IconUsers,
  IconShield,
  IconTrendingUp,
} from '@baseflo/ui/icons';

/**
 * Shell for unauthenticated routes (sign-in, sign-up, magic-link, password
 * reset). Atmospheric background with agent presence, premium card.
 * See docs/40-features/WEB-APP.md §4.1.
 */
export function AuthShell({ children }: { children: ReactNode }) {
  return (
    <div className="relative flex min-h-full w-full flex-col items-center justify-center bg-atmospheric bg-grid-dots px-4 py-12">
      {/* Subtle agent presence — bottom-right corner */}
      <div className="pointer-events-none absolute bottom-8 right-8 hidden flex-col items-end gap-3 md:flex">
        <span className="text-[10px] font-medium uppercase tracking-wider text-fg-subtle">
          4 agents on standby
        </span>
        <div className="flex items-center gap-2">
          {AGENTS.map((a, i) => (
            <motion.div
              key={a.id}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.4 + i * 0.1, duration: 0.5 }}
              className={`flex h-8 w-8 items-center justify-center rounded-full border ${a.border} ${a.bg} ${a.text} shadow-sm`}
              title={`${a.name} Agent`}
            >
              <a.icon size={14} />
            </motion.div>
          ))}
          <PulseDot tone="accent" size={6} active />
        </div>
      </div>

      <motion.header
        initial={{ opacity: 0, y: -6 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="mb-8 flex flex-col items-center gap-2"
      >
        <Wordmark />
        <p className="text-sm text-fg-muted">
          Run your business from one place.
        </p>
      </motion.header>

      <motion.main
        role="main"
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, delay: 0.15 }}
        className="w-full max-w-[420px] rounded-xl border border-border/80 bg-surface/95 p-8 shadow-lg backdrop-blur-sm"
      >
        {children}
      </motion.main>

      <motion.footer
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.4 }}
        className="mt-6 text-xs text-fg-subtle"
      >
        © {new Date().getFullYear()} Baseflo
      </motion.footer>
    </div>
  );
}

const AGENTS = [
  { id: 'source', name: 'Source', icon: IconBolt, border: 'border-accent/30', bg: 'bg-accent-soft', text: 'text-accent' },
  { id: 'recon', name: 'Recon', icon: IconUsers, border: 'border-purple-300', bg: 'bg-purple-50', text: 'text-purple-600' },
  { id: 'schema', name: 'Schema', icon: IconShield, border: 'border-emerald-300', bg: 'bg-emerald-50', text: 'text-emerald-600' },
  { id: 'insight', name: 'Insight', icon: IconTrendingUp, border: 'border-amber-300', bg: 'bg-amber-50', text: 'text-amber-600' },
];

function Wordmark() {
  return (
    <span
      className="font-serif text-2xl font-semibold tracking-tight text-fg"
      aria-label="Baseflo"
    >
      baseflo
    </span>
  );
}
