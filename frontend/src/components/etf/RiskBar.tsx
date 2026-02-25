interface Props {
  low: number;
  high: number;
  current: number;
}

export default function RiskBar({ low, high, current }: Props) {
  const range = high - low;
  const penetration = range > 0 ? ((current - low) / range) * 100 : 0;
  const clamped = Math.max(0, Math.min(100, penetration));

  let barColor = "bg-green-500";
  if (clamped > 70) barColor = "bg-red-500";
  else if (clamped > 40) barColor = "bg-yellow-500";

  return (
    <div className="flex items-center gap-2 min-w-[180px]">
      <div className="relative w-full h-2 bg-gray-800 rounded overflow-hidden">
        <div
          className={`absolute top-0 left-0 h-full rounded ${barColor}`}
          style={{ width: `${clamped}%` }}
        />
      </div>
      <span className="text-xs font-mono text-gray-400 w-10 text-right">
        {clamped.toFixed(0)}%
      </span>
    </div>
  );
}
