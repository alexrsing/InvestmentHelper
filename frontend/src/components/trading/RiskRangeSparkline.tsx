import {
  ComposedChart,
  Area,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
import type { ETFHistoryItem } from '../../types/etf';

interface ChartDataPoint {
  date: string;
  high: number;
  low: number;
  close: number;
}

export default function RiskRangeSparkline({
  history,
  ticker,
}: {
  history: ETFHistoryItem[];
  ticker: string;
}) {
  if (history.length < 2) return null;

  const data: ChartDataPoint[] = history.map((item) => ({
    date: item.date,
    high: item.high_price,
    low: item.low_price,
    close: item.close_price,
  }));

  const allPrices = data.flatMap((d) => [d.high, d.low, d.close]);
  const minPrice = Math.min(...allPrices);
  const maxPrice = Math.max(...allPrices);
  const padding = (maxPrice - minPrice) * 0.05;

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4 sm:p-5">
      <h2 className="text-lg font-semibold text-gray-900 mb-1">Risk Range — {ticker}</h2>
      <p className="text-xs text-gray-500 mb-4">
        Shaded area shows high-low range. Blue line is closing price.
      </p>
      <div style={{ height: 300 }}>
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={data} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
            <XAxis
              dataKey="date"
              tick={{ fontSize: 11 }}
              tickFormatter={(d: string) => {
                const date = new Date(d + 'T00:00:00');
                return `${date.getMonth() + 1}/${date.getDate()}`;
              }}
              interval="preserveStartEnd"
              minTickGap={40}
            />
            <YAxis
              domain={[minPrice - padding, maxPrice + padding]}
              tick={{ fontSize: 11 }}
              tickFormatter={(v: number) => `$${v.toFixed(0)}`}
              width={55}
            />
            <Tooltip
              formatter={(value: number | undefined, name: string | undefined) => [
                value != null ? `$${value.toFixed(2)}` : '',
                name === 'high' ? 'High' : name === 'low' ? 'Low' : 'Close',
              ]}
              labelFormatter={(label) => {
                const date = new Date(String(label) + 'T00:00:00');
                return date.toLocaleDateString('en-US', {
                  month: 'short',
                  day: 'numeric',
                  year: 'numeric',
                });
              }}
              contentStyle={{ fontSize: '0.8rem' }}
            />

            {/* High line (top of risk range) */}
            <Area
              type="monotone"
              dataKey="high"
              stroke="#ef4444"
              strokeWidth={1}
              strokeDasharray="4 2"
              fill="transparent"
              dot={false}
            />

            {/* Low line (bottom of risk range) - filled area up to high */}
            <Area
              type="monotone"
              dataKey="low"
              stroke="#22c55e"
              strokeWidth={1}
              strokeDasharray="4 2"
              fill="transparent"
              dot={false}
            />

            {/* Shaded area between high and low */}
            <Area
              type="monotone"
              dataKey="high"
              stroke="none"
              fill="#3b82f6"
              fillOpacity={0.08}
              dot={false}
              activeDot={false}
            />

            {/* Close price line */}
            <Line
              type="monotone"
              dataKey="close"
              stroke="#3b82f6"
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 4, fill: '#3b82f6' }}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
      <div className="flex gap-6 mt-3 text-xs text-gray-500">
        <span className="flex items-center gap-1.5">
          <span className="w-4 h-0 border-t-2 border-dashed border-red-400" /> High
        </span>
        <span className="flex items-center gap-1.5">
          <span className="w-4 h-0 border-t-2 border-dashed border-green-500" /> Low
        </span>
        <span className="flex items-center gap-1.5">
          <span className="w-4 h-0 border-t-2 border-blue-500" /> Close
        </span>
      </div>
    </div>
  );
}
