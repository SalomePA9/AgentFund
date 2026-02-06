'use client';

import Link from 'next/link';
import { formatCurrency, formatPercent, getValueColorClass } from '@/lib/utils';

// Placeholder data
const mockAgents = [
  {
    id: '1',
    name: 'Alpha Momentum',
    strategy_type: 'momentum',
    status: 'active',
    total_value: 52430.0,
    total_return_pct: 4.86,
    positions_count: 8,
    days_remaining: 142,
  },
  {
    id: '2',
    name: 'Value Hunter',
    strategy_type: 'quality_value',
    status: 'active',
    total_value: 48750.0,
    total_return_pct: -2.5,
    positions_count: 6,
    days_remaining: 89,
  },
  {
    id: '3',
    name: 'Dividend Compounder',
    strategy_type: 'dividend_growth',
    status: 'paused',
    total_value: 25000.0,
    total_return_pct: 1.2,
    positions_count: 4,
    days_remaining: 365,
  },
];

export default function AgentsPage() {
  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Agents</h1>
          <p className="text-zinc-400 mt-1">Manage your trading agents</p>
        </div>
        <Link href="/agents/new" className="btn btn-primary">
          + Create Agent
        </Link>
      </div>

      {/* Filters */}
      <div className="flex gap-2">
        <button className="btn btn-secondary text-sm">All</button>
        <button className="btn btn-ghost text-sm">Active</button>
        <button className="btn btn-ghost text-sm">Paused</button>
      </div>

      {/* Agents Table */}
      <div className="card p-0 overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="border-b border-border">
              <th className="text-left px-6 py-4 text-xs text-zinc-500 uppercase tracking-wide font-medium">
                Agent
              </th>
              <th className="text-left px-6 py-4 text-xs text-zinc-500 uppercase tracking-wide font-medium">
                Strategy
              </th>
              <th className="text-left px-6 py-4 text-xs text-zinc-500 uppercase tracking-wide font-medium">
                Status
              </th>
              <th className="text-right px-6 py-4 text-xs text-zinc-500 uppercase tracking-wide font-medium">
                Value
              </th>
              <th className="text-right px-6 py-4 text-xs text-zinc-500 uppercase tracking-wide font-medium">
                Return
              </th>
              <th className="text-right px-6 py-4 text-xs text-zinc-500 uppercase tracking-wide font-medium">
                Positions
              </th>
              <th className="px-6 py-4"></th>
            </tr>
          </thead>
          <tbody>
            {mockAgents.map((agent) => (
              <tr
                key={agent.id}
                className="border-b border-border last:border-b-0 hover:bg-background-hover transition-colors"
              >
                <td className="px-6 py-4">
                  <Link
                    href={`/agents/${agent.id}`}
                    className="font-medium hover:text-accent transition-colors"
                  >
                    {agent.name}
                  </Link>
                </td>
                <td className="px-6 py-4 text-zinc-400 capitalize">
                  {agent.strategy_type.replace(/_/g, ' ')}
                </td>
                <td className="px-6 py-4">
                  <span
                    className={`badge ${
                      agent.status === 'active'
                        ? 'badge-success'
                        : agent.status === 'paused'
                        ? 'badge-warning'
                        : 'badge-neutral'
                    }`}
                  >
                    {agent.status}
                  </span>
                </td>
                <td className="px-6 py-4 text-right text-number">
                  {formatCurrency(agent.total_value)}
                </td>
                <td
                  className={`px-6 py-4 text-right text-number ${getValueColorClass(
                    agent.total_return_pct
                  )}`}
                >
                  {formatPercent(agent.total_return_pct)}
                </td>
                <td className="px-6 py-4 text-right text-zinc-400">
                  {agent.positions_count}
                </td>
                <td className="px-6 py-4 text-right">
                  <Link
                    href={`/agents/${agent.id}`}
                    className="btn btn-ghost text-xs"
                  >
                    View
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
