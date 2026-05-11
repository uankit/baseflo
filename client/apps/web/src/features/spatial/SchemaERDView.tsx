import { useState, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Badge } from '@baseflo/ui';
import { IconLayers, IconDatabase, IconZap } from '@baseflo/ui/icons';
import { cn } from '@baseflo/ui/lib/utils';

interface Column {
  name: string;
  semanticType: string;
  physicalType: string;
  nullable: boolean;
}

interface Relationship {
  fromTable: string;
  fromColumn: string;
  toTable: string;
  toColumn: string;
  cardinality: string;
}

interface Table {
  name: string;
  label: string;
  columns: Column[];
  primaryKey: string[];
}

interface SchemaERDViewProps {
  tables: Table[];
  relationships: Relationship[];
}

export function SchemaERDView({ tables, relationships }: SchemaERDViewProps) {
  const [selectedTable, setSelectedTable] = useState<string | null>(null);

  const relatedTables = useMemo(() => {
    if (!selectedTable) return new Set<string>();
    const set = new Set<string>();
    relationships.forEach((r) => {
      if (r.fromTable === selectedTable) set.add(r.toTable);
      if (r.toTable === selectedTable) set.add(r.fromTable);
    });
    return set;
  }, [selectedTable, relationships]);

  if (tables.length === 0) {
    return (
      <div className="flex flex-col gap-4">
        <header className="rounded-xl bg-atmospheric bg-grid-dots px-6 py-8">
          <div className="flex items-center gap-2">
            <IconLayers className="h-5 w-5 text-accent" />
            <h2 className="font-serif text-2xl font-semibold text-fg">Architectural Blueprint</h2>
          </div>
          <p className="mt-1 text-sm text-fg-muted">
            The unified schema your agents designed from all connected sources.
          </p>
        </header>
        <div className="flex h-64 flex-col items-center justify-center gap-3 rounded-xl border border-dashed border-border bg-surface">
          <IconDatabase className="h-8 w-8 text-fg-subtle/40" />
          <p className="text-sm font-medium text-fg-muted">Blueprint pending</p>
          <p className="text-xs text-fg-subtle">The Schema Architect is still designing your tables.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <header className="rounded-xl bg-atmospheric bg-grid-dots px-6 py-8">
        <div className="flex items-center gap-2">
          <IconLayers className="h-5 w-5 text-accent" />
          <h2 className="font-serif text-2xl font-semibold text-fg">Architectural Blueprint</h2>
          <Badge variant="info" className="ml-2">
            {tables.length} tables
          </Badge>
        </div>
        <p className="mt-1 text-sm text-fg-muted">
          The unified schema your agents designed from all connected sources. Select a table to illuminate its connections.
        </p>
      </header>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {tables.map((table) => {
          const isSelected = selectedTable === table.name;
          const isRelated = relatedTables.has(table.name);
          return (
            <motion.div
              key={table.name}
              layout
              onClick={() =>
                setSelectedTable(selectedTable === table.name ? null : table.name)
              }
              className={cn(
                'cursor-pointer rounded-xl border p-4 transition-all duration-normal',
                isSelected
                  ? 'border-accent bg-accent/5 shadow-[0_0_24px_-6px_hsl(var(--color-accent)/0.25)]'
                  : isRelated
                    ? 'border-accent/40 bg-surface shadow-sm'
                    : 'border-border bg-surface hover:border-border-focus',
              )}
            >
              <div className="mb-3 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span
                    className={cn(
                      'h-2 w-2 rounded-full',
                      isSelected ? 'bg-accent shadow-[0_0_6px_hsl(var(--color-accent)/0.6)]' : 'bg-fg-subtle/40',
                    )}
                  />
                  <h3 className="text-sm font-semibold text-fg">{table.label}</h3>
                </div>
                <span className="rounded bg-surface-2 px-1.5 py-0.5 text-[10px] font-mono text-fg-subtle">
                  {table.name}
                </span>
              </div>
              <div className="flex flex-col gap-1">
                {table.columns.slice(0, 5).map((col) => (
                  <div
                    key={col.name}
                    className="flex items-center justify-between text-xs"
                  >
                    <span
                      className={cn(
                        table.primaryKey.includes(col.name)
                          ? 'font-semibold text-accent'
                          : 'text-fg-muted',
                      )}
                    >
                      {col.name}
                      {table.primaryKey.includes(col.name) && ' 🔑'}
                    </span>
                    <span className="font-mono text-[10px] text-fg-subtle">
                      {col.physicalType}
                    </span>
                  </div>
                ))}
                {table.columns.length > 5 && (
                  <span className="text-[10px] text-fg-subtle">
                    +{table.columns.length - 5} more
                  </span>
                )}
              </div>
            </motion.div>
          );
        })}
      </div>

      <AnimatePresence>
        {selectedTable && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="overflow-hidden rounded-xl border border-accent/30 bg-surface p-4 shadow-sm"
          >
            <div className="mb-3 flex items-center gap-2">
              <IconZap className="h-4 w-4 text-accent" />
              <h4 className="text-sm font-semibold text-fg">
                Schematic connections for {selectedTable}
              </h4>
            </div>
            <div className="flex flex-col gap-2">
              {relationships
                .filter(
                  (r) =>
                    r.fromTable === selectedTable || r.toTable === selectedTable,
                )
                .map((r) => (
                  <div
                    key={`${r.fromTable}.${r.fromColumn}-${r.toTable}.${r.toColumn}`}
                    className="flex items-center gap-2 rounded-lg border border-border bg-bg px-3 py-2 text-xs"
                  >
                    <span className="rounded bg-accent-soft px-1.5 py-0.5 font-mono text-fg">{r.fromTable}</span>
                    <span className="text-fg-subtle">.</span>
                    <span className="font-mono text-fg-muted">{r.fromColumn}</span>
                    <span className="text-accent">→</span>
                    <span className="rounded bg-accent-soft px-1.5 py-0.5 font-mono text-fg">{r.toTable}</span>
                    <span className="text-fg-subtle">.</span>
                    <span className="font-mono text-fg-muted">{r.toColumn}</span>
                    <Badge variant="info" className="ml-auto text-[10px]">
                      {r.cardinality}
                    </Badge>
                  </div>
                ))}
              {relationships.filter(
                (r) =>
                  r.fromTable === selectedTable || r.toTable === selectedTable,
              ).length === 0 && (
                <p className="text-xs text-fg-subtle">No schematic connections for this table.</p>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
