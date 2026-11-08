export type Column<T> = { key: string; label: string; className?: string; render: (row: T) => React.ReactNode };

export function DataTable<T>({ columns, rows, rowKey, empty, testId }: {
  columns: Column<T>[];
  rows: T[];
  rowKey: (row: T) => string;
  empty?: React.ReactNode;
  testId?: string;
}) {
  return (
    <div className="overflow-x-auto rounded-xl border border-line bg-white">
      <table className="w-full min-w-[960px] border-collapse text-sm" data-testid={testId}>
        <thead>
          <tr className="border-b border-line bg-canvas text-left text-xs uppercase tracking-wide text-ink-2">
            {columns.map((c) => (
              <th key={c.key} className={`px-3 py-2 font-semibold ${c.className ?? ""}`}>
                {c.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={rowKey(r)} className="border-b border-line align-top last:border-0 hover:bg-canvas/60" data-row={rowKey(r)}>
              {columns.map((c) => (
                <td key={c.key} className={`px-3 py-2 ${c.className ?? ""}`}>
                  {c.render(r)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {!rows.length && <div className="px-4 py-10 text-center text-sm text-ink-2">{empty}</div>}
    </div>
  );
}
