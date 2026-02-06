'use client';

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from 'recharts';
import { formatCurrency, formatPercent } from '@/lib/utils';

interface DataPoint {
  date: string;
  value: number;
  return_pct: number;
  benchmark?: number;
}

interface PerformanceChartProps {
  data: DataPoint[];
  height?: number;
  showBenchmark?: boolean;
  mode?: 'value' | 'return';
}

export function PerformanceChart({
  data,
  height = 300,
  showBenchmark = false,
  mode = 'value',
}: PerformanceChartProps) {
  if (data.length === 0) {
    return (
      <div
        className="flex items-center justify-center text-zinc-500 text-sm"
        style={{ height }}
      >
        No performance data available
      </div>
    );
  }

  const dataKey = mode === 'value' ? 'value' : 'return_pct';
  const formatter = mode === 'value' ? formatCurrency : (v: number) => formatPercent(v);

  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data} margin={{ top: 5, right: 10, left: 10, bottom: 5 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#27272A" />
        <XAxis
          dataKey="date"
          tick={{ fill: '#71717A', fontSize: 12 }}
          tickLine={false}
          axisLine={{ stroke: '#27272A' }}
        />
        <YAxis
          tick={{ fill: '#71717A', fontSize: 12 }}
          tickLine={false}
          axisLine={false}
          tickFormatter={(v) =>
            mode === 'value'
              ? `$${(v / 1000).toFixed(0)}k`
              : `${v.toFixed(1)}%`
          }
        />
        <Tooltip
          contentStyle={{
            backgroundColor: '#18181B',
            border: '1px solid #27272A',
            borderRadius: '8px',
            fontSize: '12px',
          }}
          labelStyle={{ color: '#A1A1AA' }}
          formatter={(value: number) => [formatter(value), mode === 'value' ? 'Value' : 'Return']}
        />
        {mode === 'return' && (
          <ReferenceLine y={0} stroke="#3F3F46" strokeDasharray="3 3" />
        )}
        <Line
          type="monotone"
          dataKey={dataKey}
          stroke="#3B82F6"
          strokeWidth={2}
          dot={false}
          activeDot={{ r: 4, fill: '#3B82F6' }}
        />
        {showBenchmark && (
          <Line
            type="monotone"
            dataKey="benchmark"
            stroke="#71717A"
            strokeWidth={1}
            strokeDasharray="4 4"
            dot={false}
          />
        )}
      </LineChart>
    </ResponsiveContainer>
  );
}
