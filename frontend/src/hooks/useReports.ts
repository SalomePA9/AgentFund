'use client';

import { useState, useEffect, useCallback } from 'react';
import type { DailyReport } from '@/types';
import { api } from '@/lib/api';

/**
 * Hook for fetching paginated reports for an agent
 */
export function useAgentReports(agentId: string, perPage = 10) {
  const [reports, setReports] = useState<DailyReport[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Reset page when agentId changes
  useEffect(() => {
    setPage(1);
  }, [agentId]);

  const fetchReports = useCallback(async () => {
    if (!agentId) return;
    setIsLoading(true);
    setError(null);
    try {
      const data = await api.reports.listAgentReports(agentId, page, perPage);
      setReports(data.data);
      setTotal(data.total);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch reports');
    } finally {
      setIsLoading(false);
    }
  }, [agentId, page, perPage]);

  useEffect(() => {
    fetchReports();
  }, [fetchReports]);

  const totalPages = Math.ceil(total / perPage);

  return {
    reports,
    total,
    page,
    totalPages,
    isLoading,
    error,
    setPage,
    refetch: fetchReports,
  };
}

/**
 * Hook for fetching a single daily report
 */
export function useReport(agentId: string, date: string) {
  const [report, setReport] = useState<DailyReport | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchReport = useCallback(async () => {
    if (!date || !agentId) {
      setIsLoading(false);
      return;
    }
    setIsLoading(true);
    setError(null);
    try {
      const data = await api.reports.getAgentReport(agentId, date);
      setReport(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch report');
    } finally {
      setIsLoading(false);
    }
  }, [agentId, date]);

  useEffect(() => {
    fetchReport();
  }, [fetchReport]);

  return { report, isLoading, error, refetch: fetchReport };
}
