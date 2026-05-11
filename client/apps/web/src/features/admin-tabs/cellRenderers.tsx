import {
  AttributionBadge,
  DateCell,
  MoneyCell,
  PIIField,
  StatusChip,
  Badge,
} from '@baseflo/ui';
import { IconExternalLink } from '@baseflo/ui/icons';
import type {
  EntityRow,
  ListColumnSpec,
  PIIRevealResponse,
} from '@baseflo/contracts';

export interface RenderCellProps {
  column: ListColumnSpec;
  row: EntityRow;
  onRevealPII?: (rowId: string, column: string) => Promise<PIIRevealResponse>;
}

/**
 * Per-WidgetKind cell renderer. Maps the schema-driven column spec from
 * AdminUISpec to a typed visual.
 */
export function RenderCell({ column, row, onRevealPII }: RenderCellProps) {
  const value = row.values[column.name];

  if (value === null || value === undefined || value === '') {
    return <span className="text-fg-subtle">—</span>;
  }

  switch (column.widget) {
    case 'text':
    case 'long_text':
      return <span className="text-sm text-fg">{String(value)}</span>;

    case 'number':
      return (
        <span className="text-sm tabular-nums text-fg">
          {typeof value === 'number'
            ? value.toLocaleString()
            : String(value)}
        </span>
      );

    case 'money':
      return (
        <MoneyCell
          minor={typeof value === 'number' ? value : Number(value) || 0}
          currency={column.currency ?? 'USD'}
        />
      );

    case 'date':
      return <DateCell iso={String(value)} withTime={false} />;
    case 'datetime':
      return <DateCell iso={String(value)} relative />;

    case 'status_chip':
      return <StatusChip value={String(value)} />;

    case 'pii_masked':
      return (
        <PIIField
          masked={maskEmail(String(value))}
          onReveal={async () => {
            if (!onRevealPII) {
              return { value: String(value), expiresAt: new Date(Date.now() + 30_000).toISOString() };
            }
            return onRevealPII(row.id, column.name);
          }}
          ariaLabel={column.label}
        />
      );

    case 'link':
      return (
        <a
          href={`#${value}`}
          className="inline-flex items-center gap-1 text-sm text-accent underline-offset-4 hover:underline"
        >
          {String(value)} <IconExternalLink className="h-3 w-3" />
        </a>
      );

    case 'boolean':
      return <Badge variant={value ? 'success' : 'neutral'}>{value ? 'Yes' : 'No'}</Badge>;

    case 'select':
      return <Badge variant="neutral">{String(value)}</Badge>;

    case 'file_upload':
      return <span className="text-sm text-fg-muted">{String(value)}</span>;

    default:
      return <span className="text-sm text-fg">{String(value)}</span>;
  }
}

export function RowAttribution({ row }: { row: EntityRow }) {
  return <AttributionBadge contributions={row.contributions} />;
}

function maskEmail(value: string): string {
  if (!value.includes('@')) return value.slice(0, 2) + '••••••';
  const [user, domain] = value.split('@');
  if (!user || !domain) return '••••••';
  return `${user.slice(0, 2)}••••@${domain}`;
}
