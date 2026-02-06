'use client';

import {
  PieChart,
  Pie,
  Cell,
  ResponsiveContainer,
  Tooltip,
} from 'recharts';
import { formatCurrency } from '@/lib/utils';

interface AllocationSlice {
  name: string;
  value: number;
}

interface AllocationChartProps {
  data: AllocationSlice[];
  height?: number;
}

const COLORS = [
  '#3B82F6', // blue
  '#8B5CF6', // purple
  '#22C55E', // green
  '#F59E0B', // amber
  '#EF4444', // red
  '#06B6D4', // cyan
  '#EC4899', // pink
  '#F97316', // orange
];

export function AllocationChart({ data, height = 250 }: AllocationChartProps) {
  if (data.length === 0) {
    return (
      <div
        className="flex items-center justify-center text-zinc-500 text-sm"
        style={{ height }}
      >
        No allocation data
      </div>
    );
  }

  const total = data.reduce((sum, d) => sum + d.value, 0);

  return (
    <div className="flex items-center gap-6">
      <div style={{ width: height, height }}>
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={data}
              cx="50%"
              cy="50%"
              innerRadius="60%"
              outerRadius="85%"
              paddingAngle={2}
              dataKey="value"
            >
              {data.map((_, index) => (
                <Cell
                  key={`cell-${index}`}
                  fill={COLORS[index % COLORS.length]}
                />
              ))}
            </Pie>
            <Tooltip
              contentStyle={{
                backgroundColor: '#18181B',
                border: '1px solid #27272A',
                borderRadius: '8px',
                fontSize: '12px',
              }}
              formatter={(value: number) => [formatCurrency(value), 'Value']}
            />
          </PieChart>
        </ResponsiveContainer>
      </div>

      {/* Legend */}
      <div className="flex-1 space-y-2">
        {data.map((item, index) => (
          <div key={item.name} className="flex items-center justify-between text-sm">
            <div className="flex items-center gap-2">
              <div
                className="w-3 h-3 rounded-full"
                style={{ backgroundColor: COLORS[index % COLORS.length] }}
              />
              <span className="text-zinc-300">{item.name}</span>
            </div>
            <div className="text-right">
              <span className="text-number text-zinc-200">
                {formatCurrency(item.value)}
              </span>
              <span className="text-zinc-500 ml-2 text-xs">
                {total > 0 ? ((item.value / total) * 100).toFixed(1) : '0.0'}%
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
