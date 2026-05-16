import { asDisplayValue, labelize } from '../../common/model/format.js';

export function EvidenceTable({
  rows,
  maxRows = 8,
}: {
  rows: Array<Record<string, unknown>>;
  maxRows?: number;
}) {
  if (!rows.length) {
    return <p className="text-sm text-ink/55">No row-level preview is attached to this artifact.</p>;
  }
  const columns = Array.from(new Set(rows.flatMap((row) => Object.keys(row)))).slice(0, 8);
  return (
    <div className="overflow-x-auto border border-ink/20 bg-paper-soft">
      <table className="min-w-full text-left text-sm">
        <thead className="border-b border-ink/20 text-[11px] uppercase tracking-[0.16em] text-ink/45">
          <tr>
            {columns.map((column) => (
              <th key={column} className="whitespace-nowrap px-3 py-2 font-semibold">
                {labelize(column)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-ink/10">
          {rows.slice(0, maxRows).map((row, index) => (
            <tr key={index} className="align-top">
              {columns.map((column) => (
                <td key={column} className="max-w-[260px] truncate px-3 py-2 text-ink/75">
                  {asDisplayValue(row[column])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
