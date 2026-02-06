'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useAgents } from '@/hooks/useAgents';
import { PageLoading, ErrorMessage, EmptyState, StatusBadge } from '@/components/ui';
import {
  formatCurrency,
  formatPercent,
  formatStrategyType,
  getValueColorClass,
} from '@/lib/utils';

const filterOptions = [
  { label: 'All', value: undefined },
  { label: 'Active', value: 'active' },
  { label: 'Paused', value: 'paused' },
  { label: 'Stopped', value: 'stopped' },
];

export default function AgentsPage() {
  const [statusFilter, setStatusFilter] = useState<string | undefined>(undefined);
  const { agents, isLoading, error, refetch, pauseAgent, resumeAgent } = useAgents(statusFilter);

  if (isLoading) return <PageLoading />;
  if (error) return <ErrorMessage message={error} onRetry={refetch} />;

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
        {filterOptions.map((opt) => (
          <button
            key={opt.label}
            onClick={() => setStatusFilter(opt.value)}
            className={`btn text-sm ${
              statusFilter === opt.value ? 'btn-secondary' : 'btn-ghost'
            }`}
          >
            {opt.label}
          </button>
        ))}
      </div>

      {agents.length === 0 ? (
        <EmptyState
          title={statusFilter ? `No ${statusFilter} agents` : 'No agents yet'}
          description={
            statusFilter
              ? 'Try a different filter or create a new agent.'
              : 'Create your first trading agent to get started.'
          }
          actionLabel="+ Create Agent"
          actionHref="/agents/new"
        />
      ) : (
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
                  Sharpe
                </th>
                <th className="px-6 py-4"></th>
              </tr>
            </thead>
            <tbody>
              {agents.map((agent) => (
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
                    <div className="text-xs text-zinc-500 mt-0.5">{agent.persona}</div>
                  </td>
                  <td className="px-6 py-4 text-zinc-400">
                    {formatStrategyType(agent.strategy_type)}
                  </td>
                  <td className="px-6 py-4">
                    <StatusBadge status={agent.status} />
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
                  <td className="px-6 py-4 text-right text-number text-zinc-400">
                    {agent.sharpe_ratio?.toFixed(2) ?? '-'}
                  </td>
                  <td className="px-6 py-4 text-right">
                    <div className="flex items-center justify-end gap-1">
                      {agent.status === 'active' && (
                        <button
                          onClick={() => { pauseAgent(agent.id).catch(() => {}); }}
                          className="btn btn-ghost text-xs py-1"
                        >
                          Pause
                        </button>
                      )}
                      {agent.status === 'paused' && (
                        <button
                          onClick={() => { resumeAgent(agent.id).catch(() => {}); }}
                          className="btn btn-ghost text-xs py-1"
                        >
                          Resume
                        </button>
                      )}
                      <Link
                        href={`/agents/${agent.id}`}
                        className="btn btn-ghost text-xs py-1"
                      >
                        View
                      </Link>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
