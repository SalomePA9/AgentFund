'use client';

import { useState, useEffect, useCallback } from 'react';
import type { Agent, Position, Activity } from '@/types';
import { api } from '@/lib/api';

/**
 * Hook for fetching and managing the list of agents
 */
export function useAgents(statusFilter?: string) {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchAgents = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await api.agents.list(statusFilter);
      setAgents(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch agents');
    } finally {
      setIsLoading(false);
    }
  }, [statusFilter]);

  useEffect(() => {
    fetchAgents();
  }, [fetchAgents]);

  const pauseAgent = useCallback(async (id: string) => {
    try {
      const updated = await api.agents.pause(id);
      setAgents((prev) => prev.map((a) => (a.id === id ? updated : a)));
      return updated;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to pause agent');
      throw err;
    }
  }, []);

  const resumeAgent = useCallback(async (id: string) => {
    try {
      const updated = await api.agents.resume(id);
      setAgents((prev) => prev.map((a) => (a.id === id ? updated : a)));
      return updated;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to resume agent');
      throw err;
    }
  }, []);

  const deleteAgent = useCallback(async (id: string) => {
    try {
      await api.agents.delete(id);
      setAgents((prev) => prev.filter((a) => a.id !== id));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete agent');
      throw err;
    }
  }, []);

  return {
    agents,
    isLoading,
    error,
    refetch: fetchAgents,
    pauseAgent,
    resumeAgent,
    deleteAgent,
  };
}

/**
 * Hook for fetching a single agent with all its related data
 */
export function useAgent(id: string) {
  const [agent, setAgent] = useState<Agent | null>(null);
  const [positions, setPositions] = useState<Position[]>([]);
  const [activity, setActivity] = useState<Activity[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchAgent = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const [agentData, positionsData, activityData] = await Promise.all([
        api.agents.get(id),
        api.agents.getPositions(id),
        api.agents.getActivity(id),
      ]);
      setAgent(agentData);
      setPositions(positionsData);
      setActivity(activityData);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch agent');
    } finally {
      setIsLoading(false);
    }
  }, [id]);

  useEffect(() => {
    fetchAgent();
  }, [fetchAgent]);

  const pause = useCallback(async () => {
    try {
      const updated = await api.agents.pause(id);
      setAgent(updated);
      return updated;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to pause agent');
      throw err;
    }
  }, [id]);

  const resume = useCallback(async () => {
    try {
      const updated = await api.agents.resume(id);
      setAgent(updated);
      return updated;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to resume agent');
      throw err;
    }
  }, [id]);

  return {
    agent,
    positions,
    activity,
    isLoading,
    error,
    refetch: fetchAgent,
    pause,
    resume,
  };
}

/**
 * Hook for the team summary / dashboard data
 */
export function useTeamSummary() {
  const [summary, setSummary] = useState<Awaited<ReturnType<typeof api.reports.getTeamSummary>> | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchSummary = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await api.reports.getTeamSummary();
      setSummary(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch summary');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchSummary();
  }, [fetchSummary]);

  return { summary, isLoading, error, refetch: fetchSummary };
}
