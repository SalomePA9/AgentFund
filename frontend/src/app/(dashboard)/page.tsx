'use client';

import Link from 'next/link';
import { formatCurrency, formatPercent, getValueColorClass } from '@/lib/utils';

// Placeholder data - will be replaced with API calls
const mockAgents = [
  {
    id: '1',
    name: 'Alpha Momentum',
    strategy_type: 'momentum',
    status: 'active',
    total_value: 52430.0,
    total_return_pct: 4.86,
    daily_return_pct: 0.32,
    positions_count: 8,
    days_remaining: 142,
    today_summary:
      'Solid day with tech momentum continuing. Added NVDA position on breakout.',
  },
  {
    id: '2',
    name: 'Value Hunter',
    strategy_type: 'quality_value',
    status: 'active',
    total_value: 48750.0,
    total_return_pct: -2.5,
    daily_return_pct: -0.15,
    positions_count: 6,
    days_remaining: 89,
    today_summary:
      'Patience required. Value stocks underperforming but fundamentals remain strong.',
  },
  {
    id: '3',
    name: 'Dividend Compounder',
    strategy_type: 'dividend_growth',
    status: 'paused',
    total_value: 25000.0,
    total_return_pct: 1.2,
    daily_return_pct: 0.0,
    positions_count: 4,
    days_remaining: 365,
    today_summary: 'Agent paused by user.',
  },
];

const totalValue = mockAgents.reduce((sum, a) => sum + a.total_value, 0);
const totalAllocated = 125000;
const totalReturn = ((totalValue / totalAllocated) - 1) * 100;

export default function DashboardPage() {
  return (
    <div className="space-y-8">
      {/* Page Header */}
      <div>
        <h1 className="text-2xl font-bold">Dashboard</h1>
        <p className="text-zinc-400 mt-1">
          Overview of your trading team performance
        </p>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          label="Total Portfolio Value"
          value={formatCurrency(totalValue)}
          change={totalReturn}
        />
        <StatCard
          label="Today's Change"
          value={formatCurrency(totalValue * 0.0015, { showSign: true })}
          change={0.15}
        />
        <StatCard label="Active Agents" value="2" subtitle="of 3 total" />
        <StatCard label="Open Positions" value="18" subtitle="across all agents" />
      </div>

      {/* Agents Section */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-xl font-semibold">Your Agents</h2>
          <Link href="/agents/new" className="btn btn-primary">
            + Create Agent
          </Link>
        </div>

        <div className="space-y-4">
          {mockAgents.map((agent) => (
            <AgentCard key={agent.id} agent={agent} />
          ))}
        </div>
      </div>
    </div>
  );
}

// Stat Card Component
function StatCard({
  label,
  value,
  change,
  subtitle,
}: {
  label: string;
  value: string;
  change?: number;
  subtitle?: string;
}) {
  return (
    <div className="card">
      <div className="text-xs text-zinc-500 uppercase tracking-wide mb-1">
        {label}
      </div>
      <div className="text-2xl font-semibold text-number">{value}</div>
      {change !== undefined && (
        <div className={`text-sm mt-1 ${getValueColorClass(change)}`}>
          {formatPercent(change)}
        </div>
      )}
      {subtitle && <div className="text-sm text-zinc-500 mt-1">{subtitle}</div>}
    </div>
  );
}

// Agent Card Component
function AgentCard({
  agent,
}: {
  agent: (typeof mockAgents)[0];
}) {
  const statusColors = {
    active: 'bg-success',
    paused: 'bg-warning',
    stopped: 'bg-error',
    completed: 'bg-zinc-500',
  };

  return (
    <Link href={`/agents/${agent.id}`} className="block">
      <div className="card hover:border-accent/50 transition-all">
        <div className="flex items-start justify-between">
          {/* Left: Agent Info */}
          <div className="flex items-start gap-3">
            <div
              className={`w-3 h-3 rounded-full mt-1.5 ${
                statusColors[agent.status as keyof typeof statusColors]
              }`}
            />
            <div>
              <h3 className="font-semibold text-lg">{agent.name}</h3>
              <p className="text-sm text-zinc-500">
                {agent.strategy_type.replace(/_/g, ' ')} •{' '}
                {agent.positions_count} positions • {agent.days_remaining} days
                remaining
              </p>
            </div>
          </div>

          {/* Right: Performance */}
          <div className="text-right">
            <div className="text-xl font-semibold text-number">
              {formatCurrency(agent.total_value)}
            </div>
            <div className={`text-sm ${getValueColorClass(agent.total_return_pct)}`}>
              {formatPercent(agent.total_return_pct)}
            </div>
          </div>
        </div>

        {/* Today's Summary */}
        <div className="mt-4 p-3 bg-background rounded-lg">
          <p className="text-sm text-zinc-400 italic">
            &ldquo;{agent.today_summary}&rdquo;
          </p>
        </div>

        {/* Quick Actions */}
        <div className="mt-4 flex gap-2">
          <button className="btn btn-secondary text-xs py-1.5">View</button>
          <button className="btn btn-secondary text-xs py-1.5">Chat</button>
          {agent.status === 'active' ? (
            <button className="btn btn-ghost text-xs py-1.5">Pause</button>
          ) : (
            <button className="btn btn-ghost text-xs py-1.5">Resume</button>
          )}
        </div>
      </div>
    </Link>
  );
}
