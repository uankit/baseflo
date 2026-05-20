import { useNavigate } from '@tanstack/react-router';
import type { RankedTableData } from '../api/workbenchClient';

interface RankedTableProps {
  table: RankedTableData;
  onRowClick?: (rowId: string, cells: Record<string, unknown>) => void;
}

export function RankedTable({ table, onRowClick }: RankedTableProps) {
  const navigate = useNavigate();

  const handleClick = (row: RankedTableData['rows'][number]) => {
    if (onRowClick) {
      onRowClick(row.row_id, row.cells);
      return;
    }
    // Auto-navigate to party drill-down if name/party_name exists
    const name = row.cells.name || row.cells.party_name;
    if (name && typeof name === 'string') {
      navigate({ to: `/os/party/${encodeURIComponent(name)}` });
    }
  };

  return (
    <div className="bg-white border-2 border-ink rounded-lg shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] overflow-hidden">
      <div className="px-4 py-3 border-b-2 border-ink bg-paper">
        <h3 className="font-bold text-ink">{table.title}</h3>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-ink/20">
              {table.columns.map((col) => (
                <th
                  key={col.key}
                  className="px-4 py-2 text-left font-semibold text-ink/70 uppercase text-xs tracking-wide"
                >
                  {col.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {table.rows.map((row) => (
              <tr
                key={row.row_id}
                onClick={() => handleClick(row)}
                className={`border-b border-ink/10 transition-colors ${
                  row.actions.includes('drill_down')
                    ? 'cursor-pointer hover:bg-paper'
                    : ''
                } ${row.severity === 'critical' ? 'bg-flame/5' : row.severity === 'high' ? 'bg-amber-50' : ''}`}
              >
                {table.columns.map((col) => (
                  <td key={col.key} className="px-4 py-2.5 text-ink">
                    {String(row.cells[col.key] ?? '—')}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
