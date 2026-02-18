export default function StatCard({
  label,
  value,
  subValue,
  trend,
}: {
  label: string;
  value: string;
  subValue?: string;
  trend?: 'up' | 'down' | 'neutral';
}) {
  const trendColor =
    trend === 'up' ? 'text-green-600' : trend === 'down' ? 'text-red-600' : 'text-gray-600';

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4 sm:p-5">
      <p className="text-sm font-medium text-gray-500 mb-1">{label}</p>
      <p className="text-xl sm:text-2xl font-bold text-gray-900">{value}</p>
      {subValue && <p className={`text-sm mt-1 font-medium ${trendColor}`}>{subValue}</p>}
    </div>
  );
}
