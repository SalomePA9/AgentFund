'use client';

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
  Cell,
} from 'recharts';

interface BarDataPoint {
  label: string;
  value: number;
}

interface BarMetricProps {
  data: BarDataPoint[];
  height?: number;
  colorByValue?: boolean;
  formatter?: (value: number) => string;
}

export function BarMetric({
  data,
  height = 200,
  colorByValue = true,
  formatter,
}: BarMetricProps) {
  if (data.length === 0) {
    return (
      <div
        className="flex items-center justify-center text-zinc-500 text-sm"
        style={{ height }}
      >
        No data available
      </div>
    );
  }

  const hasNegative = data.some((d) => d.value < 0);

  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} margin={{ top: 5, right: 10, left: 10, bottom: 5 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#27272A" vertical={false} />
        <XAxis
          dataKey="label"
          tick={{ fill: '#71717A', fontSize: 11 }}
          tickLine={false}
          axisLine={{ stroke: '#27272A' }}
        />
        <YAxis
          tick={{ fill: '#71717A', fontSize: 11 }}
          tickLine={false}
          axisLine={false}
          tickFormatter={formatter}
        />
        <Tooltip
          contentStyle={{
            backgroundColor: '#18181B',
            border: '1px solid #27272A',
            borderRadius: '8px',
            fontSize: '12px',
          }}
          formatter={(value: number) => [
            formatter ? formatter(value) : value.toFixed(2),
            'Value',
          ]}
        />
        {hasNegative && <ReferenceLine y={0} stroke="#3F3F46" />}
        <Bar dataKey="value" radius={hasNegative ? 0 : [4, 4, 0, 0]}>
          {data.map((entry, index) => (
            <Cell
              key={`cell-${index}`}
              fill={
                colorByValue
                  ? entry.value >= 0
                    ? '#22C55E'
                    : '#EF4444'
                  : '#3B82F6'
              }
            />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
