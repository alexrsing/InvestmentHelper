import type { ETFHistoryItem } from '../../types/etf';

function fmt(n: number): string {
  return `$${n.toFixed(2)}`;
}

function fmtVol(n: number): string {
  if (n >= 1e6) return `${(n / 1e6).toFixed(1)}M`;
  if (n >= 1e3) return `${(n / 1e3).toFixed(1)}K`;
  return n.toLocaleString();
}

export default function PriceHistoryTable({ history }: { history: ETFHistoryItem[] }) {
  if (history.length === 0) return null;

  // Show most recent first, limited to 30 rows
  const rows = [...history].reverse().slice(0, 30);

  return (
    <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
      <div className="px-4 sm:px-5 py-4 border-b border-gray-200 flex items-center justify-between">
        <h2 className="text-lg font-semibold text-gray-900">Price History</h2>
        <span className="text-xs text-gray-500">
          Showing {rows.length} of {history.length} records
        </span>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-gray-50 text-left text-gray-500 font-medium">
              <th className="px-4 py-3">Date</th>
              <th className="px-4 py-3 text-right">Open</th>
              <th className="px-4 py-3 text-right">High</th>
              <th className="px-4 py-3 text-right">Low</th>
              <th className="px-4 py-3 text-right">Close</th>
              <th className="px-4 py-3 text-right hidden sm:table-cell">Volume</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((item) => (
              <tr key={item.date} className="border-t border-gray-100 hover:bg-gray-50">
                <td className="px-4 py-2.5 text-gray-900">{item.date}</td>
                <td className="px-4 py-2.5 text-right text-gray-600">{fmt(item.open_price)}</td>
                <td className="px-4 py-2.5 text-right text-green-600">{fmt(item.high_price)}</td>
                <td className="px-4 py-2.5 text-right text-red-600">{fmt(item.low_price)}</td>
                <td className="px-4 py-2.5 text-right font-medium text-gray-900">
                  {fmt(item.close_price)}
                </td>
                <td className="px-4 py-2.5 text-right text-gray-500 hidden sm:table-cell">
                  {fmtVol(item.volume)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
