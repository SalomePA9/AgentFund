'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import type { ChatMessage } from '@/types';
import { api } from '@/lib/api';

/**
 * Hook for managing chat with an agent
 */
export function useChat(agentId: string) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isSending, setIsSending] = useState(false);
  const [hasMore, setHasMore] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const messagesRef = useRef<ChatMessage[]>([]);

  const fetchHistory = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await api.chat.getHistory(agentId);
      const reversed = [...data.data].reverse();
      messagesRef.current = reversed;
      setMessages(reversed);
      setHasMore(data.has_more);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load chat history');
    } finally {
      setIsLoading(false);
    }
  }, [agentId]);

  useEffect(() => {
    fetchHistory();
  }, [fetchHistory]);

  const sendMessage = useCallback(
    async (message: string) => {
      setIsSending(true);
      setError(null);

      // Optimistically add user message
      const tempUserMsg: ChatMessage = {
        id: `temp-${Date.now()}`,
        agent_id: agentId,
        role: 'user',
        message,
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, tempUserMsg]);

      try {
        const { user_message, agent_response } = await api.chat.sendMessage(agentId, message);
        // Replace temp message with real ones
        setMessages((prev) => [
          ...prev.filter((m) => m.id !== tempUserMsg.id),
          user_message,
          agent_response,
        ]);
      } catch (err) {
        // Remove optimistic message on error
        setMessages((prev) => prev.filter((m) => m.id !== tempUserMsg.id));
        setError(err instanceof Error ? err.message : 'Failed to send message');
      } finally {
        setIsSending(false);
      }
    },
    [agentId]
  );

  const loadMore = useCallback(async () => {
    if (!hasMore || messagesRef.current.length === 0) return;

    try {
      const oldest = messagesRef.current[0];
      const data = await api.chat.getHistory(agentId, 50, oldest.created_at);
      const older = [...data.data].reverse();
      setMessages((prev) => {
        const merged = [...older, ...prev];
        messagesRef.current = merged;
        return merged;
      });
      setHasMore(data.has_more);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load more messages');
    }
  }, [agentId, hasMore]);

  const clearHistory = useCallback(async () => {
    try {
      await api.chat.clearHistory(agentId);
      setMessages([]);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to clear history');
    }
  }, [agentId]);

  return {
    messages,
    isLoading,
    isSending,
    hasMore,
    error,
    sendMessage,
    loadMore,
    clearHistory,
  };
}
