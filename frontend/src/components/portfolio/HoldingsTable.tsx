import type { Holding } from '../../types/portfolio';

function fmt(n: number): string {
  return n.toLocaleString('en-US', { style: 'currency', currency: 'USD' });
}

export default function HoldingsTable({ holdings }: { holdings: Holding[] }) {
  return (
    <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
      <div className="px-4 sm:px-5 py-4 border-b border-gray-200">
        <h2 className="text-lg font-semibold text-gray-900">Holdings</h2>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-gray-50 text-left text-gray-500 font-medium">
              <th className="px-4 py-3">Ticker</th>
              <th className="px-4 py-3 hidden sm:table-cell">Name</th>
              <th className="px-4 py-3 text-right">Shares</th>
              <th className="px-4 py-3 text-right hidden md:table-cell">Avg Cost</th>
              <th className="px-4 py-3 text-right">Price</th>
              <th className="px-4 py-3 text-right">Value</th>
              <th className="px-4 py-3 text-right">Gain</th>
              <th className="px-4 py-3 text-right hidden lg:table-cell">Alloc</th>
            </tr>
          </thead>
          <tbody>
            {holdings.map((h) => {
              const isPositive = h.gain >= 0;
              return (
                <tr key={h.ticker} className="border-t border-gray-100 hover:bg-gray-50">
                  <td className="px-4 py-3 font-semibold text-gray-900">{h.ticker}</td>
                  <td className="px-4 py-3 text-gray-600 hidden sm:table-cell">{h.name}</td>
                  <td className="px-4 py-3 text-right text-gray-900">{h.shares}</td>
                  <td className="px-4 py-3 text-right text-gray-600 hidden md:table-cell">
                    {fmt(h.avgCost)}
                  </td>
                  <td className="px-4 py-3 text-right text-gray-900">{fmt(h.currentPrice)}</td>
                  <td className="px-4 py-3 text-right font-medium text-gray-900">{fmt(h.value)}</td>
                  <td
                    className={`px-4 py-3 text-right font-medium ${
                      isPositive ? 'text-green-600' : 'text-red-600'
                    }`}
                  >
                    {isPositive ? '+' : ''}
                    {h.gainPercent.toFixed(2)}%
                  </td>
                  <td className="px-4 py-3 text-right text-gray-600 hidden lg:table-cell">
                    {h.allocation.toFixed(1)}%
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
