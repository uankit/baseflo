import { useQuery } from '@tanstack/react-query';
import {
  Button,
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  ErrorCallout,
  Label,
  Spinner,
} from '@baseflo/ui';
import type { AdminTab, EntityRow } from '@baseflo/contracts';
import { useGateway } from '../../providers/GatewayProvider.js';
import { RenderCell, RowAttribution } from './cellRenderers.js';

interface Props {
  tab: AdminTab;
  versionId: string;
  rowId: string;
  onClose: () => void;
}

export function EntityDetailDrawer({ tab, versionId, rowId, onClose }: Props) {
  const gateway = useGateway();

  const rowQuery = useQuery({
    queryKey: ['entity', versionId, tab.tableName, rowId],
    queryFn: () => gateway.workspace.getEntity(versionId, tab.tableName, rowId),
  });

  return (
    <Dialog open={true} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>
            {tab.label.replace(/s$/, '')} · {rowId}
          </DialogTitle>
          <DialogDescription>
            Read-only canonical record assembled from connected sources.
          </DialogDescription>
        </DialogHeader>

        {rowQuery.isPending && (
          <div className="flex items-center justify-center py-8">
            <Spinner />
          </div>
        )}
        {rowQuery.isError && (
          <ErrorCallout title="Couldn't load record" message="Try again." />
        )}
        {rowQuery.data && (
          <DetailBody
            tab={tab}
            row={rowQuery.data}
            versionId={versionId}
            onRevealPII={(columnName) =>
              gateway.workspace.revealPII(versionId, tab.tableName, rowId, columnName)
            }
          />
        )}

        <DialogFooter>
          <Button onClick={onClose}>
            Close
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function DetailBody({
  tab,
  row,
  onRevealPII,
}: {
  tab: AdminTab;
  row: EntityRow;
  versionId: string;
  onRevealPII: (columnName: string) => Promise<{ value: string; expiresAt: string }>;
}) {
  const colMap = new Map(tab.listView.columns.map((c) => [c.name, c]));

  return (
    <div className="flex flex-col gap-6">
      <RowAttribution row={row} />
      {tab.detailView.sections.map((section) => (
        <section key={section.id}>
          <h3 className="mb-3 text-xs font-semibold uppercase tracking-wide text-fg-subtle">
            {section.label}
          </h3>
          <dl className="grid gap-3 sm:grid-cols-2">
            {section.columns.map((columnName) => {
              const column = colMap.get(columnName);
              if (!column) return null;
              return (
                <div key={columnName} className="flex flex-col gap-1">
                  <Label className="text-xs uppercase tracking-wide text-fg-subtle">
                    {column.label}
                  </Label>
                  <RenderCell
                    column={column}
                    row={row}
                    onRevealPII={async (_rowId, name) => onRevealPII(name)}
                  />
                </div>
              );
            })}
          </dl>
        </section>
      ))}
      {tab.detailView.relationships.length > 0 && (
        <section>
          <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-fg-subtle">
            Relationships
          </h3>
          <ul className="flex flex-wrap gap-2">
            {tab.detailView.relationships.map((rel) => (
              <li key={rel.toTable}>
                <Button variant="secondary" size="sm">
                  {rel.label} →
                </Button>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
