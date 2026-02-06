'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { useAgents } from '@/hooks/useAgents';
import { api } from '@/lib/api';
import {
  PageLoading,
  ErrorMessage,
  EmptyState,
  StatCard,
} from '@/components/ui';
import {
  formatCurrency,
  formatPercent,
  formatDate,
  getValueColorClass,
} from '@/lib/utils';
import type { DailyReport, Agent } from '@/types';

export default function ReportsPage() {
  const { agents, isLoading: agentsLoading } = useAgents();
  const [selectedAgent, setSelectedAgent] = useState<Agent | null>(null);
  const [reports, setReports] = useState<DailyReport[]>([]);
  const [selectedReport, setSelectedReport] = useState<DailyReport | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);

  const selectedAgentRef = useRef<string | null>(null);

  const fetchReports = useCallback(async (agentId: string, pageNum: number) => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await api.reports.listAgentReports(agentId, pageNum, 10);
      // Only update if this agent is still selected (avoid race condition)
      if (selectedAgentRef.current === agentId) {
        setReports(data.data);
        setTotalPages(Math.ceil(data.total / 10));
      }
    } catch (err) {
      if (selectedAgentRef.current === agentId) {
        setError(err instanceof Error ? err.message : 'Failed to load reports');
      }
    } finally {
      if (selectedAgentRef.current === agentId) {
        setIsLoading(false);
      }
    }
  }, []);

  // Load reports when agent or page changes (single effect to avoid race condition)
  useEffect(() => {
    if (selectedAgent) {
      selectedAgentRef.current = selectedAgent.id;
      fetchReports(selectedAgent.id, page);
    }
  }, [selectedAgent, page, fetchReports]);

  // Auto-select first agent
  useEffect(() => {
    if (agents.length > 0 && !selectedAgent) {
      setSelectedAgent(agents[0]);
    }
  }, [agents, selectedAgent]);

  if (agentsLoading) return <PageLoading />;

  if (agents.length === 0) {
    return (
      <EmptyState
        title="No agents"
        description="Create an agent to start receiving daily reports."
        actionLabel="+ Create Agent"
        actionHref="/agents/new"
      />
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold">Reports</h1>
        <p className="text-zinc-400 mt-1">
          Browse daily trading reports from your agents
        </p>
      </div>

      {/* Agent Selector */}
      <div className="flex gap-2 flex-wrap">
        {agents.map((agent) => (
          <button
            key={agent.id}
            onClick={() => {
              setSelectedAgent(agent);
              setSelectedReport(null);
              setPage(1);
            }}
            className={`btn text-sm ${
              selectedAgent?.id === agent.id ? 'btn-secondary' : 'btn-ghost'
            }`}
          >
            <span
              className={`w-2 h-2 rounded-full ${
                agent.status === 'active' ? 'bg-success' : 'bg-zinc-500'
              }`}
            />
            {agent.name}
          </button>
        ))}
      </div>

      {error && <ErrorMessage message={error} />}

      {/* Selected Report View */}
      {selectedReport ? (
        <div className="space-y-6">
          <button
            onClick={() => setSelectedReport(null)}
            className="text-sm text-zinc-400 hover:text-zinc-50"
          >
            &larr; Back to report list
          </button>

          <div>
            <h2 className="text-xl font-semibold">
              {selectedAgent?.name} &mdash;{' '}
              {formatDate(selectedReport.report_date, { format: 'long' })}
            </h2>
          </div>

          {/* Performance Snapshot */}
          {selectedReport.performance_snapshot && (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <StatCard
                label="Portfolio Value"
                value={formatCurrency(selectedReport.performance_snapshot.total_value)}
              />
              <StatCard
                label="Daily Return"
                value={formatPercent(selectedReport.performance_snapshot.daily_return_pct)}
                valueClass={getValueColorClass(selectedReport.performance_snapshot.daily_return_pct)}
              />
              <StatCard
                label="Total Return"
                value={formatPercent(selectedReport.performance_snapshot.total_return_pct)}
                valueClass={getValueColorClass(selectedReport.performance_snapshot.total_return_pct)}
              />
              <StatCard
                label="vs Benchmark"
                value={formatPercent(selectedReport.performance_snapshot.vs_benchmark)}
                valueClass={getValueColorClass(selectedReport.performance_snapshot.vs_benchmark)}
              />
            </div>
          )}

          {/* Report Content */}
          <div className="card">
            <div className="prose prose-invert prose-sm max-w-none whitespace-pre-wrap leading-relaxed">
              {selectedReport.report_content}
            </div>
          </div>

          {/* Positions Snapshot */}
          {selectedReport.positions_snapshot && selectedReport.positions_snapshot.length > 0 && (
            <div>
              <h3 className="text-lg font-medium mb-3">Position Snapshot</h3>
              <div className="card p-0 overflow-hidden">
                <table className="w-full">
                  <thead>
                    <tr className="border-b border-border">
                      <th className="text-left px-6 py-3 text-xs text-zinc-500 uppercase tracking-wide font-medium">
                        Ticker
                      </th>
                      <th className="text-right px-6 py-3 text-xs text-zinc-500 uppercase tracking-wide font-medium">
                        Shares
                      </th>
                      <th className="text-right px-6 py-3 text-xs text-zinc-500 uppercase tracking-wide font-medium">
                        Entry
                      </th>
                      <th className="text-right px-6 py-3 text-xs text-zinc-500 uppercase tracking-wide font-medium">
                        Current
                      </th>
                      <th className="text-right px-6 py-3 text-xs text-zinc-500 uppercase tracking-wide font-medium">
                        Return
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {selectedReport.positions_snapshot.map((pos) => (
                      <tr
                        key={pos.ticker}
                        className="border-b border-border last:border-b-0"
                      >
                        <td className="px-6 py-3 font-medium">{pos.ticker}</td>
                        <td className="px-6 py-3 text-right text-number text-zinc-400">
                          {pos.shares}
                        </td>
                        <td className="px-6 py-3 text-right text-number text-zinc-400">
                          {formatCurrency(pos.entry_price)}
                        </td>
                        <td className="px-6 py-3 text-right text-number">
                          {formatCurrency(pos.current_price)}
                        </td>
                        <td
                          className={`px-6 py-3 text-right text-number ${getValueColorClass(
                            pos.return_pct
                          )}`}
                        >
                          {formatPercent(pos.return_pct)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Actions Taken */}
          {selectedReport.actions_taken && selectedReport.actions_taken.length > 0 && (
            <div>
              <h3 className="text-lg font-medium mb-3">Actions Taken</h3>
              <div className="space-y-2">
                {selectedReport.actions_taken.map((action, i) => (
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
                      <span className="text-zinc-400 text-sm">
                        {action.shares} shares
                      </span>
                    )}
                    <span className="text-sm text-number">
                      @ {formatCurrency(action.price)}
                    </span>
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
      ) : (
        /* Report List */
        <div className="space-y-4">
          {isLoading ? (
            <PageLoading />
          ) : reports.length === 0 ? (
            <EmptyState
              title="No reports yet"
              description={`${selectedAgent?.name} hasn't generated any reports yet.`}
            />
          ) : (
            <>
              <div className="space-y-2">
                {reports.map((report) => (
                  <button
                    key={report.id}
                    onClick={() => setSelectedReport(report)}
                    className="card w-full text-left hover:border-accent/50 py-4"
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex-1">
                        <div className="font-medium">
                          {formatDate(report.report_date, { format: 'long' })}
                        </div>
                        <div className="text-sm text-zinc-400 mt-1 line-clamp-2">
                          {report.report_content.substring(0, 200)}...
                        </div>
                        {report.actions_taken && report.actions_taken.length > 0 && (
                          <div className="flex gap-1 mt-2">
                            {report.actions_taken.slice(0, 3).map((action, i) => (
                              <span
                                key={i}
                                className={`badge text-xs ${
                                  action.type === 'buy'
                                    ? 'badge-success'
                                    : 'badge-error'
                                }`}
                              >
                                {action.type.toUpperCase()} {action.ticker}
                              </span>
                            ))}
                            {report.actions_taken.length > 3 && (
                              <span className="badge badge-neutral text-xs">
                                +{report.actions_taken.length - 3} more
                              </span>
                            )}
                          </div>
                        )}
                      </div>
                      {report.performance_snapshot && (
                        <div className="text-right ml-6">
                          <div className="text-sm text-number">
                            {formatCurrency(report.performance_snapshot.total_value)}
                          </div>
                          <div
                            className={`text-xs ${getValueColorClass(
                              report.performance_snapshot.daily_return_pct
                            )}`}
                          >
                            {formatPercent(report.performance_snapshot.daily_return_pct)}
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
                    onClick={() => setPage((p) => Math.max(1, p - 1))}
                    disabled={page <= 1}
                    className="btn btn-ghost text-sm"
                  >
                    Previous
                  </button>
                  <span className="text-sm text-zinc-400">
                    Page {page} of {totalPages}
                  </span>
                  <button
                    onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                    disabled={page >= totalPages}
                    className="btn btn-ghost text-sm"
                  >
                    Next
                  </button>
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}
