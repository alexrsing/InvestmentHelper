import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from 'recharts';
import type { AllocationSlice } from '../../types/portfolio';

export default function AllocationChart({ data }: { data: AllocationSlice[] }) {
  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4 sm:p-5">
      <h2 className="text-lg font-semibold text-gray-900 mb-4">Allocation</h2>
      <div className="flex flex-col lg:flex-row items-center gap-4">
        <div className="w-full lg:w-1/2" style={{ height: 260 }}>
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={data}
                dataKey="percent"
                nameKey="name"
                cx="50%"
                cy="50%"
                innerRadius={60}
                outerRadius={100}
                paddingAngle={2}
              >
                {data.map((slice) => (
                  <Cell key={slice.ticker} fill={slice.color} />
                ))}
              </Pie>
              <Tooltip
                formatter={(value: number | undefined) => value != null ? `${value.toFixed(1)}%` : ''}
                contentStyle={{ fontSize: '0.875rem' }}
              />
            </PieChart>
          </ResponsiveContainer>
        </div>
        <div className="w-full lg:w-1/2 grid grid-cols-2 gap-2">
          {data.map((slice) => (
            <div key={slice.ticker} className="flex items-center gap-2 text-sm">
              <span
                className="w-3 h-3 rounded-full shrink-0"
                style={{ backgroundColor: slice.color }}
              />
              <span className="text-gray-600 truncate">{slice.name}</span>
              <span className="ml-auto font-medium text-gray-900">{slice.percent.toFixed(1)}%</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
