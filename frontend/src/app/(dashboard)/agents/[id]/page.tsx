'use client';

import { useState, useMemo } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { useAgent } from '@/hooks/useAgents';
import { useAgentReports } from '@/hooks/useReports';
import { api } from '@/lib/api';
import {
  PageLoading,
  ErrorMessage,
  EmptyState,
  StatusBadge,
  StatCard,
  Tabs,
} from '@/components/ui';
import { PerformanceChart } from '@/components/charts/PerformanceChart';
import { AllocationChart } from '@/components/charts/AllocationChart';
import {
  formatCurrency,
  formatPercent,
  formatDate,
  formatStrategyType,
  getValueColorClass,
  daysRemaining,
} from '@/lib/utils';
import type { Position, Activity, DailyReport } from '@/types';

const tabs = [
  { id: 'positions', label: 'Positions' },
  { id: 'activity', label: 'Activity' },
  { id: 'reports', label: 'Reports' },
  { id: 'performance', label: 'Performance' },
  { id: 'settings', label: 'Settings' },
];

export default function AgentDetailPage() {
  const params = useParams();
  const agentId = params.id as string;
  const [activeTab, setActiveTab] = useState('positions');
  const [isRunning, setIsRunning] = useState(false);
  const [runResult, setRunResult] = useState<string | null>(null);

  const { agent, positions, activity, isLoading, error, refetch, pause, resume } =
    useAgent(agentId);

  if (isLoading) return <PageLoading />;
  if (error) return <ErrorMessage message={error} onRetry={refetch} />;
  if (!agent) return <ErrorMessage message="Agent not found" />;

  const days = agent.end_date ? daysRemaining(agent.end_date) : null;
  const openPositions = positions.filter((p) => p.status === 'open');
  const closedPositions = positions.filter((p) => p.status !== 'open');

  const handleToggle = async () => {
    try {
      if (agent.status === 'active') await pause();
      else if (agent.status === 'paused') await resume();
    } catch {
      // Error is already set in the hook
    }
  };

  const handleRunStrategy = async () => {
    setIsRunning(true);
    setRunResult(null);
    try {
      const result = await api.agents.runStrategy(agentId);
      setRunResult(
        `Strategy executed: ${result.positions_recommended} positions recommended, ${result.orders_placed} orders placed`
      );
      // Refresh agent data to reflect new positions/activity
      refetch();
    } catch (err) {
      setRunResult(
        `Failed: ${err instanceof Error ? err.message : 'Unknown error'}`
      );
    } finally {
      setIsRunning(false);
    }
  };

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
              <h1 className="text-2xl font-bold">{agent.name}</h1>
              <StatusBadge status={agent.status} />
            </div>
            <p className="text-zinc-400 mt-1">
              {formatStrategyType(agent.strategy_type)} Strategy
              {agent.persona && ` · ${agent.persona} persona`}
              {days !== null && ` · ${days} days remaining`}
            </p>
          </div>
        </div>
        <div className="flex gap-2">
          {agent.status === 'active' && (
            <button
              onClick={handleRunStrategy}
              disabled={isRunning}
              className="btn btn-secondary"
            >
              {isRunning ? 'Running...' : 'Run Strategy'}
            </button>
          )}
          <Link href={`/agents/${agentId}/chat`} className="btn btn-secondary">
            Chat
          </Link>
          {(agent.status === 'active' || agent.status === 'paused') && (
            <button onClick={handleToggle} className="btn btn-ghost">
              {agent.status === 'active' ? 'Pause' : 'Resume'}
            </button>
          )}
        </div>
      </div>

      {/* Run Result Notification */}
      {runResult && (
        <div
          className={`p-3 rounded-lg text-sm ${
            runResult.startsWith('Failed')
              ? 'bg-red-500/10 text-red-400 border border-red-500/20'
              : 'bg-green-500/10 text-green-400 border border-green-500/20'
          }`}
        >
          {runResult}
        </div>
      )}

      {/* Stats Grid */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
        <StatCard
          label="Total Value"
          value={formatCurrency(agent.total_value)}
        />
        <StatCard
          label="Total Return"
          value={formatPercent(agent.total_return_pct)}
          valueClass={getValueColorClass(agent.total_return_pct)}
        />
        <StatCard
          label="Today"
          value={formatPercent(agent.daily_return_pct)}
          valueClass={getValueColorClass(agent.daily_return_pct)}
        />
        <StatCard
          label="Sharpe Ratio"
          value={agent.sharpe_ratio?.toFixed(2) ?? '-'}
        />
        <StatCard
          label="Win Rate"
          value={agent.win_rate_pct !== null ? `${agent.win_rate_pct}%` : '-'}
        />
        <StatCard
          label="Max Drawdown"
          value={agent.max_drawdown_pct !== null ? `${agent.max_drawdown_pct}%` : '-'}
          valueClass="text-error"
        />
      </div>

      {/* Tabs */}
      <Tabs
        tabs={tabs.map((t) => ({
          ...t,
          count:
            t.id === 'positions'
              ? openPositions.length
              : t.id === 'activity'
              ? activity.length
              : undefined,
        }))}
        activeTab={activeTab}
        onChange={setActiveTab}
      />

      {/* Tab Content */}
      {activeTab === 'positions' && (
        <PositionsTab open={openPositions} closed={closedPositions} />
      )}
      {activeTab === 'activity' && <ActivityTab activity={activity} />}
      {activeTab === 'reports' && <ReportsTab agentId={agentId} />}
      {activeTab === 'performance' && (
        <PerformanceTab agent={agent} positions={openPositions} />
      )}
      {activeTab === 'settings' && <AgentSettingsTab agent={agent} />}
    </div>
  );
}

// ============================================
// Positions Tab
// ============================================

function PositionsTab({
  open,
  closed,
}: {
  open: Position[];
  closed: Position[];
}) {
  const [showClosed, setShowClosed] = useState(false);
  const positions = showClosed ? closed : open;

  return (
    <div className="space-y-4">
      <div className="flex gap-2">
        <button
          onClick={() => setShowClosed(false)}
          className={`btn text-sm ${!showClosed ? 'btn-secondary' : 'btn-ghost'}`}
        >
          Open ({open.length})
        </button>
        <button
          onClick={() => setShowClosed(true)}
          className={`btn text-sm ${showClosed ? 'btn-secondary' : 'btn-ghost'}`}
        >
          Closed ({closed.length})
        </button>
      </div>

      {positions.length === 0 ? (
        <EmptyState
          title={showClosed ? 'No closed positions' : 'No open positions'}
          description={showClosed ? 'No positions have been closed yet.' : 'This agent has no open positions.'}
        />
      ) : (
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
                  {showClosed ? 'Exit' : 'Current'}
                </th>
                <th className="text-right px-6 py-4 text-xs text-zinc-500 uppercase tracking-wide font-medium">
                  P&L
                </th>
                <th className="text-right px-6 py-4 text-xs text-zinc-500 uppercase tracking-wide font-medium">
                  Return
                </th>
                {!showClosed && (
                  <th className="text-right px-6 py-4 text-xs text-zinc-500 uppercase tracking-wide font-medium">
                    Target / Stop
                  </th>
                )}
              </tr>
            </thead>
            <tbody>
              {positions.map((pos) => {
                const pnl = showClosed ? pos.realized_pnl : pos.unrealized_pnl;
                const pnlPct = showClosed ? pos.realized_pnl_pct : pos.unrealized_pnl_pct;
                const price = showClosed ? pos.exit_price : pos.current_price;

                return (
                  <tr
                    key={pos.id}
                    className="border-b border-border last:border-b-0 hover:bg-background-hover transition-colors"
                  >
                    <td className="px-6 py-4">
                      <div className="font-medium">{pos.ticker}</div>
                      <div className="text-xs text-zinc-500">
                        {formatDate(showClosed ? pos.exit_date : pos.entry_date)}
                      </div>
                    </td>
                    <td className="px-6 py-4 text-right text-number text-zinc-400">
                      {pos.shares}
                    </td>
                    <td className="px-6 py-4 text-right text-number text-zinc-400">
                      {formatCurrency(pos.entry_price)}
                    </td>
                    <td className="px-6 py-4 text-right text-number">
                      {formatCurrency(price)}
                    </td>
                    <td
                      className={`px-6 py-4 text-right text-number ${getValueColorClass(pnl)}`}
                    >
                      {formatCurrency(pnl, { showSign: true })}
                    </td>
                    <td
                      className={`px-6 py-4 text-right text-number ${getValueColorClass(pnlPct)}`}
                    >
                      {formatPercent(pnlPct)}
                    </td>
                    {!showClosed && (
                      <td className="px-6 py-4 text-right text-xs text-zinc-500">
                        <div>
                          {pos.target_price
                            ? `TP: ${formatCurrency(pos.target_price)}`
                            : '-'}
                        </div>
                        <div>
                          {pos.stop_loss_price
                            ? `SL: ${formatCurrency(pos.stop_loss_price)}`
                            : '-'}
                        </div>
                      </td>
                    )}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// ============================================
// Activity Tab
// ============================================

function ActivityTab({ activity }: { activity: Activity[] }) {
  if (activity.length === 0) {
    return (
      <EmptyState
        title="No activity yet"
        description="Activity will appear here as the agent trades."
      />
    );
  }

  return (
    <div className="space-y-2">
      {activity.map((item) => (
        <div
          key={item.id}
          className="card py-4 flex items-center gap-4"
        >
          <ActivityIcon type={item.activity_type} />
          <div className="flex-1">
            <div className="text-sm">
              <span className="font-medium capitalize">
                {item.activity_type.replace(/_/g, ' ')}
              </span>
              {item.ticker && (
                <span className="text-accent ml-1">{item.ticker}</span>
              )}
            </div>
            {item.details && Object.keys(item.details).length > 0 && (
              <div className="text-xs text-zinc-500 mt-1">
                {Object.entries(item.details)
                  .filter(([, v]) => v !== null && v !== undefined)
                  .map(([k, v]) => `${k}: ${v}`)
                  .join(' · ')}
              </div>
            )}
          </div>
          <div className="text-xs text-zinc-500">
            {formatDate(item.created_at, { format: 'relative' })}
          </div>
        </div>
      ))}
    </div>
  );
}

function ActivityIcon({ type }: { type: string }) {
  const isTrade = type === 'buy' || type === 'sell';
  const isAlert = type === 'alert' || type === 'stop_hit' || type === 'target_hit';

  return (
    <div
      className={`w-10 h-10 rounded-full flex items-center justify-center text-xs font-bold ${
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
        ? 'BUY'
        : type === 'sell'
        ? 'SELL'
        : type === 'stop_hit'
        ? 'SL'
        : type === 'target_hit'
        ? 'TP'
        : type.substring(0, 2).toUpperCase()}
    </div>
  );
}

// ============================================
// Reports Tab
// ============================================

function ReportsTab({ agentId }: { agentId: string }) {
  const { reports, isLoading, error, page, totalPages, setPage } =
    useAgentReports(agentId);
  const [selectedReport, setSelectedReport] = useState<DailyReport | null>(null);

  if (isLoading) return <PageLoading />;
  if (error) return <ErrorMessage message={error} />;

  if (selectedReport) {
    return (
      <div className="space-y-4">
        <button
          onClick={() => setSelectedReport(null)}
          className="text-sm text-zinc-400 hover:text-zinc-50"
        >
          &larr; Back to reports
        </button>
        <ReportView report={selectedReport} />
      </div>
    );
  }

  if (reports.length === 0) {
    return (
      <EmptyState
        title="No reports yet"
        description="Daily reports will appear here once the agent starts trading."
      />
    );
  }

  return (
    <div className="space-y-4">
      <div className="space-y-2">
        {reports.map((report) => (
          <button
            key={report.id}
            onClick={() => setSelectedReport(report)}
            className="card w-full text-left hover:border-accent/50 py-4"
          >
            <div className="flex items-center justify-between">
              <div>
                <div className="font-medium">
                  {formatDate(report.report_date, { format: 'long' })}
                </div>
                <div className="text-sm text-zinc-400 mt-1 line-clamp-2">
                  {report.report_content.substring(0, 150)}...
                </div>
              </div>
              {report.performance_snapshot && (
                <div className="text-right ml-4">
                  <div className="text-sm text-number">
                    {formatCurrency(report.performance_snapshot.total_value)}
                  </div>
                  <div
                    className={`text-xs ${getValueColorClass(
                      report.performance_snapshot.daily_return_pct
                    )}`}
                  >
                    {formatPercent(report.performance_snapshot.daily_return_pct)} day
                  </div>
                </div>
              )}
            </div>
          </button>
        ))}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2">
          <button
            onClick={() => setPage(page - 1)}
            disabled={page <= 1}
            className="btn btn-ghost text-sm"
          >
            Previous
          </button>
          <span className="text-sm text-zinc-400">
            Page {page} of {totalPages}
          </span>
          <button
            onClick={() => setPage(page + 1)}
            disabled={page >= totalPages}
            className="btn btn-ghost text-sm"
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}

function ReportView({ report }: { report: DailyReport }) {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold">
          {formatDate(report.report_date, { format: 'long' })}
        </h2>
      </div>

      {/* Performance snapshot */}
      {report.performance_snapshot && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <StatCard
            label="Portfolio Value"
            value={formatCurrency(report.performance_snapshot.total_value)}
          />
          <StatCard
            label="Daily Return"
            value={formatPercent(report.performance_snapshot.daily_return_pct)}
            valueClass={getValueColorClass(report.performance_snapshot.daily_return_pct)}
          />
          <StatCard
            label="Total Return"
            value={formatPercent(report.performance_snapshot.total_return_pct)}
            valueClass={getValueColorClass(report.performance_snapshot.total_return_pct)}
          />
          <StatCard
            label="vs Benchmark"
            value={formatPercent(report.performance_snapshot.vs_benchmark)}
            valueClass={getValueColorClass(report.performance_snapshot.vs_benchmark)}
          />
        </div>
      )}

      {/* Report content */}
      <div className="card">
        <div className="prose prose-invert prose-sm max-w-none whitespace-pre-wrap">
          {report.report_content}
        </div>
      </div>

      {/* Actions taken */}
      {report.actions_taken && report.actions_taken.length > 0 && (
        <div>
          <h3 className="text-lg font-medium mb-3">Actions Taken</h3>
          <div className="space-y-2">
            {report.actions_taken.map((action, i) => (
              <div key={i} className="card py-3 flex items-center gap-3">
                <span
                  className={`badge ${
                    action.type === 'buy' ? 'badge-success' : 'badge-error'
                  }`}
                >
                  {action.type.toUpperCase()}
                </span>
                <span className="font-medium">{action.ticker}</span>
                {action.shares && (
                  <span className="text-zinc-400 text-sm">{action.shares} shares</span>
                )}
                <span className="text-sm text-number">
                  @ {formatCurrency(action.price)}
                </span>
                {action.pnl !== undefined && action.pnl !== null && (
                  <span
                    className={`text-sm text-number ${getValueColorClass(action.pnl)}`}
                  >
                    {formatCurrency(action.pnl, { showSign: true })}
                  </span>
                )}
                {action.reason && (
                  <span className="text-xs text-zinc-500 ml-auto">
                    {action.reason}
                  </span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ============================================
// Performance Tab
// ============================================

function PerformanceTab({
  agent,
  positions,
}: {
  agent: NonNullable<ReturnType<typeof useAgent>['agent']>;
  positions: Position[];
}) {
  // Build allocation data from open positions
  const allocationData = positions
    .filter((p) => p.current_value !== null)
    .map((p) => ({ name: p.ticker, value: p.current_value! }));

  if (agent.cash_balance > 0) {
    allocationData.push({ name: 'Cash', value: agent.cash_balance });
  }

  // Placeholder performance data for chart (would come from a dedicated endpoint)
  // Memoized to prevent flicker from regeneration on re-render
  const perfData = useMemo(
    () => generatePlaceholderPerfData(agent),
    [agent.allocated_capital, agent.total_value, agent.start_date]
  );

  return (
    <div className="space-y-6">
      {/* Performance Chart */}
      <div className="card">
        <h3 className="text-lg font-medium mb-4">Portfolio Value</h3>
        <PerformanceChart data={perfData} height={350} mode="value" />
      </div>

      {/* Allocation */}
      {allocationData.length > 0 && (
        <div className="card">
          <h3 className="text-lg font-medium mb-4">Current Allocation</h3>
          <AllocationChart data={allocationData} />
        </div>
      )}

      {/* Key Metrics */}
      <div className="card">
        <h3 className="text-lg font-medium mb-4">Key Metrics</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
          <MetricItem label="Allocated Capital" value={formatCurrency(agent.allocated_capital)} />
          <MetricItem label="Current Value" value={formatCurrency(agent.total_value)} />
          <MetricItem label="Cash Balance" value={formatCurrency(agent.cash_balance)} />
          <MetricItem
            label="Total Return"
            value={formatPercent(agent.total_return_pct)}
            valueClass={getValueColorClass(agent.total_return_pct)}
          />
          <MetricItem label="Sharpe Ratio" value={agent.sharpe_ratio?.toFixed(2) ?? '-'} />
          <MetricItem
            label="Max Drawdown"
            value={agent.max_drawdown_pct !== null ? `${agent.max_drawdown_pct}%` : '-'}
            valueClass="text-error"
          />
          <MetricItem
            label="Win Rate"
            value={agent.win_rate_pct !== null ? `${agent.win_rate_pct}%` : '-'}
          />
          <MetricItem label="Open Positions" value={String(positions.length)} />
        </div>
      </div>

      {/* Strategy Config */}
      <div className="card">
        <h3 className="text-lg font-medium mb-4">Strategy Configuration</h3>
        <div className="grid grid-cols-2 gap-4 text-sm">
          <ConfigItem label="Strategy" value={formatStrategyType(agent.strategy_type)} />
          <ConfigItem label="Time Horizon" value={`${agent.time_horizon_days} days`} />
          <ConfigItem label="Start Date" value={formatDate(agent.start_date)} />
          <ConfigItem label="End Date" value={formatDate(agent.end_date)} />
          {agent.risk_params && (
            <>
              <ConfigItem
                label="Stop Loss"
                value={`${agent.risk_params.stop_loss_percentage}% (${agent.risk_params.stop_loss_type})`}
              />
              <ConfigItem
                label="Max Position Size"
                value={`${agent.risk_params.max_position_size_pct}%`}
              />
              <ConfigItem
                label="Risk/Reward Ratio"
                value={`${agent.risk_params.min_risk_reward_ratio}:1`}
              />
              <ConfigItem
                label="Max Sector Concentration"
                value={`${agent.risk_params.max_sector_concentration}%`}
              />
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function MetricItem({
  label,
  value,
  valueClass,
}: {
  label: string;
  value: string;
  valueClass?: string;
}) {
  return (
    <div>
      <div className="text-xs text-zinc-500 uppercase tracking-wide">{label}</div>
      <div className={`text-lg font-semibold text-number mt-1 ${valueClass || ''}`}>
        {value}
      </div>
    </div>
  );
}

function ConfigItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between py-2 border-b border-border">
      <span className="text-zinc-400">{label}</span>
      <span className="font-medium">{value}</span>
    </div>
  );
}

// ============================================
// Agent Settings Tab
// ============================================

function AgentSettingsTab({
  agent,
}: {
  agent: NonNullable<ReturnType<typeof useAgent>['agent']>;
}) {
  return (
    <div className="max-w-2xl space-y-6">
      <div className="card">
        <h3 className="text-lg font-medium mb-4">Agent Details</h3>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-zinc-300 mb-2">
              Name
            </label>
            <input
              type="text"
              className="input"
              defaultValue={agent.name}
              readOnly
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-zinc-300 mb-2">
              Persona
            </label>
            <input
              type="text"
              className="input capitalize"
              defaultValue={agent.persona}
              readOnly
            />
          </div>
        </div>
      </div>

      <div className="card border-error/30">
        <h3 className="text-lg font-semibold text-error mb-4">Danger Zone</h3>
        <div className="flex items-center justify-between">
          <div>
            <div className="font-medium">Delete Agent</div>
            <div className="text-sm text-zinc-400">
              Permanently delete this agent and all its data
            </div>
          </div>
          <button className="btn btn-destructive text-sm">Delete Agent</button>
        </div>
      </div>
    </div>
  );
}

// ============================================
// Helper
// ============================================

function generatePlaceholderPerfData(agent: { allocated_capital: number; total_value: number | null; start_date: string }) {
  const startValue = agent.allocated_capital;
  const endValue = agent.total_value ?? agent.allocated_capital;
  const start = new Date(agent.start_date);
  const now = new Date();
  const days = Math.max(1, Math.floor((now.getTime() - start.getTime()) / (1000 * 60 * 60 * 24)));
  const numPoints = Math.min(days, 90);
  const dailyReturn = numPoints > 0 ? (endValue / startValue - 1) / numPoints : 0;

  // Deterministic seed based on start value to avoid flicker on re-render
  let seed = startValue;
  const seededRandom = () => {
    seed = (seed * 9301 + 49297) % 233280;
    return seed / 233280;
  };

  const data = [];
  let value = startValue;

  for (let i = 0; i <= numPoints; i++) {
    const date = new Date(start);
    date.setDate(date.getDate() + Math.floor((i / numPoints) * days));
    const noise = 1 + (seededRandom() - 0.5) * 0.02;
    value = value * (1 + dailyReturn) * noise;
    data.push({
      date: date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
      value: Math.round(value * 100) / 100,
      return_pct: ((value / startValue - 1) * 100),
    });
  }

  return data;
}
