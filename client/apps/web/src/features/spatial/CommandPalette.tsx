import { useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { IconSearch, IconSparkles } from '@baseflo/ui/icons';

interface Suggestion {
  id: string;
  label: string;
  description: string;
  icon: 'query' | 'action' | 'navigate';
}

interface CommandPaletteProps {
  open: boolean;
  onClose: () => void;
  query: string;
  onQueryChange: (q: string) => void;
  suggestions: Suggestion[];
}

export function CommandPalette({
  open,
  onClose,
  query,
  onQueryChange,
  suggestions,
}: CommandPaletteProps) {
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (open) {
      inputRef.current?.focus();
    }
  }, [open]);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        if (open) onClose();
        else {
          // Parent controls open state via onClose
        }
      }
      if (e.key === 'Escape' && open) {
        onClose();
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [open, onClose]);

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-[100] flex items-start justify-center bg-bg/60 pt-[20vh] backdrop-blur-sm"
          onClick={onClose}
        >
          <motion.div
            initial={{ opacity: 0, scale: 0.96, y: -8 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.96, y: -8 }}
            transition={{ duration: 0.15 }}
            className="w-full max-w-xl overflow-hidden rounded-xl border border-border bg-surface shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center gap-3 border-b border-border px-4 py-3">
              <IconSearch size={18} className="text-fg-muted" />
              <input
                ref={inputRef}
                value={query}
                onChange={(e) => onQueryChange(e.target.value)}
                placeholder="Ask anything about your data…"
                className="flex-1 bg-transparent text-sm text-fg outline-none placeholder:text-fg-subtle"
              />
              <kbd className="rounded bg-surface-2 px-1.5 py-0.5 font-mono text-[10px] text-fg-muted">
                ESC
              </kbd>
            </div>

            <div className="max-h-80 overflow-auto py-2">
              {suggestions.length === 0 && query && (
                <div className="flex items-center gap-2 px-4 py-3 text-sm text-fg-muted">
                  <IconSparkles size={16} />
                  <span>Press Enter to ask Baseflo</span>
                </div>
              )}
              {suggestions.map((s) => (
                <button
                  key={s.id}
                  className="flex w-full items-start gap-3 px-4 py-2.5 text-left transition-colors hover:bg-surface-2"
                >
                  <span className="mt-0.5 text-fg-muted">
                    {s.icon === 'query' && <IconSearch size={14} />}
                    {s.icon === 'action' && <IconSparkles size={14} />}
                  </span>
                  <div>
                    <p className="text-sm text-fg">{s.label}</p>
                    <p className="text-xs text-fg-muted">{s.description}</p>
                  </div>
                </button>
              ))}
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
