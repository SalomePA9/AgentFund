'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useAgents, useTeamSummary } from '@/hooks/useAgents';
import { StatCard, PageLoading, ErrorMessage, EmptyState, StatusBadge } from '@/components/ui';
import {
  formatCurrency,
  formatPercent,
  formatDate,
  formatStrategyType,
  getValueColorClass,
  daysRemaining,
} from '@/lib/utils';
import type { Agent } from '@/types';

export default function DashboardPage() {
  const { agents, isLoading: agentsLoading, error: agentsError, refetch: refetchAgents, pauseAgent, resumeAgent } = useAgents();
  const { summary, isLoading: summaryLoading, error: summaryError, refetch: refetchSummary } = useTeamSummary();

  const isLoading = agentsLoading || summaryLoading;
  const error = agentsError || summaryError;

  if (isLoading) return <PageLoading />;
  if (error) return <ErrorMessage message={error} onRetry={() => { refetchAgents(); refetchSummary(); }} />;

  const activeAgents = agents.filter((a) => a.status === 'active').length;
  const totalPositions = agents.reduce((sum, a) => sum + (a.total_value ? 1 : 0), 0);

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
          value={formatCurrency(summary?.total_portfolio_value ?? 0)}
          change={summary?.total_return_pct}
        />
        <StatCard
          label="Today's Change"
          value={formatCurrency(summary?.total_daily_change ?? 0, { showSign: true })}
          change={summary?.total_daily_return_pct}
          changeLabel="today"
        />
        <StatCard
          label="Active Agents"
          value={String(activeAgents)}
          subtitle={`of ${agents.length} total`}
        />
        <StatCard
          label="Open Positions"
          value={String(totalPositions)}
          subtitle="across all agents"
        />
      </div>

      {/* Recent Actions */}
      {summary?.recent_actions && summary.recent_actions.length > 0 && (
        <div className="space-y-3">
          <h2 className="text-lg font-semibold">Recent Activity</h2>
          <div className="card p-0 divide-y divide-border">
            {summary.recent_actions.slice(0, 5).map((action, i) => (
              <div key={i} className="px-6 py-3 flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <ActivityIcon type={action.activity_type} />
                  <div>
                    <span className="text-sm font-medium">{action.agent_name}</span>
                    <span className="text-zinc-400 text-sm ml-2">
                      {action.activity_type.replace(/_/g, ' ')}
                      {action.ticker && ` ${action.ticker}`}
                    </span>
                  </div>
                </div>
                <span className="text-xs text-zinc-500">
                  {formatDate(action.created_at, { format: 'relative' })}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Agents Section */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-xl font-semibold">Your Agents</h2>
          <Link href="/agents/new" className="btn btn-primary">
            + Create Agent
          </Link>
        </div>

        {agents.length === 0 ? (
          <EmptyState
            title="No agents yet"
            description="Create your first trading agent to get started."
            actionLabel="+ Create Agent"
            actionHref="/agents/new"
          />
        ) : (
          <div className="space-y-4">
            {agents.map((agent) => (
              <AgentCard
                key={agent.id}
                agent={agent}
                onPause={pauseAgent}
                onResume={resumeAgent}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function AgentCard({
  agent,
  onPause,
  onResume,
}: {
  agent: Agent;
  onPause: (id: string) => Promise<Agent>;
  onResume: (id: string) => Promise<Agent>;
}) {
  const [actionLoading, setActionLoading] = useState(false);

  const handleToggleStatus = async (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setActionLoading(true);
    try {
      if (agent.status === 'active') {
        await onPause(agent.id);
      } else if (agent.status === 'paused') {
        await onResume(agent.id);
      }
    } finally {
      setActionLoading(false);
    }
  };

  const days = agent.end_date ? daysRemaining(agent.end_date) : null;

  return (
    <Link href={`/agents/${agent.id}`} className="block">
      <div className="card hover:border-accent/50 transition-all">
        <div className="flex items-start justify-between">
          {/* Left: Agent Info */}
          <div className="flex items-start gap-3">
            <div className="mt-1">
              <StatusDot status={agent.status} />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="font-semibold text-lg">{agent.name}</h3>
                <StatusBadge status={agent.status} />
              </div>
              <p className="text-sm text-zinc-500 mt-0.5">
                {formatStrategyType(agent.strategy_type)}
                {agent.persona && ` · ${agent.persona}`}
                {days !== null && ` · ${days} days remaining`}
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
            {agent.daily_return_pct !== null && (
              <div className={`text-xs ${getValueColorClass(agent.daily_return_pct)}`}>
                {formatPercent(agent.daily_return_pct)} today
              </div>
            )}
          </div>
        </div>

        {/* Stats Row */}
        <div className="mt-4 grid grid-cols-4 gap-4 px-2">
          <MiniStat label="Capital" value={formatCurrency(agent.allocated_capital)} />
          <MiniStat label="Cash" value={formatCurrency(agent.cash_balance)} />
          <MiniStat
            label="Sharpe"
            value={agent.sharpe_ratio?.toFixed(2) ?? '-'}
          />
          <MiniStat
            label="Win Rate"
            value={agent.win_rate_pct !== null ? `${agent.win_rate_pct}%` : '-'}
          />
        </div>

        {/* Quick Actions */}
        <div className="mt-4 flex gap-2">
          <Link
            href={`/agents/${agent.id}`}
            className="btn btn-secondary text-xs py-1.5"
            onClick={(e) => e.stopPropagation()}
          >
            View
          </Link>
          <Link
            href={`/agents/${agent.id}/chat`}
            className="btn btn-secondary text-xs py-1.5"
            onClick={(e) => e.stopPropagation()}
          >
            Chat
          </Link>
          {(agent.status === 'active' || agent.status === 'paused') && (
            <button
              className="btn btn-ghost text-xs py-1.5"
              onClick={handleToggleStatus}
              disabled={actionLoading}
            >
              {actionLoading
                ? '...'
                : agent.status === 'active'
                ? 'Pause'
                : 'Resume'}
            </button>
          )}
        </div>
      </div>
    </Link>
  );
}

function MiniStat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-xs text-zinc-500">{label}</div>
      <div className="text-sm font-medium text-number">{value}</div>
    </div>
  );
}

function StatusDot({ status }: { status: string }) {
  const colors: Record<string, string> = {
    active: 'bg-success',
    paused: 'bg-warning',
    stopped: 'bg-error',
    completed: 'bg-zinc-500',
  };

  return (
    <div className={`w-3 h-3 rounded-full ${colors[status] || 'bg-zinc-500'}`} />
  );
}

function ActivityIcon({ type }: { type: string }) {
  const isTrade = type === 'buy' || type === 'sell';
  const isAlert = type === 'alert' || type === 'stop_hit' || type === 'target_hit';

  return (
    <div
      className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-medium ${
        isTrade
          ? type === 'buy'
            ? 'bg-success-subtle text-success'
            : 'bg-error-subtle text-error'
          : isAlert
          ? 'bg-warning-subtle text-warning'
          : 'bg-background-tertiary text-zinc-400'
      }`}
    >
      {type === 'buy'
        ? 'B'
        : type === 'sell'
        ? 'S'
        : type === 'stop_hit'
        ? 'SL'
        : type === 'target_hit'
        ? 'TP'
        : type.charAt(0).toUpperCase()}
    </div>
  );
}
