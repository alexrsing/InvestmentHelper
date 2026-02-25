import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from "recharts";
import type { ETFHistoryResponse } from "../../types";

interface Props {
  ticker: string;
  data: ETFHistoryResponse | null;
  loading: boolean;
  error: string | null;
  onClose: () => void;
}

export default function ETFDetailModal({
  ticker,
  data,
  loading,
  error,
  onClose,
}: Props) {
  const history = data?.history ?? [];
  const sorted = [...history].sort((a, b) => a.date.localeCompare(b.date));
  const hasEnoughData = sorted.length >= 2;

  const latestWithRisk = [...sorted]
    .reverse()
    .find((h) => h.risk_range_low != null && h.risk_range_high != null);
  const riskLow = latestWithRisk?.risk_range_low;
  const riskHigh = latestWithRisk?.risk_range_high;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70"
      onClick={onClose}
    >
      <div
        className="bg-[#161b22] border border-gray-700 rounded-lg w-full max-w-2xl mx-4 p-6"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-green-400 font-mono font-bold text-xl">
            {ticker}
          </h2>
          <button
            type="button"
            onClick={onClose}
            className="text-gray-500 hover:text-gray-300 font-mono text-lg cursor-pointer"
          >
            [CLOSE]
          </button>
        </div>

        {loading && (
          <div className="text-gray-500 font-mono text-center py-12">
            Loading...
          </div>
        )}

        {error && (
          <div className="text-red-400 font-mono text-center py-12">
            {error}
          </div>
        )}

        {!loading && !error && !hasEnoughData && (
          <div className="text-yellow-400 font-mono text-center py-12">
            ETF does not have required history data
          </div>
        )}

        {!loading && !error && hasEnoughData && (
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={sorted}>
                <XAxis
                  dataKey="date"
                  tick={{ fill: "#6b7280", fontSize: 10, fontFamily: "monospace" }}
                  axisLine={{ stroke: "#374151" }}
                  tickLine={false}
                />
                <YAxis
                  domain={["auto", "auto"]}
                  tick={{ fill: "#6b7280", fontSize: 10, fontFamily: "monospace" }}
                  axisLine={{ stroke: "#374151" }}
                  tickLine={false}
                  tickFormatter={(v: number) => `$${v}`}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "#0d1117",
                    border: "1px solid #374151",
                    borderRadius: "4px",
                    fontFamily: "monospace",
                    fontSize: "12px",
                  }}
                  labelStyle={{ color: "#9ca3af" }}
                  itemStyle={{ color: "#34d399" }}
                  formatter={(value: number | undefined) => [
                    value != null ? `$${value.toFixed(2)}` : "—",
                    "Price",
                  ]}
                />
                <Line
                  type="monotone"
                  dataKey="close_price"
                  stroke="#34d399"
                  strokeWidth={2}
                  dot={false}
                  name="Price"
                />
                {riskLow != null && (
                  <ReferenceLine
                    y={riskLow}
                    stroke="#f87171"
                    strokeDasharray="4 4"
                    label={{
                      value: `Low $${riskLow}`,
                      fill: "#f87171",
                      fontSize: 10,
                      fontFamily: "monospace",
                      position: "left",
                    }}
                  />
                )}
                {riskHigh != null && (
                  <ReferenceLine
                    y={riskHigh}
                    stroke="#f87171"
                    strokeDasharray="4 4"
                    label={{
                      value: `High $${riskHigh}`,
                      fill: "#f87171",
                      fontSize: 10,
                      fontFamily: "monospace",
                      position: "left",
                    }}
                  />
                )}
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>
    </div>
  );
}
