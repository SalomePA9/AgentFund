'use client';

import Link from 'next/link';
import { useParams } from 'next/navigation';
import { formatCurrency, formatPercent, getValueColorClass } from '@/lib/utils';

// Placeholder data
const mockAgent = {
  id: '1',
  name: 'Alpha Momentum',
  persona: 'analytical',
  strategy_type: 'momentum',
  status: 'active',
  allocated_capital: 50000,
  total_value: 52430.0,
  cash_balance: 5243.0,
  total_return_pct: 4.86,
  daily_return_pct: 0.32,
  sharpe_ratio: 1.42,
  max_drawdown_pct: 3.2,
  win_rate_pct: 68,
  days_remaining: 142,
  start_date: '2024-09-01',
  end_date: '2025-03-01',
};

const mockPositions = [
  {
    id: '1',
    ticker: 'NVDA',
    entry_price: 875.5,
    current_price: 920.3,
    shares: 5,
    unrealized_pnl: 224.0,
    unrealized_pnl_pct: 5.11,
    status: 'open',
  },
  {
    id: '2',
    ticker: 'AAPL',
    entry_price: 182.0,
    current_price: 185.5,
    shares: 25,
    unrealized_pnl: 87.5,
    unrealized_pnl_pct: 1.92,
    status: 'open',
  },
  {
    id: '3',
    ticker: 'MSFT',
    entry_price: 405.0,
    current_price: 415.2,
    shares: 12,
    unrealized_pnl: 122.4,
    unrealized_pnl_pct: 2.52,
    status: 'open',
  },
];

export default function AgentDetailPage() {
  const params = useParams();
  const agentId = params.id;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Link href="/agents" className="text-zinc-400 hover:text-zinc-50">
            &larr; Back
          </Link>
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-bold">{mockAgent.name}</h1>
              <span className="badge badge-success">{mockAgent.status}</span>
            </div>
            <p className="text-zinc-400 mt-1 capitalize">
              {mockAgent.strategy_type.replace(/_/g, ' ')} Strategy •{' '}
              {mockAgent.persona} persona
            </p>
          </div>
        </div>
        <div className="flex gap-2">
          <Link
            href={`/agents/${agentId}/chat`}
            className="btn btn-secondary"
          >
            Chat
          </Link>
          <Link href={`/agents/${agentId}/edit`} className="btn btn-secondary">
            Edit
          </Link>
          <button className="btn btn-ghost">Pause</button>
        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
        <StatCard
          label="Total Value"
          value={formatCurrency(mockAgent.total_value)}
        />
        <StatCard
          label="Total Return"
          value={formatPercent(mockAgent.total_return_pct)}
          valueClass={getValueColorClass(mockAgent.total_return_pct)}
        />
        <StatCard
          label="Today"
          value={formatPercent(mockAgent.daily_return_pct)}
          valueClass={getValueColorClass(mockAgent.daily_return_pct)}
        />
        <StatCard label="Sharpe Ratio" value={mockAgent.sharpe_ratio.toFixed(2)} />
        <StatCard label="Win Rate" value={`${mockAgent.win_rate_pct}%`} />
        <StatCard label="Days Left" value={mockAgent.days_remaining.toString()} />
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-border">
        <TabButton active>Positions</TabButton>
        <TabButton>Activity</TabButton>
        <TabButton>Reports</TabButton>
        <TabButton>Settings</TabButton>
      </div>

      {/* Positions Table */}
      <div className="card p-0 overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="border-b border-border">
              <th className="text-left px-6 py-4 text-xs text-zinc-500 uppercase tracking-wide font-medium">
                Ticker
              </th>
              <th className="text-right px-6 py-4 text-xs text-zinc-500 uppercase tracking-wide font-medium">
                Shares
              </th>
              <th className="text-right px-6 py-4 text-xs text-zinc-500 uppercase tracking-wide font-medium">
                Entry
              </th>
              <th className="text-right px-6 py-4 text-xs text-zinc-500 uppercase tracking-wide font-medium">
                Current
              </th>
              <th className="text-right px-6 py-4 text-xs text-zinc-500 uppercase tracking-wide font-medium">
                P&L
              </th>
              <th className="text-right px-6 py-4 text-xs text-zinc-500 uppercase tracking-wide font-medium">
                Return
              </th>
            </tr>
          </thead>
          <tbody>
            {mockPositions.map((position) => (
              <tr
                key={position.id}
                className="border-b border-border last:border-b-0 hover:bg-background-hover transition-colors"
              >
                <td className="px-6 py-4 font-medium">{position.ticker}</td>
                <td className="px-6 py-4 text-right text-number text-zinc-400">
                  {position.shares}
                </td>
                <td className="px-6 py-4 text-right text-number text-zinc-400">
                  {formatCurrency(position.entry_price)}
                </td>
                <td className="px-6 py-4 text-right text-number">
                  {formatCurrency(position.current_price)}
                </td>
                <td
                  className={`px-6 py-4 text-right text-number ${getValueColorClass(
                    position.unrealized_pnl
                  )}`}
                >
                  {formatCurrency(position.unrealized_pnl, { showSign: true })}
                </td>
                <td
                  className={`px-6 py-4 text-right text-number ${getValueColorClass(
                    position.unrealized_pnl_pct
                  )}`}
                >
                  {formatPercent(position.unrealized_pnl_pct)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function StatCard({
  label,
  value,
  valueClass,
}: {
  label: string;
  value: string;
  valueClass?: string;
}) {
  return (
    <div className="card py-4">
      <div className="text-xs text-zinc-500 uppercase tracking-wide mb-1">
        {label}
      </div>
      <div className={`text-lg font-semibold text-number ${valueClass || ''}`}>
        {value}
      </div>
    </div>
  );
}

function TabButton({
  children,
  active,
}: {
  children: React.ReactNode;
  active?: boolean;
}) {
  return (
    <button
      className={`px-4 py-3 text-sm font-medium border-b-2 transition-colors ${
        active
          ? 'border-accent text-zinc-50'
          : 'border-transparent text-zinc-400 hover:text-zinc-50'
      }`}
    >
      {children}
    </button>
  );
}
