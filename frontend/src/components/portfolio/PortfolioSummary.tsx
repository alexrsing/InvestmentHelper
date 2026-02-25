import type { PortfolioSummary as PortfolioSummaryType } from "../../types";

interface Props {
  data: PortfolioSummaryType;
}

export default function PortfolioSummary({ data }: Props) {
  const isPositive = data.percent_change >= 0;
  const changeColor = isPositive ? "text-green-400" : "text-red-400";
  const sign = isPositive ? "+" : "";

  const fmt = (v: number) =>
    v.toLocaleString("en-US", { style: "currency", currency: "USD" });

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
      <div className="border border-gray-800 rounded p-4 bg-[#161b22]">
        <div className="text-xs text-gray-500 uppercase tracking-wider mb-1">
          Total Value
        </div>
        <div className="text-xl font-mono text-gray-100">{fmt(data.total_value)}</div>
      </div>
      <div className="border border-gray-800 rounded p-4 bg-[#161b22]">
        <div className="text-xs text-gray-500 uppercase tracking-wider mb-1">
          Initial Value
        </div>
        <div className="text-xl font-mono text-gray-100">{fmt(data.initial_value)}</div>
      </div>
      <div className="border border-gray-800 rounded p-4 bg-[#161b22]">
        <div className="text-xs text-gray-500 uppercase tracking-wider mb-1">
          Change
        </div>
        <div className={`text-xl font-mono ${changeColor}`}>
          {sign}{data.percent_change.toFixed(2)}%
        </div>
      </div>
    </div>
  );
}
