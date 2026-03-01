import { Link } from "react-router-dom";
import Navbar from "../components/layout/Navbar";
import { useTradeHistory } from "../hooks/useTradeHistory";

function fmt(v: number): string {
  return v.toLocaleString("en-US", { style: "currency", currency: "USD" });
}

export default function TradeHistoryPage() {
  const { data, loading, error } = useTradeHistory();

  return (
    <div className="min-h-screen bg-[#0d1117] text-gray-100">
      <Navbar />

      <main className="max-w-6xl mx-auto px-4 py-6">
        <div className="flex items-center justify-between mb-4">
          <h1 className="text-sm text-gray-500 uppercase tracking-wider font-mono">
            Trade History
          </h1>
          <Link
            to="/"
            className="text-gray-500 hover:text-gray-300 transition-colors text-sm font-mono"
          >
            &larr; Dashboard
          </Link>
        </div>

        {loading && (
          <div className="text-gray-500 font-mono text-center py-12">
            Loading trades...
          </div>
        )}

        {error && (
          <div className="text-red-400 font-mono text-center py-12">
            {error}
          </div>
        )}

        {data && data.trades.length === 0 && (
          <div className="text-gray-500 font-mono text-center py-12">
            No trades recorded yet
          </div>
        )}

        {data && data.trades.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full text-sm font-mono">
              <thead>
                <tr className="border-b border-gray-800 text-gray-500 text-xs uppercase">
                  <th className="text-left py-2 pr-4">Date</th>
                  <th className="text-left py-2 pr-4">Ticker</th>
                  <th className="text-left py-2 pr-4">Signal</th>
                  <th className="text-left py-2 pr-4">Action</th>
                  <th className="text-right py-2 pr-4">Shares</th>
                  <th className="text-right py-2 pr-4">Price</th>
                  <th className="text-right py-2 pr-4">Pos Before</th>
                  <th className="text-right py-2 pr-4">Pos After</th>
                  <th className="text-right py-2 pr-4">Cash Before</th>
                  <th className="text-right py-2">Cash After</th>
                </tr>
              </thead>
              <tbody>
                {data.trades.map((trade, i) => {
                  const actionColor = trade.action === "accepted"
                    ? trade.signal === "Buy" ? "text-green-400" : "text-red-400"
                    : "text-gray-500";
                  const signalColor = trade.signal === "Buy" ? "text-green-400" : "text-red-400";

                  return (
                    <tr key={`${trade.date}-${trade.ticker}-${i}`} className="border-b border-gray-800/50 hover:bg-[#161b22]">
                      <td className="py-2 pr-4 text-gray-400">{trade.date}</td>
                      <td className="py-2 pr-4 text-green-400 font-bold">{trade.ticker}</td>
                      <td className={`py-2 pr-4 ${signalColor}`}>{trade.signal}</td>
                      <td className={`py-2 pr-4 ${actionColor} uppercase`}>{trade.action}</td>
                      <td className="py-2 pr-4 text-right text-gray-300">{trade.shares}</td>
                      <td className="py-2 pr-4 text-right text-gray-300">{fmt(trade.price)}</td>
                      <td className="py-2 pr-4 text-right text-gray-400">{trade.position_before}</td>
                      <td className="py-2 pr-4 text-right text-gray-300">{trade.position_after}</td>
                      <td className="py-2 pr-4 text-right text-gray-400">{fmt(trade.cash_before)}</td>
                      <td className="py-2 text-right text-gray-300">{fmt(trade.cash_after)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </main>
    </div>
  );
}
