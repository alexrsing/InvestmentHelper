import type { PerformancePeriod } from '../../types/portfolio';

export default function PerformanceCard({ periods }: { periods: PerformancePeriod[] }) {
  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4 sm:p-5">
      <h2 className="text-lg font-semibold text-gray-900 mb-4">Performance</h2>
      <div className="flex flex-wrap gap-3">
        {periods.map((p) => {
          const isPositive = p.returnPercent >= 0;
          return (
            <div
              key={p.label}
              className="flex-1 min-w-[80px] text-center rounded-lg border border-gray-100 p-3"
            >
              <p className="text-xs font-medium text-gray-500 mb-1">{p.label}</p>
              <p
                className={`text-lg font-bold ${isPositive ? 'text-green-600' : 'text-red-600'}`}
              >
                {isPositive ? '+' : ''}{p.returnPercent.toFixed(2)}%
              </p>
            </div>
          );
        })}
      </div>
    </div>
  );
}
