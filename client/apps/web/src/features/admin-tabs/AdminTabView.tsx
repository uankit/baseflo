import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  Card,
  CardContent,
  EmptyState,
  ErrorCallout,
  Input,
  LoadingSkeletonRow,
} from '@baseflo/ui';
import { IconSearch } from '@baseflo/ui/icons';
import type { AdminTab } from '@baseflo/contracts';
import { useGateway } from '../../providers/GatewayProvider.js';
import { RenderCell, RowAttribution } from './cellRenderers.js';
import { EntityDetailDrawer } from './EntityDetailDrawer.js';

interface AdminTabViewProps {
  tab: AdminTab;
  versionId: string;
}

export function AdminTabView({ tab, versionId }: AdminTabViewProps) {
  const gateway = useGateway();
  const [search, setSearch] = useState('');
  const [selectedRowId, setSelectedRowId] = useState<string | null>(null);

  const dataQuery = useQuery({
    queryKey: ['entity-list', versionId, tab.tableName, search],
    queryFn: () => gateway.workspace.listEntities(versionId, tab.tableName, { search }),
  });

  const visibleColumns = useMemo(
    () => tab.listView.columns.filter((c) => c.visibleByDefault),
    [tab.listView.columns],
  );

  return (
    <div className="flex flex-col gap-4">
      <header className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-fg">{tab.label}</h1>
        <div className="relative w-64">
          <IconSearch className="absolute left-3 top-2.5 h-4 w-4 text-fg-subtle" aria-hidden />
          <Input
            type="search"
            placeholder={`Search ${tab.label.toLowerCase()}…`}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9"
          />
        </div>
      </header>

      <Card>
        <CardContent className="p-0">
          {dataQuery.isPending ? (
            <div className="flex flex-col">
              {[0, 1, 2, 3].map((i) => (
                <LoadingSkeletonRow key={i} />
              ))}
            </div>
          ) : dataQuery.isError ? (
            <ErrorCallout
              title="Couldn't load this list"
              message="Try again."
              action={{ label: 'Retry', onClick: () => dataQuery.refetch() }}
            />
          ) : dataQuery.data.rows.length === 0 ? (
            <EmptyState
              title="No rows yet"
              description={`Once your sources sync, ${tab.label.toLowerCase()} will appear here.`}
            />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm tabular-nums">
                <thead>
                  <tr className="border-b border-border bg-surface-2 text-xs font-medium uppercase tracking-wide text-fg-subtle">
                    {tab.listView.showSourceBadge && (
                      <th scope="col" className="px-4 py-2 text-left">
                        Source
                      </th>
                    )}
                    {visibleColumns.map((col) => (
                      <th key={col.name} scope="col" className="px-4 py-2 text-left">
                        {col.label}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {dataQuery.data.rows.map((row) => (
                    <tr
                      key={row.id}
                      tabIndex={0}
                      role="link"
                      aria-label={`Open ${tab.label} ${row.id}`}
                      className="cursor-pointer border-b border-border last:border-b-0 hover:bg-surface-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-border-focus"
                      onClick={() => setSelectedRowId(row.id)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' || e.key === ' ') {
                          e.preventDefault();
                          setSelectedRowId(row.id);
                        }
                      }}
                    >
                      {tab.listView.showSourceBadge && (
                        <td className="px-4 py-2">
                          <RowAttribution row={row} />
                        </td>
                      )}
                      {visibleColumns.map((col) => (
                        <td key={col.name} className="px-4 py-2 align-middle">
                          <RenderCell
                            column={col}
                            row={row}
                            onRevealPII={async (rowId, columnName) =>
                              gateway.workspace.revealPII(
                                versionId,
                                tab.tableName,
                                rowId,
                                columnName,
                              )
                            }
                          />
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      {selectedRowId && (
        <EntityDetailDrawer
          tab={tab}
          versionId={versionId}
          rowId={selectedRowId}
          onClose={() => setSelectedRowId(null)}
        />
      )}
    </div>
  );
}
